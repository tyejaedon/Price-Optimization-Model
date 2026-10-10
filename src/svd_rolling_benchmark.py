"""Retrospective #117 rolling job-budget sensitivity, never a fresh blind test."""

import argparse
import json
import os
import platform
import tempfile
import time
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import sklearn

from src.inference_safe_benchmark import _per_industry
from src.ingest_multisource import BILATERAL_ALPHA
from src.macro_arbitrage import ContinuousMetadataNormalizer
from src.nlp_pipeline import TextFeatureReducer
from src.spatial_engine import DEFAULT_IDW_EPSILON, DEFAULT_MIN_PARTITION_SIZE, DomainPartitionedKDTreeIndexer
from src.svd_dimension_benchmark import (
    PREVIOUSLY_OPENED_DATASET_SHA256, _explanations, _hash,
    _peer_stability, _profile, _vectors,
)
from src.train_pipeline import (
    DEFAULT_HARMONIZED_PARQUET, DEFAULT_IDW_NEIGHBORS, OOT_RATE_MAX, OOT_RATE_MIN,
    OOT_TIMESTAMP_COLUMN, SplitData, _metric_summary, _oot_train_derived_metadata,
    load_harmonized_parquet,
)

DEFAULT_WINDOWS = (
    ("2024-02-15T00:00:00+00:00", "2024-02-16T00:00:00+00:00"),
    ("2024-02-16T00:00:00+00:00", "2024-02-17T00:00:00+00:00"),
    ("2024-02-17T00:00:00+00:00", "2024-02-18T00:00:00+00:00"),
    ("2024-02-18T00:00:00+00:00", "2024-02-19T00:00:00+00:00"),
    ("2024-02-19T00:00:00+00:00", "2024-02-20T00:00:00+00:00"),
)
DEFAULT_REPORT_DIR = "reports/m9_svd_rolling_117"
DEFAULT_SEEDS = (42, 7)
PREVIOUSLY_OPENED_VALIDATION_START = pd.Timestamp("2024-02-20T00:00:00+00:00")


def _bounds(windows: tuple[tuple[str, str], ...], dataset_sha256: str) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    if len(windows) < 2:
        raise ValueError("At least two retrospective windows are required.")
    parsed = []
    previous_end = None
    for start, end in windows:
        first, last = pd.Timestamp(start), pd.Timestamp(end)
        if (pd.isna(first) or pd.isna(last) or first.tzinfo is None or last.tzinfo is None
                or first >= last or (previous_end is not None and first != previous_end)):
            raise ValueError("Windows must be contiguous, strictly increasing and timezone-aware.")
        first, last = first.tz_convert("UTC"), last.tz_convert("UTC")
        parsed.append((first, last))
        previous_end = last
    if dataset_sha256 == PREVIOUSLY_OPENED_DATASET_SHA256 and parsed[-1][1] > PREVIOUSLY_OPENED_VALIDATION_START:
        raise ValueError("#93 snapshot: retrospective windows must end by 2024-02-20 UTC; do not reopen validation/test.")
    return parsed


def _population(frame: pd.DataFrame, final_end: pd.Timestamp) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Apply #93's rules only to earlier dated jobs; never read future rates."""
    if not {"source_dataset", "harmonized_hourly_rate", OOT_TIMESTAMP_COLUMN}.issubset(frame.columns):
        raise ValueError("Dated jobs require source_dataset, harmonized_hourly_rate and observation time.")
    jobs = cast(pd.DataFrame, frame.loc[frame["source_dataset"].eq("upwork_jobs")].copy())
    if jobs.empty:
        raise ValueError("No upwork_jobs proxy budgets available.")
    try:
        parsed = jobs[OOT_TIMESTAMP_COLUMN].map(pd.Timestamp)
    except (ValueError, TypeError) as exc:
        raise ValueError("Job timestamps must be timezone-aware source publication times.") from exc
    if parsed.map(lambda value: pd.isna(value) or value.tzinfo is None).any():
        raise ValueError("Job timestamps must be timezone-aware source publication times.")
    jobs[OOT_TIMESTAMP_COLUMN] = pd.to_datetime(parsed, utc=True)
    jobs = cast(pd.DataFrame, jobs.loc[jobs[OOT_TIMESTAMP_COLUMN].le(final_end)].copy())
    # No target/description from #93 validation or test enters this study.
    rates = np.asarray(pd.to_numeric(jobs["harmonized_hourly_rate"], errors="coerce"), dtype=float)
    eligible = np.isfinite(rates) & (rates >= OOT_RATE_MIN) & (rates <= OOT_RATE_MAX)
    jobs = cast(pd.DataFrame, jobs.iloc[np.flatnonzero(eligible)].copy())
    jobs["target_rate"] = rates[eligible]
    jobs = jobs.sort_values([OOT_TIMESTAMP_COLUMN, "record_id"])
    descriptions = jobs["raw_description"].str.lower().str.split().str.join(" ")
    duplicates = descriptions.duplicated(keep="first")
    jobs = cast(pd.DataFrame, jobs.loc[~duplicates].reset_index(drop=True))
    return jobs, {
        "past_jobs_before_post_arbitrage_filter": int(len(rates)),
        "excluded_invalid_or_out_of_bounds": int((~eligible).sum()),
        "excluded_repeated_descriptions": int(duplicates.sum()),
        "eligible_distinct_past_jobs": len(jobs),
        "future_rows_excluded_before_rate_inspection": True,
        "rate_bounds_kes_per_hour": [OOT_RATE_MIN, OOT_RATE_MAX],
    }


def _window(jobs: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> SplitData:
    train = cast(pd.DataFrame, jobs.loc[jobs[OOT_TIMESTAMP_COLUMN].le(start)].reset_index(drop=True))
    validation = cast(pd.DataFrame, jobs.loc[
        jobs[OOT_TIMESTAMP_COLUMN].gt(start) & jobs[OOT_TIMESTAMP_COLUMN].le(end)].reset_index(drop=True))
    if len(train) < 2 or len(validation) < 2:
        raise ValueError("Each window needs at least two eligible distinct train and validation jobs.")
    if set(train["record_id"]) & set(validation["record_id"]):
        raise ValueError("Rolling train/validation IDs overlap.")
    return _oot_train_derived_metadata(SplitData(train, validation, validation))


def _validation_vectors(text: TextFeatureReducer, metadata: ContinuousMetadataNormalizer,
                        validation: pd.DataFrame, dimensions: int) -> np.ndarray:
    """Use only request-visible fields and the frozen scaler for held-out queries."""
    dense = text.transform(validation["raw_description"].tolist())
    live = np.vstack([
        metadata.transform_live_metadata(str(row.mentor_country_iso2), str(row.client_country_iso2),
                                         float(row.market_saturation_score), float(row.industry_relative_density))[0]
        for row in validation.itertuples(index=False)
    ])
    vectors = np.concatenate((dense, live), axis=1)
    if vectors.shape != (len(validation), dimensions + 3) or not np.isfinite(vectors).all():
        raise ValueError("Non-finite or mismatched request-time research coordinates.")
    return vectors


def _paired_uncertainty(
    comparisons: list[tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]], seed: int,
    repetitions: int = 2000,
) -> dict[str, Any]:
    """Descriptive paired MAE/RMSE differences; resample dates, not seeds or rows."""
    if not comparisons or repetitions < 1:
        raise ValueError("Paired comparisons and bootstrap repetitions are required.")
    by_day: dict[str, list[tuple[float, float, float, float]]] = {}
    window_deltas = []
    for truth, candidate, baseline, dates in comparisons:
        if not (len(truth) == len(candidate) == len(baseline) == len(dates)):
            raise ValueError("Paired jobs must be aligned by validation request order.")
        if not np.isfinite(np.concatenate((truth, candidate, baseline))).all():
            raise ValueError("Non-finite paired errors.")
        window_deltas.append(float(np.mean(np.abs(candidate - truth) - np.abs(baseline - truth))))
        for a, b, y, date in zip(candidate, baseline, truth, dates):
            by_day.setdefault(date, []).append((abs(a - y) - abs(b - y), (a - y) ** 2,
                                                 (b - y) ** 2, abs(b - y)))
    day_stats = [np.asarray(by_day[date], dtype=float) for date in sorted(by_day)]
    counts = np.asarray([len(group) for group in day_stats])
    mae_sums = np.asarray([group[:, 0].sum() for group in day_stats])
    candidate_sq = np.asarray([group[:, 1].sum() for group in day_stats])
    baseline_sq = np.asarray([group[:, 2].sum() for group in day_stats])
    total = int(counts.sum())
    if len(day_stats) < 2 or total < 2:
        raise ValueError("At least two independent calendar dates are required for descriptive uncertainty.")
    rng = np.random.default_rng(4107 + seed)
    sampled = rng.integers(0, len(day_stats), size=(repetitions, len(day_stats)))
    bootstrap = mae_sums[sampled].sum(axis=1) / counts[sampled].sum(axis=1)
    return {
        "matched_jobs": total, "calendar_days": len(day_stats),
        "mae_delta_vs_50d_kes": round(float(mae_sums.sum() / total), 6),
        "rmse_delta_vs_50d_kes": round(float(np.sqrt(candidate_sq.sum() / total)
                                            - np.sqrt(baseline_sq.sum() / total)), 6),
        "mae_delta_95pct_day_block_bootstrap_kes": [round(float(x), 6) for x in np.percentile(bootstrap, [2.5, 97.5])],
        "validation_windows_with_lower_mae": sum(delta < 0 for delta in window_deltas),
        "validation_windows": len(window_deltas),
        "uncertainty_scope": "descriptive only: few days, overlapping expanding training sets and reused proxy snapshot",
    }


def run_rolling_benchmark(
    parquet_path: str, macro_path: str, dataset_version: str, output_dir: str = DEFAULT_REPORT_DIR,
    windows: tuple[tuple[str, str], ...] = DEFAULT_WINDOWS,
    dimensions: tuple[int, ...] = (25, 50, 75), seeds: tuple[int, ...] = DEFAULT_SEEDS,
    samples: int = 20,
) -> dict[str, Any]:
    if (not dataset_version.strip() or samples < 1 or 50 not in dimensions or len(set(dimensions)) != len(dimensions)
            or not dimensions or any(d < 1 for d in dimensions)
            or not seeds or len(set(seeds)) != len(seeds) or any(s < 0 for s in seeds)):
        raise ValueError("Supply a dataset version, positive samples, unique dimensions including 50 and unique nonnegative seeds.")
    dataset_sha256 = _hash(parquet_path)
    bounds = _bounds(windows, dataset_sha256)
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new empty report directory for this retrospective run.")
    frame = load_harmonized_parquet(parquet_path)
    jobs, population = _population(frame, bounds[-1][1])
    splits = [_window(jobs, start, end) for start, end in bounds]
    output.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "issue": 117, "status": "retrospective_sensitivity_only_no_promotion",
        "dataset_version": dataset_version, "dataset_sha256": dataset_sha256,
        "macro_lookup_sha256": _hash(macro_path), "population": population,
        "windows_utc": [[a.isoformat(), b.isoformat()] for a, b in bounds],
        "split_rows": [{"train": len(s.train), "validation": len(s.validation)} for s in splits],
        "dimensions": list(dimensions), "seeds": list(seeds), "samples_per_window_candidate": samples,
        "fixed_settings": {"max_features": 12000, "ngram_range": [1, 2], "min_df": 1,
                           "normalize_output": False, "alpha": BILATERAL_ALPHA,
                           "k_neighbors": DEFAULT_IDW_NEIGHBORS, "epsilon": DEFAULT_IDW_EPSILON,
                           "minimum_partition_size": DEFAULT_MIN_PARTITION_SIZE, "text_weight": 1,
                           "metadata_weight": 1},
        "test_policy": "only earlier training-era dated jobs; #93 validation and final test NEVER scored here",
        "label_scope": "upwork_jobs posted budgets; not mentor payments or a fresh blind test",
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "cpu": platform.processor(), "numpy": np.__version__, "sklearn": sklearn.__version__,
                        "threads": {key: os.getenv(key) for key in
                                    ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")}},
        "results": [], "no_production_promotion": True,
    }
    (output / "protocol_frozen.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    matched: dict[tuple[int, int], list[tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]]] = {}
    for window_number, split in enumerate(splits):
        dates = split.validation[OOT_TIMESTAMP_COLUMN].dt.strftime("%Y-%m-%d").tolist()
        y = split.validation["target_rate"].to_numpy(dtype=float)
        for seed in seeds:
            results: dict[int, tuple[np.ndarray, list[dict[str, Any]]]] = {}
            rows = []
            for d in dimensions:
                row: dict[str, Any] = {"text_dimensions": d, "status": "failed"}
                rows.append(row)
                try:
                    started = time.perf_counter()
                    text = TextFeatureReducer(n_components=d, random_state=seed)
                    text.fit_transform(split.train["raw_description"].tolist())
                    row["text_fit_ms"] = round((time.perf_counter() - started) * 1000, 6)
                    if text.reducer.components_.shape[0] != d:
                        raise ValueError(f"SVD did not fit {d} text coordinates.")
                    metadata = ContinuousMetadataNormalizer(macro_path, alpha=BILATERAL_ALPHA)
                    metadata.fit(cast(list[dict[str, Any]], split.train.to_dict(orient="records")))
                    x_train = _vectors(text, metadata, split.train, d)
                    x_validation = _validation_vectors(text, metadata, split.validation, d)
                    tree = DomainPartitionedKDTreeIndexer(minimum_partition_size=DEFAULT_MIN_PARTITION_SIZE,
                                                          vector_dimensions=d + 3)
                    started = time.perf_counter()
                    tree.fit(x_train, split.train["industry_partition"].tolist(),
                             record_indices=split.train["record_id"].tolist(),
                             verified_rates=split.train["target_rate"].tolist())
                    row["tree_fit_ms"] = round((time.perf_counter() - started) * 1000, 6)
                    predictions, peers = _explanations(tree, x_validation, split.validation)
                    row["validation"] = _metric_summary(y, predictions)
                    row["validation_per_industry"] = _per_industry(split.validation, predictions)
                    row["explained_variance_sum"] = round(text.explained_variance_sum(), 6)
                    with tempfile.TemporaryDirectory(dir=output) as directory:
                        row.update(_profile(text, metadata, tree, split.validation, x_validation,
                                            Path(directory) / "research", macro_path, samples))
                    results[d] = predictions, peers
                    row["status"] = "ok"
                except (ValueError, RuntimeError, KeyError) as exc:
                    row["failure"] = f"{type(exc).__name__}: {exc}"
            if 50 not in results:
                raise ValueError(f"50D baseline failed in window {window_number}, seed {seed}.")
            reference, reference_peers = results[50]
            for row in rows:
                d = row["text_dimensions"]
                if d in results:
                    predictions, peers = results[d]
                    row["peer_stability_vs_50d"] = _peer_stability(reference_peers, peers, reference, predictions)
                    matched.setdefault((seed, d), []).append((y, predictions, reference, dates))
            report["results"].append({"window": window_number + 1, "seed": seed,
                                      "train_rows": len(split.train), "validation_rows": len(y),
                                      "validation_industries": split.validation["industry_partition"].value_counts().sort_index().to_dict(),
                                      "candidates": rows})
    report["paired_vs_50d"] = {
        str(seed): {str(d): _paired_uncertainty(matched[(seed, d)], seed)
                    for d in dimensions if (seed, d) in matched and len(matched[(seed, d)]) == len(splits)}
        for seed in seeds
    }
    (output / "benchmark.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="#117 retrospective pre-#93 SVD rolling sensitivity")
    parser.add_argument("--harmonized-parquet", default=DEFAULT_HARMONIZED_PARQUET)
    parser.add_argument("--macro-lookup", required=True)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--output-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--samples", type=int, default=20)
    args = parser.parse_args()
    result = run_rolling_benchmark(args.harmonized_parquet, args.macro_lookup,
                                   args.dataset_version, args.output_dir, samples=args.samples)
    print(json.dumps({"report": str(Path(args.output_dir) / "benchmark.json"),
                      "windows": len(result["windows_utc"]), "test_policy": result["test_policy"]}, indent=2))


if __name__ == "__main__":
    main()
