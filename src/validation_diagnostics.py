import argparse
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

try:
    import numpy as np
    import pandas as pd
    from sklearn.model_selection import train_test_split
except ImportError as exc:
    raise RuntimeError("Install project dependencies from requirements.txt") from exc

from src.ingest_multisource import BILATERAL_ALPHA
from src.nlp_pipeline import sanitize_many
from src.spatial_engine import DomainPartitionedKDTreeIndexer
from src.train_pipeline import (
    DEFAULT_IDW_NEIGHBORS,
    OOT_TIMESTAMP_COLUMN,
    SplitData,
    _build_category_mean_baseline,
    _fit_feature_matrices,
    _metric_summary,
    _oot_train_derived_metadata,
    _predict_category_mean_baseline,
    _predict_idw,
    build_stratified_splits,
    load_harmonized_parquet,
)

DEFAULT_DIAGNOSTIC_DIR = os.path.join("reports", "m6_7_validation_diagnostics")
DEFAULT_SEEDS = (42, 43, 44)
MIN_DIAGNOSTIC_ROWS = 30
HIGH_ERROR_KES = 5000.0
POST_ARBITRAGE_RATE_BOUNDS = (500.0, 35000.0)


def detect_duplicate_records(
    frame: pd.DataFrame,
    key_columns: Sequence[str] = ("raw_description", "target_rate"),
) -> Dict[str, Any]:
    available_columns = [column for column in key_columns if column in frame.columns]
    if not available_columns:
        raise ValueError("At least one duplicate-detection key column must exist in the frame.")

    normalized = frame[available_columns].copy()
    if "raw_description" in normalized.columns:
        normalized["raw_description"] = (
            normalized["raw_description"].astype(str).str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
        )
    duplicate_mask = normalized.duplicated(keep=False)
    groups = normalized.loc[duplicate_mask].value_counts(dropna=False)
    group_rows = []
    for key, count in groups.items():
        key_tuple = key if isinstance(key, tuple) else (key,)
        group_rows.append({**dict(zip(available_columns, key_tuple)), "rows": int(count)})

    return {
        "key_columns": available_columns,
        "duplicate_rows": int(duplicate_mask.sum()),
        "duplicate_groups": int(len(group_rows)),
        "duplicate_rate": round(float(duplicate_mask.mean()), 6),
        "examples": group_rows[:20],
    }


def compute_partition_metrics(
    frame: pd.DataFrame,
    predictions: np.ndarray,
    partition_column: str = "industry_partition",
) -> pd.DataFrame:
    if len(frame) != len(predictions):
        raise ValueError("Frame rows and prediction rows must have equal length.")

    rows: List[Dict[str, Any]] = []
    target = frame["target_rate"].to_numpy(dtype=float)
    for partition, indices in frame.groupby(partition_column).groups.items():
        positions = np.asarray(list(indices), dtype=int)
        metrics = _metric_summary(target[positions], np.asarray(predictions)[positions])
        rows.append({"partition": str(partition), "rows": int(len(positions)), **metrics})
    return pd.DataFrame(rows).sort_values("rows", ascending=False).reset_index(drop=True)


def compute_confidence_interval(values: Sequence[float], confidence: float = 0.95) -> Dict[str, float]:
    array = np.asarray(values, dtype=float)
    if array.size == 0 or not np.all(np.isfinite(array)):
        raise ValueError("Confidence interval values must be finite and non-empty.")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1.")
    mean = float(np.mean(array))
    std = float(np.std(array, ddof=1)) if array.size > 1 else 0.0
    margin = 1.96 * std / float(np.sqrt(array.size))
    return {
        "mean": round(mean, 6),
        "std": round(std, 6),
        "ci_lower": round(mean - margin, 6),
        "ci_upper": round(mean + margin, 6),
        "confidence": float(confidence),
        "samples": int(array.size),
    }


def _fit_and_score_seed(
    frame: pd.DataFrame,
    macro_lookup_path: str,
    seed: int,
    k_neighbors: int,
    n_components: int,
    max_features: int,
    alpha: float,
) -> Dict[str, Any]:
    split_data = build_stratified_splits(frame, random_state=seed)
    matrices = _fit_feature_matrices(
        split_data=split_data,
        macro_lookup_path=macro_lookup_path,
        n_components=n_components,
        max_features=max_features,
        alpha=alpha,
        save_artifacts=False,
    )
    indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=1)
    indexer.fit(
        matrices.x_train,
        [str(value) for value in split_data.train["industry_partition"].tolist()],
        record_indices=np.asarray(split_data.train["record_id"].to_numpy(), dtype=int).tolist(),
        verified_rates=matrices.y_train.tolist(),
    )
    validation_predictions = _predict_idw(
        indexer,
        matrices.x_validation,
        [str(value) for value in split_data.validation["industry_partition"].tolist()],
        k_neighbors,
    )
    test_predictions = _predict_idw(
        indexer,
        matrices.x_test,
        [str(value) for value in split_data.test["industry_partition"].tolist()],
        k_neighbors,
    )
    return {
        "seed": int(seed),
        "split_rows": {"train": len(split_data.train), "validation": len(split_data.validation), "test": len(split_data.test)},
        "validation_metrics": _metric_summary(matrices.y_validation, validation_predictions),
        "test_metrics": _metric_summary(matrices.y_test, test_predictions),
        "validation_frame": split_data.validation,
        "validation_predictions": validation_predictions,
        "test_frame": split_data.test,
        "test_predictions": test_predictions,
    }


def run_validation_diagnostics(
    harmonized_parquet_path: str,
    macro_lookup_path: str,
    output_dir: str = DEFAULT_DIAGNOSTIC_DIR,
    seeds: Sequence[int] = DEFAULT_SEEDS,
    k_neighbors: int = DEFAULT_IDW_NEIGHBORS,
    n_components: int = 50,
    max_features: int = 12000,
    alpha: float = BILATERAL_ALPHA,
) -> Dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    frame = load_harmonized_parquet(harmonized_parquet_path)
    duplicate_analysis = detect_duplicate_records(frame)
    source_distribution = (
        frame.get("source_dataset", pd.Series(["unknown"] * len(frame))).astype(str).value_counts().to_dict()
    )
    seed_results = [
        _fit_and_score_seed(
            frame=frame,
            macro_lookup_path=macro_lookup_path,
            seed=int(seed),
            k_neighbors=int(k_neighbors),
            n_components=n_components,
            max_features=max_features,
            alpha=alpha,
        )
        for seed in seeds
    ]

    validation_metrics = pd.DataFrame([
        {"seed": result["seed"], **result["validation_metrics"]} for result in seed_results
    ])
    test_metrics = pd.DataFrame([
        {"seed": result["seed"], **result["test_metrics"]} for result in seed_results
    ])
    reference = seed_results[0]
    validation_partition_metrics = compute_partition_metrics(
        reference["validation_frame"], reference["validation_predictions"]
    )
    test_partition_metrics = compute_partition_metrics(
        reference["test_frame"], reference["test_predictions"]
    )
    confidence_intervals = {
        "validation": {
            metric: compute_confidence_interval(validation_metrics[metric].tolist())
            for metric in ("rmse", "mae", "median_absolute_error", "smape_percent", "r2")
        },
        "test": {
            metric: compute_confidence_interval(test_metrics[metric].tolist())
            for metric in ("rmse", "mae", "median_absolute_error", "smape_percent", "r2")
        },
    }

    validation_metrics.to_csv(output_path / "seed_validation_metrics.csv", index=False)
    test_metrics.to_csv(output_path / "seed_test_metrics.csv", index=False)
    validation_partition_metrics.to_csv(output_path / "validation_partition_metrics.csv", index=False)
    test_partition_metrics.to_csv(output_path / "test_partition_metrics.csv", index=False)
    (output_path / "duplicate_analysis.json").write_text(json.dumps(duplicate_analysis, indent=2), encoding="utf-8")
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_rows": int(len(frame)),
        "seeds": [int(seed) for seed in seeds],
        "k_neighbors": int(k_neighbors),
        "split_strategy": "stratified_by_industry_partition_70_15_15",
        "feature_fit_scope": "train_split_only",
        "grouping_keys": ["industry_partition"],
        "source_distribution": {str(key): int(value) for key, value in source_distribution.items()},
        "duplicate_analysis": duplicate_analysis,
        "confidence_intervals": confidence_intervals,
        "supported_partition_count": int(len(validation_partition_metrics)),
        "weakest_validation_partition": validation_partition_metrics.sort_values("r2").iloc[0].to_dict(),
        "output_dir": str(output_path),
    }
    (output_path / "validation_diagnostics.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    markdown = [
        "# M6.7 Leakage-Safe Validation Diagnostics",
        "",
        "- Feature fitting scope: training split only.",
        "- Split strategy: stratified 70/15/15 by industry partition.",
        f"- Seeds evaluated: `{list(seeds)}`.",
        "",
        "## Validation seed metrics",
        "",
        validation_metrics.to_string(index=False),
        "",
        "## Validation partition metrics",
        "",
        validation_partition_metrics.to_string(index=False),
        "",
        "## Test partition metrics",
        "",
        test_partition_metrics.to_string(index=False),
        "",
        "## Duplicate analysis",
        "",
        json.dumps(duplicate_analysis, indent=2),
        "",
        "## Confidence intervals",
        "",
        json.dumps(confidence_intervals, indent=2),
    ]
    (output_path / "validation_diagnostics.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    return summary


def _description_groups(frame: pd.DataFrame) -> pd.Series:
    # Mirror the model's NLP input; never group on rate or source metadata.
    return pd.Series(sanitize_many(frame["raw_description"].astype(str).tolist()), index=frame.index)


def build_description_group_splits(frame: pd.DataFrame, seed: int) -> SplitData:
    """Approximate 70/15/15 exploratory split, grouping equivalent NLP descriptions."""
    keys = _description_groups(frame)
    labels = frame.groupby(keys, sort=True)["industry_partition"].agg(lambda values: values.mode().iloc[0])
    if len(labels) < 4:
        raise ValueError("At least four distinct description groups are required for three splits.")

    def split_groups(group_labels: pd.Series, train_fraction: float) -> tuple[np.ndarray, np.ndarray]:
        train_count = math.floor(len(group_labels) * train_fraction)
        counts = group_labels.value_counts()
        stratify = (
            group_labels if counts.min() >= 2 and min(train_count, len(group_labels) - train_count) >= len(counts)
            else None
        )
        return train_test_split(
            group_labels.index.to_numpy(), train_size=train_fraction, random_state=seed, stratify=stratify,
        )

    training_groups, remaining_groups = split_groups(labels, 0.70)
    validation_groups, test_groups = split_groups(labels.loc[remaining_groups], 0.50)

    def select(groups: np.ndarray) -> pd.DataFrame:
        return frame.loc[keys.isin(groups)].sort_values("record_id").reset_index(drop=True)

    split = SplitData(select(training_groups), select(validation_groups), select(test_groups))
    if any(part.empty for part in (split.train, split.validation, split.test)):
        raise ValueError("Each description-group split needs at least one row.")
    return split


def _quantiles(values: np.ndarray) -> Dict[str, float]:
    p10, median, p90 = np.percentile(values, [10, 50, 90])
    return {"p10": round(float(p10), 6), "median": round(float(median), 6), "p90": round(float(p90), 6)}


def _segment_errors(actual: np.ndarray, predicted: np.ndarray, baseline: np.ndarray, total_squared_error: float) -> Dict[str, Any]:
    residual = predicted - actual
    absolute = np.abs(residual)
    squared = np.square(residual)
    baseline_residual = baseline - actual
    variance_sum = float(np.square(actual - actual.mean()).sum())
    r2 = None if len(actual) < 2 or np.var(actual) == 0 else round(
        1 - float(squared.sum()) / variance_sum, 6,
    )
    baseline_r2 = None if len(actual) < 2 or np.var(actual) == 0 else round(
        1 - float(np.square(baseline_residual).sum()) / variance_sum, 6,
    )
    lower, upper = POST_ARBITRAGE_RATE_BOUNDS
    return {
        "rmse_kes": round(float(np.sqrt(squared.mean())), 6),
        "mae_kes": round(float(absolute.mean()), 6),
        "r2": r2,
        "baseline_rmse_kes": round(float(np.sqrt(np.mean(np.square(baseline_residual)))), 6),
        "baseline_r2": baseline_r2,
        "squared_error_share": round(float(squared.sum() / total_squared_error), 6) if total_squared_error else 0.0,
        "high_error_rows": int((absolute > HIGH_ERROR_KES).sum()),
        "out_of_post_arbitrage_bounds_rows": int(((actual < lower) | (actual > upper)).sum()),
        "target_kes": _quantiles(actual),
        "residual_kes": _quantiles(residual),
    }


def _coverage_segments(frame: pd.DataFrame, split: SplitData, predictions: np.ndarray, baseline: np.ndarray) -> Dict[str, List[Dict[str, Any]]]:
    actual = split.validation["target_rate"].to_numpy(dtype=float)
    total_squared_error = float(np.square(predictions - actual).sum())
    dimensions = {
        "industry": ("industry_partition",),
        "source": ("source_dataset",),
        "source_industry": ("source_dataset", "industry_partition"),
    }
    tables: Dict[str, List[Dict[str, Any]]] = {}
    for table_name, columns in dimensions.items():
        rows: List[Dict[str, Any]] = []
        for group, population in frame.groupby(list(columns), sort=True, dropna=False):
            values = group if isinstance(group, tuple) else (group,)
            criteria = dict(zip(columns, values))

            def mask(part: pd.DataFrame) -> np.ndarray:
                return np.logical_and.reduce([part[column].eq(value).to_numpy() for column, value in criteria.items()])

            val_mask = mask(split.validation)
            count = int(val_mask.sum())
            rows.append({
                **{key: str(value) for key, value in criteria.items()},
                "population_rows": int(len(population)),
                "train_rows": int(mask(split.train).sum()),
                "validation_rows": count,
                "test_rows_unscored": int(mask(split.test).sum()),
                "sparse_validation": count < MIN_DIAGNOSTIC_ROWS,
                "errors": _segment_errors(actual[val_mask], predictions[val_mask], baseline[val_mask], total_squared_error)
                if count else None,
            })
        tables[table_name] = rows
    return tables


def _oot_availability(frame: pd.DataFrame) -> Dict[str, Any]:
    if OOT_TIMESTAMP_COLUMN not in frame.columns:
        return {"status": "not_run", "timestamped_rows": 0, "reason": "No source observation timestamps in this parquet; #81 OOT cannot run."}
    timestamped = 0
    for value in frame[OOT_TIMESTAMP_COLUMN].dropna():
        try:
            timestamp = pd.Timestamp(value)
            timestamped += int(not pd.isna(timestamp) and timestamp.tzinfo is not None)
        except (TypeError, ValueError):
            pass
    return {
        "status": "not_run",
        "timestamped_rows": timestamped,
        "reason": (
            f"Missing timezone-aware source observation timestamps for {len(frame) - timestamped} of {len(frame)} rows; "
            "#81 cannot evaluate the full population. Source-event provenance and a prespecified cutoff "
            "are required; this report does not run the OOT gate."
            if timestamped < len(frame) else
            "#81 requires verified source-event provenance and a prespecified cutoff; this report does not run the OOT gate."
        ),
    }


def run_industry_error_diagnostics(
    harmonized_parquet_path: str,
    macro_lookup_path: str,
    output_dir: str,
    dataset_version: str = "",
    seeds: Sequence[int] = DEFAULT_SEEDS,
    k_neighbors: int = DEFAULT_IDW_NEIGHBORS,
    n_components: int = 50,
    max_features: int = 12000,
    alpha: float = BILATERAL_ALPHA,
) -> Dict[str, Any]:
    """Report proxy-label errors without fitting on, or selecting models by, held-out rows."""
    seeds = tuple(int(seed) for seed in seeds)
    if not seeds or len(set(seeds)) != len(seeds) or k_neighbors < 1:
        raise ValueError("Provide distinct predeclared seeds and a positive neighbor count.")
    frame = load_harmonized_parquet(harmonized_parquet_path)
    if "harmonized_hourly_rate" not in frame.columns:
        raise ValueError("Industry diagnostics require post-arbitrage harmonized_hourly_rate in KES/hour.")
    frame["target_rate"] = pd.to_numeric(frame["harmonized_hourly_rate"], errors="coerce")
    if not np.isfinite(frame["target_rate"].to_numpy(dtype=float)).all():
        raise ValueError("Non-finite harmonized rates require a predeclared eligibility policy, not silent filtering.")
    frame["source_dataset"] = frame.get("source_dataset", pd.Series("unknown", index=frame.index)).fillna("unknown").astype(str)
    with open(harmonized_parquet_path, "rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    with open(macro_lookup_path, "rb") as handle:
        macro_digest = hashlib.file_digest(handle, "sha256").hexdigest()
    if dataset_version and not dataset_version.strip():
        raise ValueError("dataset_version cannot be blank.")

    results: List[Dict[str, Any]] = []
    reference_segments = None
    reference_rows = None
    for seed in seeds:
        split = build_description_group_splits(frame, seed)
        group_sets = [set(_description_groups(part)) for part in (split.train, split.validation, split.test)]
        id_sets = [set(part["record_id"]) for part in (split.train, split.validation, split.test)]
        if any(sets[i] & sets[j] for sets in (group_sets, id_sets) for i, j in ((0, 1), (0, 2), (1, 2))):
            raise AssertionError("Description groups and record IDs must not cross splits.")
        # Replaces corpus-wide frequency fields before any feature fitting, including on held-out rows.
        split = _oot_train_derived_metadata(split)
        matrices = _fit_feature_matrices(
            split, macro_lookup_path, n_components=n_components, max_features=max_features,
            alpha=alpha, save_artifacts=False,
        )
        indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=1)
        indexer.fit(
            matrices.x_train, split.train["industry_partition"].tolist(),
            record_indices=split.train["record_id"].tolist(), verified_rates=matrices.y_train.tolist(),
        )
        predictions = _predict_idw(indexer, matrices.x_validation, split.validation["industry_partition"].tolist(), k_neighbors)
        partition_means, global_mean = _build_category_mean_baseline(split.train)
        baseline = _predict_category_mean_baseline(split.validation, partition_means, global_mean)
        if len(matrices.y_validation) < 2 or np.var(matrices.y_validation) == 0:
            raise ValueError("Validation labels require at least two non-constant raw-KES observations for R2.")
        model_metrics = _metric_summary(matrices.y_validation, predictions)
        baseline_metrics = _metric_summary(matrices.y_validation, baseline)
        results.append({
            "seed": seed,
            "split_rows": {"train": len(split.train), "validation": len(split.validation), "test_unscored": len(split.test)},
            "model_validation": model_metrics,
            "baseline_validation": baseline_metrics,
        })
        if reference_segments is None:
            reference_segments = _coverage_segments(frame, split, predictions, baseline)
            reference_rows = results[-1]["split_rows"]

    group_sizes = _description_groups(frame).value_counts()
    report = {
        "evaluation_protocol": "exploratory_description_group_disjoint_random_70_15_15",
        "population": "marketplace job budgets / profile asking rates; proxy, not verified mentor transactions",
        "dataset_version": dataset_version or f"sha256:{digest}",
        "dataset_sha256": digest,
        "macro_lookup_sha256": macro_digest,
        "population_rows": len(frame),
        "duplicate_description_rows": int(group_sizes[group_sizes > 1].sum()),
        "seeds_predeclared": list(seeds),
        "reference_seed": seeds[0],
        "reference_split_rows": reference_rows,
        "k_neighbors": int(k_neighbors),
        "n_components": int(n_components),
        "max_features": int(max_features),
        "alpha": float(alpha),
        "feature_fit_scope": "train_only; saturation_and_density_recomputed_from_train_counts",
        "validation_metric_units": "raw KES/hour",
        "timestamp_cutoff_utc": None,
        "locked_test": "unscored; no model selection on test outcomes",
        "source_grouped_evaluation": "not_run; job budgets and profile asking rates are different populations",
        "oot_evaluation": _oot_availability(frame),
        "segment_policy": {
            "sparse_below_validation_rows": MIN_DIAGNOSTIC_ROWS,
            "high_error_absolute_kes_above": HIGH_ERROR_KES,
            "out_of_post_arbitrage_bounds_kes": list(POST_ARBITRAGE_RATE_BOUNDS),
            "no_holdout_dependent_exclusions": True,
        },
        "seed_metrics": results,
        "validation_seed_intervals_descriptive_not_independent": {
            name: compute_confidence_interval([result["model_validation"][name] for result in results])
            for name in ("rmse", "r2")
        },
        "reference_validation_segments": reference_segments,
    }
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "industry_error_diagnostics.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8",
    )
    return report

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate M6.7 leakage-safe validation diagnostics.")
    parser.add_argument("--mode", choices=("m6_7", "industry"), default="m6_7")
    parser.add_argument("--harmonized-parquet", required=True)
    parser.add_argument("--macro-lookup", required=True)
    parser.add_argument("--output-dir", help="Report directory (defaults vary by mode)")
    parser.add_argument("--dataset-version", default="", help="Immutable input version for industry diagnostics")
    parser.add_argument("--seeds", nargs="+", type=int, default=list(DEFAULT_SEEDS))
    parser.add_argument("--k-neighbors", type=int, default=DEFAULT_IDW_NEIGHBORS)
    parser.add_argument("--n-components", type=int, default=50)
    parser.add_argument("--max-features", type=int, default=12000)
    parser.add_argument("--alpha", type=float, default=BILATERAL_ALPHA)
    return parser.parse_args()
def main() -> None:
    args = parse_args()
    runner = run_industry_error_diagnostics if args.mode == "industry" else run_validation_diagnostics
    kwargs = dict(
        harmonized_parquet_path=args.harmonized_parquet,
        macro_lookup_path=args.macro_lookup,
        output_dir=args.output_dir or (
            os.path.join("reports", "m9_industry_error_diagnostics") if args.mode == "industry" else DEFAULT_DIAGNOSTIC_DIR
        ),
        seeds=args.seeds,
        k_neighbors=args.k_neighbors,
        n_components=args.n_components,
        max_features=args.max_features,
        alpha=args.alpha,
    )
    if args.mode == "industry":
        kwargs["dataset_version"] = args.dataset_version
    payload = runner(**kwargs)
    print(json.dumps(payload, indent=2, default=str))
if __name__ == "__main__":
    main()
