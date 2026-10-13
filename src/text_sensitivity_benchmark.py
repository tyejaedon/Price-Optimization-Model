"""#120 validation-only, fixed-53D text sensitivity on dated proxy budgets."""

import argparse
import hashlib
import json
import platform
import time
import tracemalloc
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import sklearn

from src.inference_safe_benchmark import _per_industry, _split_population
from src.ingest_multisource import BILATERAL_ALPHA
from src.macro_arbitrage import ContinuousMetadataNormalizer, DEFAULT_FEATURE_NAMES
from src.nlp_pipeline import TextFeatureReducer, sanitize_many
from src.spatial_engine import DEFAULT_IDW_EPSILON, DEFAULT_MIN_PARTITION_SIZE, DomainPartitionedKDTreeIndexer
from src.svd_dimension_benchmark import _explanations, _peer_stability, _profile, _vectors
from src.train_pipeline import DEFAULT_HARMONIZED_PARQUET, DEFAULT_IDW_NEIGHBORS, _metric_summary, load_harmonized_parquet

DEFAULT_REPORT_DIR = "reports/m9_text_sensitivity_120"
TEXT_DIMENSIONS = 50


@dataclass(frozen=True)
class Candidate:
    name: str
    tfidf_norm: str = "l2"
    normalize_output: bool = False


# Only these three single-variable comparisons are predeclared; no grid search.
CANDIDATES = (
    Candidate("baseline_l2_raw"),
    Candidate("sparse_l1", tfidf_norm="l1"),
    Candidate("post_svd_unit", normalize_output=True),
)


def _hash(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _text_diagnostics(reducer: TextFeatureReducer, frame: pd.DataFrame) -> dict[str, Any]:
    cleaned = sanitize_many(frame["raw_description"].tolist())
    sparse = reducer.vectorizer.transform(cleaned)
    dense = reducer.reducer.transform(sparse)
    vocabulary = reducer.vectorizer.vocabulary_
    analyzer = reducer.vectorizer.build_analyzer()
    tokens = sum(len(analyzer(text)) for text in cleaned)
    oov = sum(sum(token not in vocabulary for token in analyzer(text)) for text in cleaned)
    return {
        "rows": len(frame), "analyzed_ngrams": tokens, "oov_ngrams": oov,
        "oov_ngram_fraction": round(oov / tokens, 6) if tokens else None,
        "zero_tfidf_rows": int(np.count_nonzero(np.diff(sparse.indptr) == 0)),
        "zero_svd_rows": int(np.count_nonzero(np.linalg.norm(dense, axis=1) == 0)),
    }


def run_benchmark(parquet_path: str, macro_path: str, validation_cutoff: str, test_cutoff: str,
                  dataset_version: str, expected_parquet_sha256: str, expected_macro_sha256: str,
                  output_dir: str = DEFAULT_REPORT_DIR, samples: int = 25) -> dict[str, Any]:
    if not dataset_version.strip() or samples < 1:
        raise ValueError("Supply a dataset_version and positive profiling sample count.")
    if any(len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest.lower())
           for digest in (expected_parquet_sha256, expected_macro_sha256)):
        raise ValueError("Freeze both input SHA-256 digests before evaluating outcomes.")
    parquet_hash, macro_hash = _hash(parquet_path), _hash(macro_path)
    if (parquet_hash.lower(), macro_hash.lower()) != (expected_parquet_sha256.lower(), expected_macro_sha256.lower()):
        raise ValueError("Input SHA-256 does not match the predeclared dataset/macro snapshot.")

    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new empty report directory for each frozen protocol.")
    split, provenance = _split_population(load_harmonized_parquet(parquet_path), validation_cutoff, test_cutoff)
    output.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "issue": 120, "status": "research_only_no_promotion",
        "dataset_version": dataset_version, "dataset_sha256": parquet_hash,
        "macro_lookup_sha256": macro_hash, "protocol": provenance,
        "test_policy": "validation only; #93 final window previously opened; no final-test features or outcomes evaluated",
        "label_scope": "dated upwork_jobs posted proxy budgets in raw KES/hour, not verified mentor prices",
        "candidates_predeclared": [asdict(candidate) for candidate in CANDIDATES],
        "fixed_settings": {
            "text_dimensions": TEXT_DIMENSIONS, "hybrid_dimensions": 53, "max_features": 12000,
            "min_df": 1, "ngram_range": [1, 2], "sublinear_tf": True, "svd_random_state": 42,
            "metadata_features": list(DEFAULT_FEATURE_NAMES), "bilateral_alpha": BILATERAL_ALPHA,
            "text_weight": 1.0, "metadata_weight": 1.0, "k": DEFAULT_IDW_NEIGHBORS,
            "epsilon": DEFAULT_IDW_EPSILON, "minimum_partition_size": DEFAULT_MIN_PARTITION_SIZE,
        },
        "decision_rule": "descriptive validation MAE/RMSE/R2, peer/operational trade-offs; no automatic promotion or winner",
        "environment": {
            "python": platform.python_version(), "platform": platform.platform(), "processor": platform.processor(),
            "numpy": np.__version__, "pandas": pd.__version__, "sklearn": sklearn.__version__,
        },
        "measurement_scope": "train fit and validation-only warmed local text/index/IDW; tracemalloc peak Python allocations, not RSS or HTTP",
        "results": [], "no_production_promotion": True,
    }
    (output / "protocol_frozen.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    peer_results: dict[str, tuple[np.ndarray, list[dict[str, Any]]]] = {}
    for candidate in CANDIDATES:
        row: dict[str, Any] = {"name": candidate.name, "settings": asdict(candidate), "status": "failed"}
        report["results"].append(row)
        tracemalloc.start()
        try:
            reducer = TextFeatureReducer(n_components=TEXT_DIMENSIONS, max_features=12000,
                                         ngram_range=(1, 2), min_df=1, random_state=42,
                                         normalize_output=candidate.normalize_output,
                                         tfidf_norm=candidate.tfidf_norm)
            started = time.perf_counter()
            reducer.fit_transform(split.train["raw_description"].tolist())
            row["text_fit_ms"] = round((time.perf_counter() - started) * 1000, 6)
            if reducer.reducer.n_components != TEXT_DIMENSIONS:
                raise ValueError("Training vocabulary cannot support exactly 50 SVD coordinates.")
            row["vocabulary_size"] = len(reducer.vectorizer.vocabulary_)
            row["explained_variance_sum"] = round(reducer.explained_variance_sum(), 6)
            row["train_text"] = _text_diagnostics(reducer, split.train)
            row["validation_text"] = _text_diagnostics(reducer, split.validation)
            normalizer = ContinuousMetadataNormalizer(macro_path, alpha=BILATERAL_ALPHA)
            normalizer.fit(cast(list[dict[str, Any]], split.train.to_dict(orient="records")))
            train_vectors = _vectors(reducer, normalizer, split.train, TEXT_DIMENSIONS)
            started = time.perf_counter()
            validation_vectors = _vectors(reducer, normalizer, split.validation, TEXT_DIMENSIONS)
            row["validation_batch_transform_ms"] = round((time.perf_counter() - started) * 1000, 6)
            indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=DEFAULT_MIN_PARTITION_SIZE,
                                                      vector_dimensions=53)
            started = time.perf_counter()
            indexer.fit(train_vectors, split.train["industry_partition"].tolist(),
                        record_indices=split.train["record_id"].tolist(),
                        verified_rates=split.train["target_rate"].tolist())
            row["tree_fit_ms"] = round((time.perf_counter() - started) * 1000, 6)
            predictions, peers = _explanations(indexer, validation_vectors, split.validation)
            labels = split.validation["target_rate"].to_numpy(dtype=float)
            row["validation"] = _metric_summary(labels, predictions)
            row["validation"]["bias_kes"] = round(float(np.mean(predictions - labels)), 6)
            row["validation_per_industry"] = _per_industry(split.validation, predictions)
            row["train_industry_counts"] = {str(key): int(value) for key, value in
                                            split.train["industry_partition"].value_counts(sort=False).sort_index().items()}
            row.update(_profile(reducer, normalizer, indexer, split.validation, validation_vectors,
                                output / candidate.name, macro_path, samples))
            if not row["request_reload_parity"]:
                raise ValueError("Request reload parity failed.")
            row["status"] = "ok"
            peer_results[candidate.name] = predictions, peers
        except Exception as exc:
            row["failure"] = f"{type(exc).__name__}: {exc}"
        finally:
            row["training_python_peak_bytes"] = tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()
            (output / "benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    baseline = peer_results.get(CANDIDATES[0].name)
    if baseline is None:
        raise ValueError(f"Baseline failed; inspect {output / 'benchmark.json'}.")
    for row in report["results"]:
        if row["name"] in peer_results:
            prediction, peers = peer_results[row["name"]]
            row["peer_stability_vs_baseline"] = _peer_stability(baseline[1], peers, baseline[0], prediction)
    (output / "benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="#120 validation-only 53D proxy text sensitivity; no serving output")
    parser.add_argument("--harmonized-parquet", default=DEFAULT_HARMONIZED_PARQUET)
    parser.add_argument("--macro-lookup", required=True)
    parser.add_argument("--validation-cutoff", required=True, help="Timezone-aware train/validation UTC boundary")
    parser.add_argument("--test-cutoff", required=True, help="Previously opened final-window boundary; never scored")
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--expected-parquet-sha256", required=True)
    parser.add_argument("--expected-macro-sha256", required=True)
    parser.add_argument("--output-dir", default=DEFAULT_REPORT_DIR)
    parser.add_argument("--samples", type=int, default=25)
    args = parser.parse_args()
    result = run_benchmark(args.harmonized_parquet, args.macro_lookup, args.validation_cutoff, args.test_cutoff,
                           args.dataset_version, args.expected_parquet_sha256, args.expected_macro_sha256,
                           args.output_dir, args.samples)
    print(json.dumps({"report": str(Path(args.output_dir) / "benchmark.json"),
                      "statuses": {row["name"]: row["status"] for row in result["results"]},
                      "test_policy": result["test_policy"]}, indent=2))


if __name__ == "__main__":
    main()
