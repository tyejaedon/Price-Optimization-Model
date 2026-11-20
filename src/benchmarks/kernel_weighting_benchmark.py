"""Non-promoting validation benchmark for M16.3 distance weighting kernels.

Evaluates IDW power-p (p in {1, 2, 3, 4}), Exponential decay, and Gaussian RBF
(fixed and adaptive median bandwidth) on the chronological validation split
without touching the test split or mutating production artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, cast

import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import mean_absolute_error, median_absolute_error, r2_score, root_mean_squared_error

from src.benchmarks.inference_safe_benchmark import _split_population
from src.benchmarks.knn_sensitivity_benchmark import _online_vectors
from src.data.ingest_multisource import BILATERAL_ALPHA
from src.engine.interval_synthesizer import synthesize_corridor, weighted_peer_stddev
from src.engine.macro_arbitrage import ContinuousMetadataNormalizer
from src.engine.spatial_engine import (
    DEFAULT_IDW_EPSILON,
    DEFAULT_MIN_PARTITION_SIZE,
    DEFAULT_QUERY_NEIGHBORS,
    DomainPartitionedKDTreeIndexer,
)
from src.nlp.nlp_pipeline import TextFeatureReducer, ensure_text_dimensions
from src.training.train_pipeline import DEFAULT_HARMONIZED_PARQUET, load_harmonized_parquet

DEFAULT_OUTPUT = "reports/m16_kernel_tuning"
DENSE_PARTITIONS = ("design_creative", "web_backend")
SPARSE_PARTITIONS = ("product_management", "devops_cloud")


@dataclass(frozen=True)
class KernelSpec:
    """Configuration for a candidate peer-distance weighting kernel."""

    name: str
    kernel: str
    power: Optional[float] = None
    gamma: float = 1.0
    sigma: Optional[float] = None
    description: str = ""


DEFAULT_KERNEL_SPECS: Tuple[KernelSpec, ...] = (
    KernelSpec("idw_linear", "idw_linear", power=1.0, description="Linear IDW (p=1)"),
    KernelSpec("idw_quadratic", "idw_quadratic", power=2.0, description="Quadratic IDW baseline (p=2)"),
    KernelSpec("idw_cubic", "idw_cubic", power=3.0, description="Cubic IDW (p=3)"),
    KernelSpec("idw_quartic", "idw_quartic", power=4.0, description="Quartic IDW (p=4)"),
    KernelSpec("exp_gamma_0.5", "exponential", gamma=0.5, description="Exponential decay (gamma=0.5)"),
    KernelSpec("exp_gamma_1.0", "exponential", gamma=1.0, description="Exponential decay (gamma=1.0)"),
    KernelSpec("exp_gamma_2.0", "exponential", gamma=2.0, description="Exponential decay (gamma=2.0)"),
    KernelSpec("rbf_adaptive_median", "gaussian_rbf", sigma=None, description="Gaussian RBF (adaptive median sigma)"),
    KernelSpec("rbf_sigma_0.5", "gaussian_rbf", sigma=0.5, description="Gaussian RBF (fixed sigma=0.5)"),
    KernelSpec("rbf_sigma_1.0", "gaussian_rbf", sigma=1.0, description="Gaussian RBF (fixed sigma=1.0)"),
    KernelSpec("rbf_sigma_2.0", "gaussian_rbf", sigma=2.0, description="Gaussian RBF (fixed sigma=2.0)"),
)


def _digest(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def compute_weight_distribution_stats(weights: Sequence[float]) -> Dict[str, float]:
    """Compute Shannon entropy, normalized entropy, max weight, and N_eff."""
    w = np.asarray(weights, dtype=float).reshape(-1)
    if w.size == 0:
        raise ValueError("weights cannot be empty.")
    positive = w[w > 0.0]
    entropy = float(-np.sum(positive * np.log(positive)))
    norm_entropy = float(entropy / math.log(w.size)) if w.size > 1 else 1.0
    max_weight = float(np.max(w))
    hhi = float(np.sum(np.square(w)))
    effective_neighbors = float(1.0 / hhi) if hhi > 0.0 else float(w.size)
    return {
        "entropy": entropy,
        "normalized_entropy": norm_entropy,
        "max_weight": max_weight,
        "effective_neighbors": effective_neighbors,
    }


def run_edge_stability_probes(
    specs: Sequence[KernelSpec] = DEFAULT_KERNEL_SPECS,
    epsilon: float = DEFAULT_IDW_EPSILON,
) -> List[Dict[str, Any]]:
    """Verify numerical stability across extreme distance edge conditions."""
    probes = {
        "all_zeros": [0.0, 0.0, 0.0, 0.0, 0.0],
        "duplicate_exact_match": [0.0, 0.0, 1.0, 2.0, 3.0],
        "distant_outliers": [100.0, 500.0, 1000.0, 5000.0, 10000.0],
        "extreme_mixed_scale": [0.0, 1e-12, 1.0, 1e3, 1e4],
    }
    records: List[Dict[str, Any]] = []
    for spec in specs:
        for probe_name, distances in probes.items():
            weights = DomainPartitionedKDTreeIndexer.compute_distance_weights(
                distances,
                kernel=spec.kernel,
                power=spec.power,
                epsilon=epsilon,
                gamma=spec.gamma,
                sigma=spec.sigma,
            )
            finite = bool(np.all(np.isfinite(weights)))
            non_negative = bool(np.all(weights >= 0.0))
            weight_sum = float(np.sum(weights))
            if not (finite and non_negative and abs(weight_sum - 1.0) <= 1e-9):
                raise ValueError(f"Numerical stability probe failed for {spec.name} on {probe_name}.")
            records.append(
                {
                    "kernel": spec.name,
                    "probe": probe_name,
                    "finite": finite,
                    "non_negative": non_negative,
                    "weight_sum": round(weight_sum, 9),
                    "max_weight": round(float(np.max(weights)), 6),
                    "min_weight": round(float(np.min(weights)), 6),
                }
            )
    return records


def _regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    return {
        "count": int(len(y_true)),
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 4),
        "rmse": round(float(root_mean_squared_error(y_true, y_pred)), 4),
        "r2": round(float(r2_score(y_true, y_pred)), 6),
        "median_ae": round(float(median_absolute_error(y_true, y_pred)), 4),
        "mean_bias": round(float(np.mean(y_pred - y_true)), 4),
    }


def _summarize_partition_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not records:
        return {"count": 0}
    entropies = [r["entropy"] for r in records]
    norm_entropies = [r["normalized_entropy"] for r in records]
    max_weights = [r["max_weight"] for r in records]
    eff_k = [r["effective_neighbors"] for r in records]
    stddevs = [r["peer_stddev"] for r in records]
    widths = [r["corridor_width"] for r in records]
    return {
        "count": len(records),
        "mean_entropy": round(float(np.mean(entropies)), 6),
        "mean_normalized_entropy": round(float(np.mean(norm_entropies)), 6),
        "mean_max_weight": round(float(np.mean(max_weights)), 6),
        "p95_max_weight": round(float(np.percentile(max_weights, 95)), 6),
        "mean_effective_neighbors": round(float(np.mean(eff_k)), 4),
        "mean_peer_stddev": round(float(np.mean(stddevs)), 4),
        "median_peer_stddev": round(float(np.median(stddevs)), 4),
        "mean_corridor_width": round(float(np.mean(widths)), 4),
        "median_corridor_width": round(float(np.median(widths)), 4),
        "p95_corridor_width": round(float(np.percentile(widths, 95)), 4),
        "std_corridor_width": round(float(np.std(widths)), 4),
    }


def run_benchmark(
    parquet_path: str,
    macro_path: str,
    validation_cutoff: str,
    test_cutoff: str,
    dataset_version: str,
    output_dir: str = DEFAULT_OUTPUT,
    k: int = DEFAULT_QUERY_NEIGHBORS,
    epsilon: float = DEFAULT_IDW_EPSILON,
    specs: Sequence[KernelSpec] = DEFAULT_KERNEL_SPECS,
) -> Dict[str, Any]:
    """Run non-promoting validation-only kernel comparison benchmark."""
    if not dataset_version.strip():
        raise ValueError("Provide a non-empty dataset_version.")
    if k < 1:
        raise ValueError("k must be positive.")

    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new empty report directory for each snapshot.")

    frame = load_harmonized_parquet(parquet_path)
    split, provenance = _split_population(frame, validation_cutoff, test_cutoff)

    report: Dict[str, Any] = {
        "issue": "M16.3",
        "status": "exploratory_proxy_only_no_promotion",
        "dataset_version": dataset_version,
        "dataset_sha256": _digest(parquet_path),
        "macro_lookup_sha256": _digest(macro_path),
        "protocol": provenance,
        "fixed": {
            "k_neighbors": k,
            "epsilon": epsilon,
            "text_dimensions": 50,
            "metadata_dimensions": 3,
            "alpha": BILATERAL_ALPHA,
            "minimum_partition_size": DEFAULT_MIN_PARTITION_SIZE,
            "fallback_partition": "general_tech",
        },
        "kernels": [asdict(spec) for spec in specs],
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "sklearn": sklearn.__version__,
        },
        "edge_stability_probes": run_edge_stability_probes(specs=specs, epsilon=epsilon),
        "results": [],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "protocol_frozen.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    reducer = TextFeatureReducer(
        n_components=50,
        max_features=12000,
        ngram_range=(1, 2),
        min_df=1,
        random_state=42,
        normalize_output=False,
    )
    train_text = ensure_text_dimensions(reducer.fit_transform(split.train["raw_description"].tolist()))
    normalizer = ContinuousMetadataNormalizer(macro_path, alpha=BILATERAL_ALPHA)
    normalizer.fit(cast(List[Dict[str, Any]], split.train.to_dict(orient="records")))
    train_metadata = normalizer.transform(cast(List[Dict[str, Any]], split.train.to_dict(orient="records")))
    train_vectors = np.concatenate((train_text, train_metadata), axis=1)
    validation_vectors = _online_vectors(reducer, normalizer, split.validation)

    indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=DEFAULT_MIN_PARTITION_SIZE)
    indexer.fit(
        train_vectors,
        split.train["industry_partition"].tolist(),
        record_indices=split.train["record_id"].tolist(),
        verified_rates=split.train["target_rate"].tolist(),
    )

    # Pre-query nearest neighbors once per validation row so all kernels evaluate identical peer sets.
    cached_queries: List[Dict[str, Any]] = []
    for vector, row in zip(validation_vectors, split.validation.itertuples(index=False)):
        query_res = indexer._query_partition_tree(
            query_vector=vector,
            requested_partition=str(row.industry_partition),
            k=k,
            allow_fallback=True,
        )
        routed = str(query_res["routed_partition"])
        local_pos = np.asarray(query_res["local_neighbor_positions"], dtype=int)
        cached_queries.append(
            {
                "requested_partition": str(row.industry_partition),
                "routed_partition": routed,
                "fallback_triggered": bool(query_res["fallback_triggered"]),
                "distances": np.asarray(query_res["distances"], dtype=float),
                "verified_rates": indexer.partition_verified_rates[routed][local_pos],
                "bilateral_factor": float(row.bilateral_arbitrage_factor),
                "target_rate": float(row.target_rate),
            }
        )

    y_true = np.asarray([q["target_rate"] for q in cached_queries], dtype=float)
    baseline_metrics: Optional[Dict[str, float]] = None

    for spec in specs:
        preds: List[float] = []
        row_records: List[Dict[str, Any]] = []
        by_partition: Dict[str, List[Dict[str, Any]]] = {}

        for item in cached_queries:
            weights = DomainPartitionedKDTreeIndexer.compute_distance_weights(
                item["distances"],
                kernel=spec.kernel,
                power=spec.power,
                epsilon=epsilon,
                gamma=spec.gamma,
                sigma=spec.sigma,
            )
            weighted_rate = float(np.dot(item["verified_rates"], weights))
            base_rate = round(weighted_rate, 2)
            peer_stddev = weighted_peer_stddev(item["verified_rates"].tolist(), weights.tolist())
            bounds = synthesize_corridor(base_rate, peer_stddev, item["bilateral_factor"])
            if base_rate < 0.0 or bounds["min_quoted_rate"] < 0.0 or bounds["max_quoted_rate"] < bounds["min_quoted_rate"]:
                raise ValueError(f"Corridor invariant violated for kernel {spec.name}.")

            stats = compute_weight_distribution_stats(weights)
            rec = {
                **stats,
                "peer_stddev": peer_stddev,
                "corridor_width": bounds["max_quoted_rate"] - bounds["min_quoted_rate"],
                "requested_partition": item["requested_partition"],
            }
            preds.append(base_rate)
            row_records.append(rec)
            by_partition.setdefault(item["requested_partition"], []).append(rec)

        y_pred = np.asarray(preds, dtype=float)
        reg = _regression_metrics(y_true, y_pred)
        if spec.name == "idw_quadratic":
            baseline_metrics = reg

        overall_stats = _summarize_partition_records(row_records)
        partition_summary = {
            part: _summarize_partition_records(recs) for part, recs in sorted(by_partition.items())
        }
        dense_records = [r for p in DENSE_PARTITIONS for r in by_partition.get(p, [])]
        sparse_records = [r for p in SPARSE_PARTITIONS for r in by_partition.get(p, [])]

        entry: Dict[str, Any] = {
            "name": spec.name,
            "kernel": spec.kernel,
            "power": spec.power,
            "gamma": spec.gamma if spec.kernel == "exponential" else None,
            "sigma": spec.sigma if spec.kernel == "gaussian_rbf" else None,
            "description": spec.description,
            "validation": reg,
            "overall_dynamics": overall_stats,
            "dense_partitions_summary": _summarize_partition_records(dense_records),
            "sparse_partitions_summary": _summarize_partition_records(sparse_records),
            "per_partition": partition_summary,
            "corridor_invariants_preserved": True,
        }
        report["results"].append(entry)

    if baseline_metrics is not None:
        for entry in report["results"]:
            val = entry["validation"]
            entry["delta_vs_baseline"] = {
                "mae_delta": round(val["mae"] - baseline_metrics["mae"], 4),
                "rmse_delta": round(val["rmse"] - baseline_metrics["rmse"], 4),
                "r2_delta": round(val["r2"] - baseline_metrics["r2"], 6),
                "bias_delta": round(val["mean_bias"] - baseline_metrics["mean_bias"], 4),
            }

    (output / "benchmark.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="M16.3 distance weighting kernel validation benchmark")
    parser.add_argument("--harmonized-parquet", default=DEFAULT_HARMONIZED_PARQUET)
    parser.add_argument("--macro-lookup", required=True)
    parser.add_argument("--validation-cutoff", required=True)
    parser.add_argument("--test-cutoff", required=True)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT)
    parser.add_argument("--k", type=int, default=DEFAULT_QUERY_NEIGHBORS)
    args = parser.parse_args()
    report = run_benchmark(
        args.harmonized_parquet,
        args.macro_lookup,
        args.validation_cutoff,
        args.test_cutoff,
        args.dataset_version,
        output_dir=args.output_dir,
        k=args.k,
    )
    print(json.dumps({"report": str(Path(args.output_dir) / "benchmark.json"), "kernels": len(report["results"])}))


if __name__ == "__main__":
    main()
