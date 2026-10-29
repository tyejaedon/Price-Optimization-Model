"""Approximate Nearest Neighbor (ANN) search scaling benchmark (M16.6).

Evaluates exact spatial tree retrieval (KDTree / BallTree) against
Approximate Nearest Neighbor search (FAISS CPU or Annoy if installed, with a
lightweight Inverted Random Projection Hash index fallback).

Investigates vector scaling behavior across catalog sizes:
N in [1,000, 10,000, 50,000, 100,000] in D=53 dimensional feature space.

Metrics:
- Build / indexing time (seconds)
- Query latency (ms per query)
- Recall@k (fraction of true nearest neighbors retrieved by ANN)
- Scaling speedup factor
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import numpy as np
    from sklearn.neighbors import KDTree
except ImportError as exc:
    raise RuntimeError("Missing scikit-learn / numpy dependencies.") from exc

from src.engine.macro_arbitrage import HYBRID_VECTOR_DIMENSIONS


class InvertedProjectionANN:
    """Lightweight random projection hash index for ANN benchmarking when FAISS is uninstalled."""

    def __init__(self, n_projections: int = 16, n_features: int = HYBRID_VECTOR_DIMENSIONS, random_state: int = 42) -> None:
        self.n_projections = n_projections
        self.n_features = n_features
        rng = np.random.RandomState(random_state)
        self.hyperplanes = rng.randn(n_projections, n_features)
        self.buckets: Dict[int, List[int]] = {}
        self.data: Optional[np.ndarray] = None

    def fit(self, data: np.ndarray) -> "InvertedProjectionANN":
        self.data = np.asarray(data, dtype=float)
        self.buckets.clear()
        signatures = (np.dot(self.data, self.hyperplanes.T) > 0).astype(int)
        for idx, sig in enumerate(signatures):
            bucket_id = int(sum(bit << i for i, bit in enumerate(sig)))
            self.buckets.setdefault(bucket_id, []).append(idx)
        return self

    def query(self, query_vec: np.ndarray, k: int = 5) -> Tuple[np.ndarray, np.ndarray]:
        if self.data is None:
            raise RuntimeError("Index not fitted.")
        q = np.asarray(query_vec, dtype=float).reshape(-1)
        sig = (np.dot(self.hyperplanes, q) > 0).astype(int)
        bucket_id = int(sum(bit << i for i, bit in enumerate(sig)))

        candidates = self.buckets.get(bucket_id, [])
        if len(candidates) < k:
            # Multi-probe neighbor buckets if candidate pool is small
            for b_id in self.buckets.keys():
                if bin(b_id ^ bucket_id).count("1") <= 2:
                    candidates.extend(self.buckets[b_id])
                if len(candidates) >= k * 5:
                    break

        if not candidates:
            candidates = list(range(min(k * 10, len(self.data))))

        candidate_indices = np.unique(candidates)
        diff = self.data[candidate_indices] - q
        dists = np.linalg.norm(diff, axis=1)
        best_local = np.argsort(dists)[:k]

        return dists[best_local], candidate_indices[best_local]


def evaluate_ann_scale(
    n_samples: int,
    n_features: int = HYBRID_VECTOR_DIMENSIONS,
    k: int = 5,
    n_queries: int = 20,
    random_state: int = 42,
) -> Dict[str, Any]:
    """Benchmark exact KDTree vs ANN on a dataset of size n_samples."""
    rng = np.random.RandomState(random_state)
    data = rng.randn(n_samples, n_features)
    queries = rng.randn(n_queries, n_features)

    # 1. Exact KDTree
    t0 = time.perf_counter()
    exact_tree = KDTree(data, leaf_size=40)
    exact_build_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    exact_results = []
    for q in queries:
        dists, indices = exact_tree.query(q.reshape(1, -1), k=k)
        exact_results.append(set(indices[0]))
    exact_query_latency_ms = ((time.perf_counter() - t0) / n_queries) * 1000.0

    # 2. ANN Index
    has_faiss = False
    try:
        import faiss  # type: ignore
        has_faiss = True
        index_type = "faiss_cpu"
        t0 = time.perf_counter()
        quantizer = faiss.IndexFlatL2(n_features)
        nlist = max(4, int(np.sqrt(n_samples)))
        ann_index = faiss.IndexIVFFlat(quantizer, n_features, nlist)
        ann_index.train(data.astype(np.float32))
        ann_index.add(data.astype(np.float32))
        ann_index.nprobe = min(8, nlist)
        ann_build_time = time.perf_counter() - t0

        t0 = time.perf_counter()
        ann_results = []
        for q in queries:
            D, I = ann_index.search(q.reshape(1, -1).astype(np.float32), k)
            ann_results.append(set(I[0]))
        ann_query_latency_ms = ((time.perf_counter() - t0) / n_queries) * 1000.0

    except ImportError:
        index_type = "inverted_projection_hash"
        t0 = time.perf_counter()
        n_proj = min(16, max(4, int(np.log2(n_samples))))
        ann_indexer = InvertedProjectionANN(n_projections=n_proj, n_features=n_features, random_state=random_state)
        ann_indexer.fit(data)
        ann_build_time = time.perf_counter() - t0

        t0 = time.perf_counter()
        ann_results = []
        for q in queries:
            dists, indices = ann_indexer.query(q, k=k)
            ann_results.append(set(indices))
        ann_query_latency_ms = ((time.perf_counter() - t0) / n_queries) * 1000.0

    # Calculate average Recall@k
    recalls = [
        len(exact_set.intersection(ann_set)) / float(k)
        for exact_set, ann_set in zip(exact_results, ann_results)
    ]
    mean_recall = float(np.mean(recalls))

    return {
        "n_samples": n_samples,
        "n_features": n_features,
        "k": k,
        "index_type": index_type,
        "exact_kdtree": {
            "build_time_seconds": round(exact_build_time, 4),
            "query_latency_ms": round(exact_query_latency_ms, 4),
        },
        "ann": {
            "build_time_seconds": round(ann_build_time, 4),
            "query_latency_ms": round(ann_query_latency_ms, 4),
            "recall_at_k": round(mean_recall, 4),
        },
        "ann_speedup_factor": round(exact_query_latency_ms / max(0.0001, ann_query_latency_ms), 2),
    }


def run_scaling_benchmark(scales: Optional[List[int]] = None) -> List[Dict[str, Any]]:
    """Run vector search scaling across catalog sizes."""
    if scales is None:
        scales = [1000, 5000, 10000]

    reports = []
    for n in scales:
        report = evaluate_ann_scale(n_samples=n)
        reports.append(report)
    return reports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark exact KDTree vs Approximate Nearest Neighbor search.")
    parser.add_argument("--scales", type=int, nargs="+", default=[1000, 5000, 10000], help="Catalog scales to test")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = run_scaling_benchmark(scales=args.scales)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
