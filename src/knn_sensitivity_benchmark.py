"""Non-promoting chronological proxy-budget study of k and IDW epsilon (#121)."""

import argparse
import hashlib
import json
import platform
import shutil
import time
import tracemalloc
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import sklearn

from src.inference_safe_benchmark import _per_industry, _split_population
from src.ingest_multisource import BILATERAL_ALPHA
from src.interval_synthesizer import synthesize_corridor
from src.macro_arbitrage import ContinuousMetadataNormalizer
from src.nlp_pipeline import TextFeatureReducer, ensure_text_dimensions
from src.spatial_engine import DEFAULT_IDW_EPSILON, DEFAULT_MIN_PARTITION_SIZE, DomainPartitionedKDTreeIndexer
from src.train_pipeline import DEFAULT_HARMONIZED_PARQUET, _metric_summary, load_harmonized_parquet

BASELINE = (5, DEFAULT_IDW_EPSILON)
K_SERIES = (BASELINE, (3, DEFAULT_IDW_EPSILON), (10, DEFAULT_IDW_EPSILON))
EPSILON_SERIES = (BASELINE, (5, 1e-8), (5, 1e-4))
DEFAULT_OUTPUT = "reports/m9_knn_sensitivity_121"


def _digest(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _online_vectors(reducer: TextFeatureReducer, normalizer: ContinuousMetadataNormalizer,
                    frame: pd.DataFrame) -> np.ndarray:
    text = ensure_text_dimensions(reducer.transform(frame["raw_description"].tolist()))
    metadata = np.vstack([
        normalizer.transform_live_metadata(
            str(row.mentor_country_iso2), str(row.client_country_iso2),
            float(row.market_saturation_score), float(row.industry_relative_density),
        ).reshape(-1)
        for row in frame.itertuples(index=False)
    ])
    vectors = np.concatenate((text, metadata), axis=1)
    if vectors.shape != (len(frame), 53) or not np.isfinite(vectors).all():
        raise ValueError("Expected finite 53D request-time coordinates.")
    return vectors


def _peer_changes(reference: list[dict[str, Any]], candidate: list[dict[str, Any]]) -> dict[str, float | int]:
    if len(reference) != len(candidate) or not reference:
        raise ValueError("Comparable peer cohorts must be aligned and nonempty.")
    jaccard, common_rank, quote, dispersion, corridor, fallback = [], [], [], [], [], []
    for base, trial in zip(reference, candidate):
        base_ids = [peer["peer_index"] for peer in base["nearest_neighbors"]]
        trial_ids = [peer["peer_index"] for peer in trial["nearest_neighbors"]]
        shared = set(base_ids) & set(trial_ids)
        jaccard.append(len(shared) / len(set(base_ids) | set(trial_ids)))
        common_rank.append(sum(base_ids.index(peer) == trial_ids.index(peer) for peer in shared) / len(shared)
                           if shared else 0.0)
        quote.append(abs(base["base_predicted_rate"] - trial["base_predicted_rate"]))
        dispersion.append(abs(base["peer_stddev"] - trial["peer_stddev"]))
        corridor.append(abs(base["corridor_width"] - trial["corridor_width"]))
        fallback.append(base["fallback_triggered"] != trial["fallback_triggered"])
    return {
        "mean_peer_jaccard": round(float(np.mean(jaccard)), 6),
        "mean_shared_peer_same_rank_fraction": round(float(np.mean(common_rank)), 6),
        "mean_absolute_base_change_kes": round(float(np.mean(quote)), 6),
        "mean_absolute_peer_dispersion_change_kes": round(float(np.mean(dispersion)), 6),
        "mean_absolute_corridor_width_change_kes": round(float(np.mean(corridor)), 6),
        "fallback_mismatch_count": sum(fallback),
    }


def _predict(indexer: DomainPartitionedKDTreeIndexer, vectors: np.ndarray, frame: pd.DataFrame,
             k: int, epsilon: float) -> tuple[np.ndarray, list[dict[str, Any]]]:
    results = []
    for vector, row in zip(vectors, frame.itertuples(index=False)):
        result = indexer.predict_base_rate(vector, str(row.industry_partition), k=k, epsilon=epsilon)
        bounds = synthesize_corridor(result["base_predicted_rate"], result["peer_stddev"],
                                     float(row.bilateral_arbitrage_factor))
        result["corridor_width"] = bounds["max_quoted_rate"] - bounds["min_quoted_rate"]
        results.append(result)
    return np.asarray([row["base_predicted_rate"] for row in results], dtype=float), results


def _zero_distance_probe(candidates: tuple[tuple[int, float], ...]) -> list[dict[str, Any]]:
    vectors = np.zeros((10, 53))
    vectors[2:, 0] = np.arange(1, 9)
    index = DomainPartitionedKDTreeIndexer()
    index.fit(vectors, ["general_tech"] * len(vectors),
              verified_rates=[100, 300, 500, 600, 700, 800, 900, 1000, 1100, 1200])
    probes = []
    for k, epsilon in candidates:
        result = index.predict_base_rate(np.zeros(53), "general_tech", k=k, epsilon=epsilon)
        weights = [peer["idw_weight"] for peer in result["nearest_neighbors"]]
        zero_peers = sum(peer["distance"] == 0 for peer in result["nearest_neighbors"])
        if not np.isfinite(result["base_predicted_rate"]) or zero_peers != min(k, 2):
            raise ValueError("Exact-match IDW probe did not produce finite results and expected zero-distance peers.")
        probes.append({"k": k, "epsilon": epsilon, "synthetic_base_kes": result["base_predicted_rate"],
                       "zero_distance_peers": zero_peers, "rounded_weight_sum": round(sum(weights), 6)})
    return probes


def run_benchmark(parquet_path: str, macro_path: str, validation_cutoff: str, test_cutoff: str,
                  dataset_version: str, output_dir: str = DEFAULT_OUTPUT, samples: int = 25,
                  k_series: tuple[tuple[int, float], ...] = K_SERIES,
                  epsilon_series: tuple[tuple[int, float], ...] = EPSILON_SERIES) -> dict[str, Any]:
    if not dataset_version.strip() or samples < 1:
        raise ValueError("Provide a dataset version and positive profiling sample count.")
    if (not k_series or k_series[0] != BASELINE or BASELINE not in epsilon_series
            or len(k_series) < 2 or len(epsilon_series) < 2):
        raise ValueError("Both candidate series need the k=5, epsilon=1e-6 baseline; k-series starts with it.")
    if (len(set(k_series)) != len(k_series) or len(set(epsilon_series)) != len(epsilon_series)
            or any(k < 1 or epsilon != BASELINE[1] for k, epsilon in k_series)
            or any(k != BASELINE[0] or not np.isfinite(epsilon) or epsilon <= 0
                   for k, epsilon in epsilon_series)):
        raise ValueError("Each series must vary only its declared positive parameter.")

    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new empty report directory for each snapshot.")
    frame = load_harmonized_parquet(parquet_path)
    split, provenance = _split_population(frame, validation_cutoff, test_cutoff)
    report: dict[str, Any] = {
        "issue": 121, "status": "exploratory_proxy_only_no_promotion",
        "dataset_version": dataset_version, "dataset_sha256": _digest(parquet_path),
        "macro_lookup_sha256": _digest(macro_path), "protocol": provenance,
        "label": "posted job budgets in KES/hour, not verified paid mentor prices",
        "test_policy": "previously opened #93 calendar window; NOT rescored or used for selection",
        "fixed": {"text_dimensions": 50, "metadata_dimensions": 3, "alpha": BILATERAL_ALPHA,
                  "max_features": 12000, "ngram_range": [1, 2], "min_df": 1, "sparse_norm": "l2",
                  "post_svd_norm": False, "svd_seed": 42, "text_weight": 1.0,
                  "metadata_weight": 1.0, "idw_exponent": 2,
                  "minimum_partition_size": DEFAULT_MIN_PARTITION_SIZE,
                  "fallback_partition": "general_tech"},
        "k_series": [list(item) for item in k_series],
        "epsilon_series": [list(item) for item in epsilon_series],
        "selection": "descriptive only; no candidate promoted or chosen by proxy score",
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "cpu": platform.processor(), "numpy": np.__version__, "sklearn": sklearn.__version__},
        "results": [],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "protocol_frozen.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    tracemalloc.start()
    try:
        reducer = TextFeatureReducer(n_components=50, max_features=12000, ngram_range=(1, 2),
                                     min_df=1, random_state=42, normalize_output=False)
        start = time.perf_counter()
        train_text = ensure_text_dimensions(reducer.fit_transform(split.train["raw_description"].tolist()))
        text_fit_seconds = time.perf_counter() - start
        normalizer = ContinuousMetadataNormalizer(macro_path, alpha=BILATERAL_ALPHA)
        normalizer.fit(cast(list[dict[str, Any]], split.train.to_dict(orient="records")))
        train_metadata = normalizer.transform(cast(list[dict[str, Any]], split.train.to_dict(orient="records")))
        train_vectors = np.concatenate((train_text, train_metadata), axis=1)
        validation_vectors = _online_vectors(reducer, normalizer, split.validation)
        indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=DEFAULT_MIN_PARTITION_SIZE)
        start = time.perf_counter()
        indexer.fit(train_vectors, split.train["industry_partition"].tolist(),
                    record_indices=split.train["record_id"].tolist(),
                    verified_rates=split.train["target_rate"].tolist())
        index_fit_seconds = time.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    artifact_dir = output / "research_artifacts"
    artifact_dir.mkdir()
    reducer.save_artifacts(str(artifact_dir))
    normalizer.save_artifacts(str(artifact_dir))
    indexer.save_artifacts(str(artifact_dir))
    shutil.copyfile(macro_path, artifact_dir / "macro_lookup_table.json")
    restored_text = TextFeatureReducer.load_artifacts(str(artifact_dir))
    restored_meta = ContinuousMetadataNormalizer.load_artifacts(
        str(artifact_dir), macro_lookup_path=str(artifact_dir / "macro_lookup_table.json"))
    restored_index = DomainPartitionedKDTreeIndexer.load_artifacts(str(artifact_dir))
    report["fit"] = {"text_seconds": round(text_fit_seconds, 6), "index_seconds": round(index_fit_seconds, 6),
                     "python_allocation_peak_bytes": peak, "python_peak_is_not_rss": True,
                     "research_artifact_bytes": sum(p.stat().st_size for p in artifact_dir.iterdir()),
                     "partition_train_counts": indexer.partition_counts,
                     "label_scope": "training rows only"}

    report["zero_distance_synthetic_probe"] = _zero_distance_probe(
        tuple(dict.fromkeys((*k_series, *epsilon_series))))
    # Only validation queries are transformed or scored; test labels remain unopened by this run.
    baseline_results: list[dict[str, Any]] | None = None
    for series, candidates in (("k", k_series), ("epsilon", epsilon_series)):
        for k, epsilon in candidates:
            if series == "epsilon" and (k, epsilon) == BASELINE:
                continue
            row: dict[str, Any] = {"series": series, "k": k, "epsilon": epsilon, "status": "failed"}
            report["results"].append(row)
            predictions, results = _predict(indexer, validation_vectors, split.validation, k, epsilon)
            row["validation"] = _metric_summary(split.validation["target_rate"].to_numpy(), predictions)
            row["validation_per_industry"] = _per_industry(split.validation, predictions)
            row["fallback_count"] = sum(result["fallback_triggered"] for result in results)
            row["small_partition_count"] = sum(count < max(k, DEFAULT_MIN_PARTITION_SIZE)
                                               for count in indexer.partition_counts.values())
            if (k, epsilon) == BASELINE:
                baseline_results = results
            if baseline_results is not None:
                row["vs_k5_epsilon_1e-6"] = _peer_changes(baseline_results, results)
            else:
                row["vs_k5_epsilon_1e-6"] = None
            positions = np.linspace(0, len(split.validation) - 1,
                                    min(samples, len(split.validation)), dtype=int)
            timings, query_timings = [], []
            for position in positions:
                source = split.validation.iloc[position]
                replay_vector = _online_vectors(restored_text, restored_meta, split.validation.iloc[[position]])[0]
                if not np.allclose(replay_vector, validation_vectors[position], atol=1e-5, rtol=1e-7):
                    raise ValueError("Request coordinate changed after artifact reload.")
                expected = results[position]
                replayed = restored_index.predict_base_rate(
                    replay_vector, str(source["industry_partition"]), k=k, epsilon=epsilon)
                if (expected["base_predicted_rate"] != replayed["base_predicted_rate"]
                        or expected["routed_partition"] != replayed["routed_partition"]
                        or [n["peer_index"] for n in expected["nearest_neighbors"]]
                        != [n["peer_index"] for n in replayed["nearest_neighbors"]]):
                    raise ValueError("Peer or quote changed after research artifact reload.")
                start = time.perf_counter()
                warm_vector = _online_vectors(restored_text, restored_meta, split.validation.iloc[[position]])[0]
                query_start = time.perf_counter()
                restored_index.predict_base_rate(warm_vector, str(source["industry_partition"]), k=k,
                                                 epsilon=epsilon)
                end = time.perf_counter()
                timings.append((end - query_start) * 1000)
                query_timings.append((end - start) * 1000)
            row["reload_parity"] = True
            row["warm_search_p50_ms"] = round(float(np.median(timings)), 6)
            row["warm_search_p95_ms"] = round(float(np.percentile(timings, 95)), 6)
            row["warm_local_query_p50_ms"] = round(float(np.median(query_timings)), 6)
            row["warm_local_query_p95_ms"] = round(float(np.percentile(query_timings, 95)), 6)
            row["profile_samples"] = len(timings)
            row["status"] = "ok"
    if baseline_results is None:
        raise ValueError("The k-series baseline was not measured.")
    (output / "benchmark.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Research-only #121 k/epsilon sensitivity")
    parser.add_argument("--harmonized-parquet", default=DEFAULT_HARMONIZED_PARQUET)
    parser.add_argument("--macro-lookup", required=True)
    parser.add_argument("--validation-cutoff", required=True)
    parser.add_argument("--test-cutoff", required=True)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT)
    parser.add_argument("--samples", type=int, default=25)
    args = parser.parse_args()
    report = run_benchmark(args.harmonized_parquet, args.macro_lookup, args.validation_cutoff,
                           args.test_cutoff, args.dataset_version, args.output_dir, args.samples)
    print(json.dumps({"report": str(Path(args.output_dir) / "benchmark.json"),
                      "candidates": len(report["results"]), "status": report["status"]}))


if __name__ == "__main__":
    main()
