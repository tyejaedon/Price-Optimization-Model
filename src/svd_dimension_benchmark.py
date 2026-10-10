"""Research-only #117 dimension sweep on dated job-posting proxy budgets.

The #93 final window was already opened; results from that snapshot are
exploratory OOT comparisons, never a new blind test or serving promotion.
"""

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
from src.macro_arbitrage import ContinuousMetadataNormalizer, DEFAULT_FEATURE_NAMES
from src.nlp_pipeline import TextFeatureReducer
from src.spatial_engine import DEFAULT_IDW_EPSILON, DEFAULT_MIN_PARTITION_SIZE, DomainPartitionedKDTreeIndexer
from src.train_pipeline import (
    DEFAULT_HARMONIZED_PARQUET, DEFAULT_IDW_NEIGHBORS,
    _build_category_mean_baseline, _metric_summary, _predict_category_mean_baseline,
    load_harmonized_parquet,
)

DEFAULT_DIMENSIONS = (25, 50, 75, 100)
DEFAULT_REPORT_DIR = "reports/m9_svd_dimensions_117"
PREVIOUSLY_OPENED_DATASET_SHA256 = "da5432eec261e8b8aff66d046f276562a75d24b2106d61a9c189571e8725a5ca"


def _hash(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _vectors(reducer: TextFeatureReducer, normalizer: ContinuousMetadataNormalizer,
             frame: pd.DataFrame, dimensions: int) -> np.ndarray:
    text = reducer.transform(frame["raw_description"].tolist())
    metadata = normalizer.transform(cast(list[dict[str, Any]], frame.to_dict(orient="records")))
    vectors = np.concatenate((text, metadata), axis=1)
    if text.shape[1] != dimensions or metadata.shape[1] != 3 or vectors.shape != (len(frame), dimensions + 3):
        raise ValueError(f"Expected {dimensions}+3 research coordinates; got {vectors.shape}.")
    if not np.isfinite(vectors).all():
        raise ValueError("Non-finite research coordinates.")
    return vectors


def _explanations(indexer: DomainPartitionedKDTreeIndexer, vectors: np.ndarray,
                  frame: pd.DataFrame) -> tuple[np.ndarray, list[dict[str, Any]]]:
    predictions = []
    peers = []
    for vector, industry in zip(vectors, frame["industry_partition"]):
        result = indexer.predict_base_rate(vector, str(industry), k=DEFAULT_IDW_NEIGHBORS,
                                            epsilon=DEFAULT_IDW_EPSILON)
        predictions.append(result["base_predicted_rate"])
        peers.append({"ids": [peer["peer_index"] for peer in result["nearest_neighbors"]],
                      "weights": {peer["peer_index"]: peer["idw_weight"] for peer in result["nearest_neighbors"]},
                      "similarity": {peer["peer_index"]: peer["similarity_score"] for peer in result["nearest_neighbors"]},
                      "fallback": result["fallback_triggered"]})
    return np.asarray(predictions, dtype=float), peers


def _peer_stability(reference: list[dict[str, Any]], candidate: list[dict[str, Any]],
                    reference_predictions: np.ndarray, predictions: np.ndarray) -> dict[str, float]:
    """Aggregate matched-request peer changes; never serialize individual IDs."""
    if len(reference) != len(candidate) or len(reference) != len(predictions):
        raise ValueError("Peer cohorts must align by held-out request order.")
    overlap, rank, weights, similarity, fallback = [], [], [], [], []
    for base, trial in zip(reference, candidate):
        base_ids, trial_ids = set(base["ids"]), set(trial["ids"])
        union = base_ids | trial_ids
        overlap.append(len(base_ids & trial_ids) / len(union))
        rank.append(sum(a == b for a, b in zip(base["ids"], trial["ids"])) / max(len(base["ids"]), len(trial["ids"])))
        weights.append(sum(abs(base["weights"].get(i, 0) - trial["weights"].get(i, 0)) for i in union) / len(union))
        common = base_ids & trial_ids
        if common:
            similarity.append(sum(abs(base["similarity"][i] - trial["similarity"][i]) for i in common) / len(common))
        fallback.append(base["fallback"] != trial["fallback"])
    return {
        "requests": len(reference),
        "mean_top5_jaccard": round(float(np.mean(overlap)), 6),
        "mean_same_rank_fraction": round(float(np.mean(rank)), 6),
        "mean_absolute_idw_weight_change": round(float(np.mean(weights)), 6),
        "mean_absolute_common_peer_similarity_change": round(float(np.mean(similarity)), 6) if similarity else None,
        "mean_absolute_base_quote_change_kes": round(float(np.mean(np.abs(reference_predictions - predictions))), 6),
        "fallback_mismatch_count": sum(fallback),
        "fallback_count": sum(peer["fallback"] for peer in candidate),
    }


def _same_explanation(expected: dict[str, Any], restored: dict[str, Any]) -> bool:
    """Require the same peers/quote/routing, allowing float-roundoff at 6 decimals."""
    if (expected["routed_partition"] != restored["routed_partition"]
            or expected["fallback_triggered"] != restored["fallback_triggered"]
            or expected["base_predicted_rate"] != restored["base_predicted_rate"]):
        return False
    left, right = expected["nearest_neighbors"], restored["nearest_neighbors"]
    return len(left) == len(right) and all(
        a["peer_index"] == b["peer_index"] and a["verified_rate"] == b["verified_rate"]
        and all(abs(a[field] - b[field]) <= 2e-6
                for field in ("distance", "idw_weight", "similarity_score"))
        for a, b in zip(left, right)
    )


def _profile(reducer: TextFeatureReducer, normalizer: ContinuousMetadataNormalizer,
             indexer: DomainPartitionedKDTreeIndexer, validation: pd.DataFrame, vectors: np.ndarray,
             artifact_dir: Path, macro_path: str, samples: int) -> dict[str, Any]:
    artifact_dir.mkdir()
    reducer.save_artifacts(str(artifact_dir))
    normalizer.save_artifacts(str(artifact_dir))
    indexer.save_artifacts(str(artifact_dir))
    shutil.copyfile(macro_path, artifact_dir / "macro_lookup_table.json")
    restored_text = TextFeatureReducer.load_artifacts(str(artifact_dir))
    restored_meta = ContinuousMetadataNormalizer.load_artifacts(
        str(artifact_dir), macro_lookup_path=str(artifact_dir / "macro_lookup_table.json"))
    restored_index = DomainPartitionedKDTreeIndexer.load_artifacts(str(artifact_dir))
    indices = np.linspace(0, len(validation) - 1, min(samples, len(validation)), dtype=int)
    text_times, search_times, total_times = [], [], []
    for position in indices:
        row = validation.iloc[position]

        def replay() -> tuple[np.ndarray, dict[str, Any], float, float, float]:
            start = time.perf_counter()
            text = restored_text.transform([str(row["raw_description"])])
            text_end = time.perf_counter()
            meta = restored_meta.transform_live_metadata(
                str(row["mentor_country_iso2"]), str(row["client_country_iso2"]),
                float(row["market_saturation_score"]),
                float(validation.loc[position, "industry_relative_density"]),
            )
            vector = np.concatenate((text, meta), axis=1).reshape(-1)
            query_start = time.perf_counter()
            prediction = restored_index.predict_base_rate(vector, str(row["industry_partition"]),
                                                          k=DEFAULT_IDW_NEIGHBORS, epsilon=DEFAULT_IDW_EPSILON)
            end = time.perf_counter()
            return vector, prediction, (text_end - start) * 1000, (end - query_start) * 1000, (end - start) * 1000

        replay()  # warm the fixed held-out request before timing
        vector, prediction, text_ms, search_ms, total_ms = replay()
        expected = indexer.predict_base_rate(vectors[position], str(row["industry_partition"]),
                                             k=DEFAULT_IDW_NEIGHBORS, epsilon=DEFAULT_IDW_EPSILON)
        if vector.shape != (reducer.n_components_requested + 3,) or not np.isfinite(vector).all():
            raise ValueError("Reloaded request coordinate has wrong shape or non-finite values.")
        if not np.allclose(vector, vectors[position], atol=1e-5, rtol=1e-7):
            raise ValueError("Training/online request coordinates differ after reload.")
        if not _same_explanation(expected, prediction):
            raise ValueError("Reloaded peer explanation or prediction differs.")
        text_times.append(text_ms)
        search_times.append(search_ms)
        total_times.append(total_ms)

    return {
        "request_reload_parity": True, "profile_samples": len(indices),
        "warm_text_p50_ms": round(float(np.median(text_times)), 6),
        "warm_text_p95_ms": round(float(np.percentile(text_times, 95)), 6),
        "warm_search_p50_ms": round(float(np.median(search_times)), 6),
        "warm_search_p95_ms": round(float(np.percentile(search_times, 95)), 6),
        "warm_local_inference_p50_ms": round(float(np.median(total_times)), 6),
        "warm_local_inference_p95_ms": round(float(np.percentile(total_times, 95)), 6),
        "artifact_bytes": sum(path.stat().st_size for path in artifact_dir.iterdir() if path.is_file()),
    }


def run_benchmark(parquet_path: str, macro_path: str, validation_cutoff: str, test_cutoff: str,
                  dataset_version: str, output_dir: str = DEFAULT_REPORT_DIR,
                  dimensions: tuple[int, ...] = DEFAULT_DIMENSIONS, samples: int = 25) -> dict[str, Any]:
    if not dataset_version.strip() or samples < 1 or not dimensions or 50 not in dimensions or len(set(dimensions)) != len(dimensions) or any(d < 1 for d in dimensions):
        raise ValueError("Supply a dataset_version, positive samples and unique positive dimensions including 50.")
    frame = load_harmonized_parquet(parquet_path)
    split, provenance = _split_population(frame, validation_cutoff, test_cutoff)
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new empty report directory for each dataset/protocol.")
    output.mkdir(parents=True, exist_ok=True)
    dataset_hash = _hash(parquet_path)
    report: dict[str, Any] = {
        "issue": 117, "status": "research_only_no_promotion", "dataset_version": dataset_version,
        "dataset_sha256": dataset_hash, "macro_lookup_sha256": _hash(macro_path),
        "protocol": provenance, "dimensions_predeclared": list(dimensions),
        "test_policy": "previously opened #93 final window; exploratory OOT reuse, not a blind test" if dataset_hash == PREVIOUSLY_OPENED_DATASET_SHA256 else "exploratory chronological test; no blind-test claim",
        "fixed_settings": {"tfidf_max_features": 12000, "ngram_range": [1, 2], "min_df": 1,
                           "normalize_output": False, "svd_random_state": 42, "metadata_features": list(DEFAULT_FEATURE_NAMES),
                           "bilateral_alpha": BILATERAL_ALPHA, "k": DEFAULT_IDW_NEIGHBORS,
                           "epsilon": DEFAULT_IDW_EPSILON, "text_weight": 1.0, "metadata_weight": 1.0,
                           "minimum_partition_size": DEFAULT_MIN_PARTITION_SIZE},
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "cpu": platform.processor(), "numpy": np.__version__, "sklearn": sklearn.__version__},
        "measurement_scope": "local warmed NLP+metadata+KDTree/IDW, not authenticated API; peak Python tracemalloc allocations, not RSS",
        "label_scope": "dated upwork_jobs posted proxy budgets in KES/hour; not verified mentor prices",
        "results": [], "no_production_promotion": True,
    }
    (output / "protocol_frozen.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    means, global_mean = _build_category_mean_baseline(split.train)
    baseline_val = _predict_category_mean_baseline(split.validation, means, global_mean)
    report["category_mean"] = {
        "validation": _metric_summary(split.validation["target_rate"].to_numpy(), baseline_val),
    }
    peer_results: dict[int, tuple[np.ndarray, list[dict[str, Any]]]] = {}
    for d in dimensions:
        row: dict[str, Any] = {"text_dimensions": d, "hybrid_dimensions": d + 3, "status": "failed"}
        report["results"].append(row)
        tracemalloc.start()
        try:
            reducer = TextFeatureReducer(n_components=d, max_features=12000, ngram_range=(1, 2),
                                         min_df=1, random_state=42, normalize_output=False)
            started = time.perf_counter()
            reducer.fit_transform(split.train["raw_description"].tolist())
            row["text_fit_ms"] = round((time.perf_counter() - started) * 1000, 6)
            if reducer.reducer.n_components != d:
                raise ValueError(f"SVD fitted {reducer.reducer.n_components} rather than {d} components.")
            normalizer = ContinuousMetadataNormalizer(macro_path, alpha=BILATERAL_ALPHA)
            normalizer.fit(cast(list[dict[str, Any]], split.train.to_dict(orient="records")))
            train_vectors = _vectors(reducer, normalizer, split.train, d)
            validation_vectors = _vectors(reducer, normalizer, split.validation, d)
            indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=DEFAULT_MIN_PARTITION_SIZE,
                                                      vector_dimensions=d + 3)
            started = time.perf_counter()
            indexer.fit(train_vectors, split.train["industry_partition"].tolist(),
                        record_indices=split.train["record_id"].tolist(),
                        verified_rates=split.train["target_rate"].tolist())
            row["tree_fit_ms"] = round((time.perf_counter() - started) * 1000, 6)
            predictions, peers = _explanations(indexer, validation_vectors, split.validation)
            row["explained_variance_sum"] = round(reducer.explained_variance_sum(), 6)
            row["validation"] = _metric_summary(split.validation["target_rate"].to_numpy(), predictions)
            row["validation"]["bias_kes"] = round(float(np.mean(predictions - split.validation["target_rate"].to_numpy())), 6)
            row["validation_per_industry"] = _per_industry(split.validation, predictions)
            row.update(_profile(reducer, normalizer, indexer, split.validation, validation_vectors,
                                output / f"svd_{d}", macro_path, samples))
            row["training_python_peak_bytes"] = tracemalloc.get_traced_memory()[1]
            row["status"] = "ok"
            peer_results[d] = predictions, peers
        except (ValueError, KeyError, RuntimeError) as exc:
            row["failure"] = f"{type(exc).__name__}: {exc}"
        finally:
            tracemalloc.stop()
    if 50 not in peer_results:
        raise ValueError(f"50D baseline failed; see {output / 'protocol_frozen.json'} and candidate output.")
    base_predictions, base_peers = peer_results[50]
    for row in report["results"]:
        d = row["text_dimensions"]
        if d in peer_results:
            row["peer_stability_vs_50d"] = _peer_stability(base_peers, peer_results[d][1],
                                                           base_predictions, peer_results[d][0])
    # Freeze validation comparisons and peer stability before touching any test features.
    (output / "validation_frozen.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    baseline_test = _predict_category_mean_baseline(split.test, means, global_mean)
    report["category_mean"]["test_exploratory"] = _metric_summary(split.test["target_rate"].to_numpy(), baseline_test)
    for row in report["results"]:
        if row["status"] != "ok":
            continue
        d = row["text_dimensions"]
        artifact_dir = output / f"svd_{d}"
        reducer = TextFeatureReducer.load_artifacts(str(artifact_dir))
        normalizer = ContinuousMetadataNormalizer.load_artifacts(
            str(artifact_dir), macro_lookup_path=str(artifact_dir / "macro_lookup_table.json"))
        indexer = DomainPartitionedKDTreeIndexer.load_artifacts(str(artifact_dir))
        test_vectors = _vectors(reducer, normalizer, split.test, d)
        predictions, _ = _explanations(indexer, test_vectors, split.test)
        row["test_exploratory"] = _metric_summary(split.test["target_rate"].to_numpy(), predictions)
        row["test_exploratory"]["bias_kes"] = round(float(np.mean(predictions - split.test["target_rate"].to_numpy())), 6)
        row["test_per_industry_exploratory"] = _per_industry(split.test, predictions)
    (output / "benchmark.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="#117 non-promoting chronological proxy-budget SVD research")
    parser.add_argument("--harmonized-parquet", default=DEFAULT_HARMONIZED_PARQUET)
    parser.add_argument("--macro-lookup", required=True)
    parser.add_argument("--validation-cutoff", required=True, help="Timezone-aware UTC train/validation boundary")
    parser.add_argument("--test-cutoff", required=True, help="Timezone-aware UTC validation/test boundary")
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--output-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--samples", type=int, default=25)
    args = parser.parse_args()
    result = run_benchmark(args.harmonized_parquet, args.macro_lookup, args.validation_cutoff, args.test_cutoff,
                           args.dataset_version, args.output_dir, samples=args.samples)
    print(json.dumps({"report": str(Path(args.output_dir) / "benchmark.json"),
                      "dimensions": [row["text_dimensions"] for row in result["results"]],
                      "test_policy": result["test_policy"]}, indent=2))


if __name__ == "__main__":
    main()
