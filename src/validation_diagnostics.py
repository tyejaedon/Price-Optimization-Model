import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

try:
    import numpy as np
    import pandas as pd
except ImportError as exc:
    raise RuntimeError("Install project dependencies from requirements.txt") from exc

from src.ingest_multisource import BILATERAL_ALPHA
from src.spatial_engine import DomainPartitionedKDTreeIndexer
from src.train_pipeline import (
    DEFAULT_HARMONIZED_PARQUET,
    DEFAULT_IDW_NEIGHBORS,
    DEFAULT_RANDOM_STATE,
    _fit_feature_matrices,
    _metric_summary,
    _predict_idw,
    build_stratified_splits,
    load_harmonized_parquet,
)

DEFAULT_DIAGNOSTIC_DIR = os.path.join("reports", "m6_7_validation_diagnostics")
DEFAULT_SEEDS = (42, 43, 44)


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

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate M6.7 leakage-safe validation diagnostics.")
    parser.add_argument("--harmonized-parquet", required=True)
    parser.add_argument("--macro-lookup", required=True)
    parser.add_argument("--output-dir", default=DEFAULT_DIAGNOSTIC_DIR)
    parser.add_argument("--seeds", nargs="+", type=int, default=list(DEFAULT_SEEDS))
    parser.add_argument("--k-neighbors", type=int, default=DEFAULT_IDW_NEIGHBORS)
    parser.add_argument("--n-components", type=int, default=50)
    parser.add_argument("--max-features", type=int, default=12000)
    parser.add_argument("--alpha", type=float, default=BILATERAL_ALPHA)
    return parser.parse_args()
def main() -> None:
    args = parse_args()
    payload = run_validation_diagnostics(
        harmonized_parquet_path=args.harmonized_parquet,
        macro_lookup_path=args.macro_lookup,
        output_dir=args.output_dir,
        seeds=args.seeds,
        k_neighbors=args.k_neighbors,
        n_components=args.n_components,
        max_features=args.max_features,
        alpha=args.alpha,
    )
    print(json.dumps(payload, indent=2, default=str))
if __name__ == "__main__":
    main()
