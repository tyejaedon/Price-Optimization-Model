"""Research-only #93 benchmark; never publishes serving artifacts or gates deployment."""

import argparse
import hashlib
import json
import math
import shutil
import time
import tracemalloc
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from src.ingest_multisource import BILATERAL_ALPHA
from src.macro_arbitrage import (
    DEFAULT_BUNDLED_MACRO_LOOKUP,
    DEFAULT_FEATURE_NAMES,
    DEFAULT_INFERENCE_CONFIG_ARTIFACT,
    ContinuousMetadataNormalizer,
    fuse_coordinate_batches,
    fuse_coordinates,
)
from src.nlp_pipeline import TextFeatureReducer, ensure_text_dimensions
from src.spatial_engine import DEFAULT_IDW_EPSILON, DEFAULT_MIN_PARTITION_SIZE, DomainPartitionedKDTreeIndexer
from src.train_pipeline import (
    DEFAULT_HARMONIZED_PARQUET,
    DEFAULT_IDW_NEIGHBORS,
    OOT_RATE_MAX,
    OOT_RATE_MIN,
    OOT_TIMESTAMP_COLUMN,
    SplitData,
    _build_category_mean_baseline,
    _metric_summary,
    _oot_train_derived_metadata,
    _predict_category_mean_baseline,
    _predict_idw,
    build_chronological_splits,
    load_harmonized_parquet,
)

DEFAULT_REPORT_DIR = Path("reports/m9_inference_safe_benchmark")


@dataclass(frozen=True)
class Candidate:
    name: str
    ngram_range: tuple[int, int] = (1, 2)
    normalize_output: bool = False
    text_weight: float = 1.0
    metadata_weight: float = 1.0


# No alternative changes the fixed 50 text + 3 metadata coordinate schema.
CANDIDATES = (
    Candidate("baseline_53d"),
    Candidate("unigram_53d", ngram_range=(1, 1)),
    Candidate("normalized_text_53d", normalize_output=True),
    Candidate("metadata_half_53d", metadata_weight=0.5),
)


def _split_population(frame: pd.DataFrame, validation_cutoff: str, test_cutoff: str) -> tuple[SplitData, dict[str, Any]]:
    """Use #91's job-budget population and #81's strict, aware-time policy."""
    if not {"source_dataset", "harmonized_hourly_rate"}.issubset(frame.columns):
        raise ValueError("Dated job-budget evaluation requires source_dataset and harmonized_hourly_rate.")
    first = pd.Timestamp(validation_cutoff)
    last = pd.Timestamp(test_cutoff)
    if pd.isna(first) or pd.isna(last) or first.tzinfo is None or last.tzinfo is None or first >= last:
        raise ValueError("Supply two increasing, prespecified timezone-aware cutoffs.")
    jobs = cast(pd.DataFrame, frame.loc[frame["source_dataset"].eq("upwork_jobs")].copy())
    if jobs.empty:
        raise ValueError("No dated upwork_jobs proxy-budget records are available.")
    rates = np.asarray(pd.to_numeric(jobs["harmonized_hourly_rate"].to_numpy(), errors="coerce"), dtype=float)
    eligible = np.isfinite(rates) & (rates >= OOT_RATE_MIN) & (rates <= OOT_RATE_MAX)
    jobs = cast(pd.DataFrame, jobs.iloc[np.flatnonzero(eligible)].copy())
    jobs["target_rate"] = rates[eligible]
    # The time check belongs after the predeclared rate-eligibility rule; missing
    # times on eligible jobs cannot silently turn a chronological study into random.
    earlier = build_chronological_splits(cast(pd.DataFrame, jobs), validation_cutoff)
    later = build_chronological_splits(earlier.test, test_cutoff)
    split = SplitData(earlier.train, later.train, later.test)

    # A repeated description is one source event for leakage purposes. Keep its
    # earliest occurrence; report exclusions rather than letting a copy cross a split.
    seen: set[str] = set()
    deduped = []
    removed: dict[str, int] = {}
    for name, part in (("train", split.train), ("validation", split.validation), ("test", split.test)):
        keys = part["raw_description"].str.lower().str.split().str.join(" ").tolist()
        keep = []
        for key in keys:
            keep.append(key not in seen)
            seen.add(key)
        removed[name] = int(len(part) - sum(keep))
        deduped.append(part.loc[keep].reset_index(drop=True))
    if any(len(part) < 2 for part in deduped):
        raise ValueError("Every chronological split needs at least two distinct eligible records.")
    split = _oot_train_derived_metadata(SplitData(*deduped))
    ids = [set(part["record_id"]) for part in (split.train, split.validation, split.test)]
    if any(ids[i] & ids[j] for i, j in ((0, 1), (0, 2), (1, 2))):
        raise ValueError("Chronological split IDs overlap.")
    return split, {
        "population": "dated upwork_jobs posted budgets, not verified mentor transactions",
        "input_rows": int(len(frame)),
        "excluded_other_sources": int(len(frame) - len(rates)),
        "excluded_invalid_or_out_of_bounds_post_arbitrage": int((~eligible).sum()),
        "excluded_cross_split_or_repeated_descriptions": removed,
        "rate_bounds_kes_per_hour": [OOT_RATE_MIN, OOT_RATE_MAX],
        "split_policy": "strict chronological train <= validation_cutoff < validation <= test_cutoff < test",
        "validation_cutoff_utc": first.tz_convert("UTC").isoformat(),
        "test_cutoff_utc": last.tz_convert("UTC").isoformat(),
        "train_end_utc": split.train[OOT_TIMESTAMP_COLUMN].max().isoformat(),
        "validation_start_utc": split.validation[OOT_TIMESTAMP_COLUMN].min().isoformat(),
        "validation_end_utc": split.validation[OOT_TIMESTAMP_COLUMN].max().isoformat(),
        "test_start_utc": split.test[OOT_TIMESTAMP_COLUMN].min().isoformat(),
        "split_rows": {name: len(part) for name, part in zip(("train", "validation", "test"), deduped)},
        "disjoint_record_ids": True,
        "description_groups_purged": True,
    }


def _features(reducer: TextFeatureReducer, normalizer: ContinuousMetadataNormalizer,
              frame: pd.DataFrame, candidate: Candidate) -> np.ndarray:
    text = ensure_text_dimensions(reducer.transform(frame["raw_description"].tolist()))
    metadata = normalizer.transform(cast(list[dict[str, Any]], frame.to_dict(orient="records")))
    return fuse_coordinate_batches(text * candidate.text_weight, metadata * candidate.metadata_weight)


def _per_industry(frame: pd.DataFrame, predictions: np.ndarray) -> list[dict[str, Any]]:
    rows = []
    for industry, group in frame.groupby("industry_partition", sort=True):
        positions = group.index.to_numpy(dtype=int)
        labels = group["target_rate"].to_numpy(dtype=float)
        scores = _metric_summary(labels, predictions[positions]) if len(group) >= 2 else {
            "rmse": round(float(abs(labels[0] - predictions[positions][0])), 6), "r2": None,
        }
        rows.append({"industry": industry, "rows": int(len(group)), **scores})
    return rows


def _query_coordinate(reducer: TextFeatureReducer, normalizer: ContinuousMetadataNormalizer,
                      config: dict[str, Any], row: pd.Series) -> np.ndarray:
    """Independently replay the same request fields consumed by InferenceRuntime."""
    text = ensure_text_dimensions(reducer.transform([str(row["raw_description"])]))
    meta = normalizer.transform_live_metadata(
        str(row["mentor_country_iso2"]), str(row["client_country_iso2"]),
        float(row["market_saturation_score"]), config["partition_density"][str(row["industry_partition"])],
    )
    return fuse_coordinates(text * config["text_weight"], meta * config["metadata_weight"])


def _replay_and_profile(reducer: TextFeatureReducer, normalizer: ContinuousMetadataNormalizer,
                        indexer: DomainPartitionedKDTreeIndexer, config: dict[str, Any],
                        validation: pd.DataFrame, validation_vectors: np.ndarray,
                        output: Path, macro_lookup_path: str, samples: int) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    reducer.save_artifacts(str(output))
    normalizer.save_artifacts(str(output))
    indexer.save_artifacts(str(output))
    shutil.copyfile(macro_lookup_path, output / DEFAULT_BUNDLED_MACRO_LOOKUP)
    (output / DEFAULT_INFERENCE_CONFIG_ARTIFACT).write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    restored_reducer = TextFeatureReducer.load_artifacts(str(output))
    restored_normalizer = ContinuousMetadataNormalizer.load_artifacts(
        str(output), macro_lookup_path=str(output / DEFAULT_BUNDLED_MACRO_LOOKUP),
    )
    restored_indexer = DomainPartitionedKDTreeIndexer.load_artifacts(str(output))
    restored_config = json.loads((output / DEFAULT_INFERENCE_CONFIG_ARTIFACT).read_text(encoding="utf-8"))
    if restored_config != config:
        raise ValueError("Query-time configuration changed on reload.")
    # Validation samples (never the final test) check request coordinates and
    # IDW predictions after reload using the actual online request fields.
    warmups = min(samples, len(validation))
    coordinate_parity = True
    replay_parity = True
    for index in range(warmups):
        row = validation.iloc[index]
        vector = _query_coordinate(restored_reducer, restored_normalizer, restored_config, row)
        coordinate_parity &= bool(np.allclose(vector, validation_vectors[index], atol=1e-5, rtol=1e-7))
        expected = indexer.predict_base_rate(validation_vectors[index], str(row["industry_partition"]),
                                             k=DEFAULT_IDW_NEIGHBORS, epsilon=DEFAULT_IDW_EPSILON)
        replayed = restored_indexer.predict_base_rate(vector, str(row["industry_partition"]),
                                                       k=DEFAULT_IDW_NEIGHBORS, epsilon=DEFAULT_IDW_EPSILON)
        replay_parity &= bool(expected["base_predicted_rate"] == replayed["base_predicted_rate"]
                              and [n["peer_index"] for n in expected["nearest_neighbors"]]
                              == [n["peer_index"] for n in replayed["nearest_neighbors"]])
    timings = []
    for index in range(warmups):
        sample = validation.iloc[index]
        start = time.perf_counter()
        query = _query_coordinate(restored_reducer, restored_normalizer, restored_config, sample)
        restored_indexer.predict_base_rate(query, str(sample["industry_partition"]),
                                          k=DEFAULT_IDW_NEIGHBORS, epsilon=DEFAULT_IDW_EPSILON)
        timings.append((time.perf_counter() - start) * 1000)
    return {
        "request_coordinate_parity": coordinate_parity,
        "reload_prediction_parity": bool(coordinate_parity and replay_parity),
        "request_parity_samples": warmups,
        "warmed_query_p95_ms": round(float(np.percentile(timings, 95)), 6),
        "warmed_query_samples": len(timings),
        "artifact_bytes": sum(path.stat().st_size for path in output.iterdir() if path.is_file()),
        "research_artifacts": "report subdirectory only; no production manifest or promotion",
    }


def run_benchmark(parquet_path: str, macro_lookup_path: str, validation_cutoff: str, test_cutoff: str,
                  dataset_version: str, output_dir: str = str(DEFAULT_REPORT_DIR),
                  candidates: tuple[Candidate, ...] = CANDIDATES, samples: int = 25) -> dict[str, Any]:
    if not dataset_version.strip():
        raise ValueError("Supply an immutable dataset_version before benchmarking.")
    if samples < 1 or not candidates or candidates[0] != Candidate("baseline_53d"):
        raise ValueError("A 53D baseline and positive profiling sample count are required.")
    if len({candidate.name for candidate in candidates}) != len(candidates):
        raise ValueError("Candidate names must be unique.")
    if any(not candidate.name.isidentifier() or not all(math.isfinite(weight) and weight > 0 for weight in
           (candidate.text_weight, candidate.metadata_weight)) for candidate in candidates):
        raise ValueError("Candidate names and block weights must be safe, finite and positive.")
    frame = load_harmonized_parquet(parquet_path)
    split, provenance = _split_population(frame, validation_cutoff, test_cutoff)
    with open(parquet_path, "rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new empty report directory to avoid mixing benchmark snapshots.")
    output.mkdir(parents=True, exist_ok=True)
    means, global_mean = _build_category_mean_baseline(split.train)
    baseline_validation = _predict_category_mean_baseline(split.validation, means, global_mean)
    rows: list[dict[str, Any]] = [{
        "name": "category_mean", "validation": _metric_summary(split.validation["target_rate"].to_numpy(), baseline_validation),
        "validation_per_industry": _per_industry(split.validation, baseline_validation),
        "promotion_status": "comparator_only",
    }]
    # The test frame and its outcomes are not passed to any candidate, transform,
    # selection rule or profiler until ALL validation scores have been frozen.
    for candidate in candidates:
        directory = output / candidate.name
        tracemalloc.start()
        try:
            reducer = TextFeatureReducer(n_components=50, max_features=12000,
                                         ngram_range=candidate.ngram_range, normalize_output=candidate.normalize_output)
            reducer.fit_transform(split.train["raw_description"].tolist())
            normalizer = ContinuousMetadataNormalizer(macro_lookup_path, alpha=BILATERAL_ALPHA)
            normalizer.fit(cast(list[dict[str, Any]], split.train.to_dict(orient="records")))
            train_vectors = _features(reducer, normalizer, split.train, candidate)
            validation_vectors = _features(reducer, normalizer, split.validation, candidate)
            indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=DEFAULT_MIN_PARTITION_SIZE)
            indexer.fit(train_vectors, split.train["industry_partition"].tolist(),
                        record_indices=split.train["record_id"].tolist(),
                        verified_rates=split.train["target_rate"].tolist())
            predictions = _predict_idw(indexer, validation_vectors, split.validation["industry_partition"].tolist(),
                                       DEFAULT_IDW_NEIGHBORS)
            config = {
                "version": 1, "text_dimensions": 50, "metadata_features": list(DEFAULT_FEATURE_NAMES),
                "k_neighbors": DEFAULT_IDW_NEIGHBORS, "idw_epsilon": DEFAULT_IDW_EPSILON,
                "text_weight": candidate.text_weight, "metadata_weight": candidate.metadata_weight,
                "minimum_partition_size": indexer.minimum_partition_size,
                "fallback_partition": indexer.fallback_partition, "allow_fallback": True,
                "partition_density": {str(key): float(group.median()) for key, group in
                                      split.train.groupby("industry_partition")["industry_relative_density"]},
            }
            replay = _replay_and_profile(reducer, normalizer, indexer, config, split.validation,
                                         validation_vectors, directory, macro_lookup_path, samples)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        rows.append({
            "name": candidate.name,
            "settings": {"ngram_range": list(candidate.ngram_range), "normalize_output": candidate.normalize_output,
                         "max_features": 12000, "min_df": 1, "requested_text_dimensions": 50,
                         "fitted_text_dimensions": int(reducer.reducer.n_components),
                         "text_weight": candidate.text_weight, "metadata_weight": candidate.metadata_weight,
                         "k_neighbors": DEFAULT_IDW_NEIGHBORS, "idw_epsilon": DEFAULT_IDW_EPSILON},
            "validation": _metric_summary(split.validation["target_rate"].to_numpy(), predictions),
            "validation_per_industry": _per_industry(split.validation, predictions),
            "training_python_peak_bytes": peak,
            **replay,
            "promotion_status": "research_only_not_promoted",
        })

    eligible_rows = [row for row in rows[1:] if row["reload_prediction_parity"]]
    if not eligible_rows:
        raise ValueError("No candidate replayed its request coordinate and prediction after reload.")
    # Selection depends only on validation in raw KES/hour; ties prefer lower
    # error and then the prespecified candidate order (baseline first).
    selected = max(eligible_rows, key=lambda row: (row["validation"]["r2"],
                    -row["validation"]["rmse"], -next(i for i, c in enumerate(candidates) if c.name == row["name"])))
    for row in rows[1:]:
        row["validation_vs_53d_baseline"] = {
            "delta_r2": round(row["validation"]["r2"] - rows[1]["validation"]["r2"], 6),
            "delta_rmse_kes": round(row["validation"]["rmse"] - rows[1]["validation"]["rmse"], 6),
        }
        row["outcome"] = ("selected_for_research_test" if row is selected else
                          "rejected_by_validation_or_replay; not promoted")
    (output / "selection_frozen.json").write_text(json.dumps({
        "selected": selected["name"], "criterion": "validation raw-KES R2; RMSE tie-break; candidate order",
        "dataset_sha256": digest,
    }, indent=2), encoding="utf-8")

    # Only after selection is frozen, evaluate the baseline and the selected
    # candidate on the final untouched test. Never select again by test score.
    for row in (rows[1], selected):
        if "test" in row:
            continue
        candidate = next(c for c in candidates if c.name == row["name"])
        directory = output / candidate.name
        reducer = TextFeatureReducer.load_artifacts(str(directory))
        normalizer = ContinuousMetadataNormalizer.load_artifacts(
            str(directory), macro_lookup_path=str(directory / DEFAULT_BUNDLED_MACRO_LOOKUP))
        indexer = DomainPartitionedKDTreeIndexer.load_artifacts(str(directory))
        vectors = _features(reducer, normalizer, split.test, candidate)
        predictions = _predict_idw(indexer, vectors, split.test["industry_partition"].tolist(), DEFAULT_IDW_NEIGHBORS)
        row["test"] = _metric_summary(split.test["target_rate"].to_numpy(), predictions)
        row["test_per_industry"] = _per_industry(split.test, predictions)
    baseline_test = _predict_category_mean_baseline(split.test, means, global_mean)
    rows[0]["test"] = _metric_summary(split.test["target_rate"].to_numpy(), baseline_test)
    rows[0]["test_per_industry"] = _per_industry(split.test, baseline_test)

    payload = {
        "issue": 93, "status": "research_only_no_promotion", "dataset_version": dataset_version,
        "dataset_sha256": digest, "macro_lookup_sha256": hashlib.sha256(Path(macro_lookup_path).read_bytes()).hexdigest(),
        "protocol": provenance, "feature_fit_scope": "training rows only; fixed 50D text plus three scaled metadata",
        "label_units": "raw proxy KES/hour; NOT verified mentor transaction prices",
        "final_test_policy": "selection_frozen.json written before test transforms and outcomes are evaluated",
        "selected_by_validation": selected["name"], "results": rows,
        "quality_gate": "not evaluated: #81 empirical mentor-pricing gate is deferred; proxy scores are not approval",
        "latency_scope": "warmed local NLP + metadata + IDW only; not full authenticated API (#70)",
        "memory_scope": "tracemalloc peak Python allocations during candidate fit, not process RSS",
    }
    (output / "benchmark.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="#93 non-promoting chronological 53D ablations")
    parser.add_argument("--harmonized-parquet", default=DEFAULT_HARMONIZED_PARQUET)
    parser.add_argument("--macro-lookup", required=True)
    parser.add_argument("--validation-cutoff", required=True, help="Prespecified train/validation boundary with timezone")
    parser.add_argument("--test-cutoff", required=True, help="Prespecified validation/test boundary with timezone")
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--output-dir", default=str(DEFAULT_REPORT_DIR))
    parser.add_argument("--samples", type=int, default=25)
    args = parser.parse_args()
    report = run_benchmark(args.harmonized_parquet, args.macro_lookup, args.validation_cutoff, args.test_cutoff,
                           args.dataset_version, args.output_dir, samples=args.samples)
    print(json.dumps({"report": str(Path(args.output_dir) / "benchmark.json"),
                      "selected_by_validation": report["selected_by_validation"],
                      "protocol": report["protocol"]["split_policy"]}, indent=2))


if __name__ == "__main__":
    main()
