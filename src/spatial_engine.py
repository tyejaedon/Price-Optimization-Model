import argparse
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple, cast

try:
    import joblib
    import numpy as np
    from sklearn.neighbors import KDTree
except ImportError as exc:
    raise RuntimeError("Missing spatial-index dependencies. Install from requirements.txt") from exc

from src.ingest_multisource import SUPPORTED_INDUSTRY_PARTITIONS
from src.macro_arbitrage import HYBRID_VECTOR_DIMENSIONS

DEFAULT_ARTIFACT_DIR = "artifacts"
DEFAULT_KDTREE_ARTIFACT = "industry_kdtrees.joblib"
DEFAULT_KDTREE_METADATA = "industry_kdtrees_metadata.json"
DEFAULT_LEAF_SIZE = 40
DEFAULT_MIN_PARTITION_SIZE = 5
DEFAULT_QUERY_NEIGHBORS = 5
DEFAULT_FALLBACK_PARTITION = "general_tech"


def _normalize_partition(partition: Any) -> str:
    normalized = str(partition or "").strip().lower()
    if normalized in SUPPORTED_INDUSTRY_PARTITIONS:
        return normalized
    return DEFAULT_FALLBACK_PARTITION


def _coerce_hybrid_matrix(hybrid_vectors: Any) -> np.ndarray:
    matrix = np.asarray(hybrid_vectors, dtype=float)
    if matrix.ndim != 2:
        raise ValueError(f"hybrid_vectors must be a 2-D matrix; got shape {matrix.shape}.")
    if matrix.shape[1] != HYBRID_VECTOR_DIMENSIONS:
        raise ValueError(
            f"hybrid_vectors must have {HYBRID_VECTOR_DIMENSIONS} columns; got {matrix.shape[1]}."
        )
    if matrix.shape[0] == 0:
        raise ValueError("hybrid_vectors cannot be empty.")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("hybrid_vectors contains non-finite values.")
    return matrix.astype(float, copy=False)


def _coerce_query_vector(query_vector: Any) -> np.ndarray:
    vector = np.asarray(query_vector, dtype=float)
    if vector.ndim == 2:
        if vector.shape[0] != 1:
            raise ValueError(f"query_vector must be a 1-D vector or single-row matrix; got shape {vector.shape}.")
        vector = vector.reshape(-1)
    elif vector.ndim != 1:
        raise ValueError(f"query_vector must be 1-D; got shape {vector.shape}.")

    if vector.size != HYBRID_VECTOR_DIMENSIONS:
        raise ValueError(
            f"query_vector must contain exactly {HYBRID_VECTOR_DIMENSIONS} values; got {vector.size}."
        )
    if not np.all(np.isfinite(vector)):
        raise ValueError("query_vector contains non-finite values.")
    return vector.astype(float, copy=False)


class DomainPartitionedKDTreeIndexer:
    """Build and query domain-specific KD-Tree indices over fused hybrid coordinates."""

    def __init__(
        self,
        leaf_size: int = DEFAULT_LEAF_SIZE,
        minimum_partition_size: int = DEFAULT_MIN_PARTITION_SIZE,
        fallback_partition: str = DEFAULT_FALLBACK_PARTITION,
    ) -> None:
        self.leaf_size = max(1, int(leaf_size))
        self.minimum_partition_size = max(1, int(minimum_partition_size))
        self.fallback_partition = _normalize_partition(fallback_partition)
        self.partition_trees: Dict[str, KDTree] = {}
        self.partition_row_indices: Dict[str, np.ndarray] = {}
        self.partition_counts: Dict[str, int] = {}
        self.hybrid_dimensions = HYBRID_VECTOR_DIMENSIONS
        self.fitted = False

    def fit(
        self,
        hybrid_vectors: Any,
        industry_partitions: Sequence[str],
        record_indices: Optional[Sequence[int]] = None,
    ) -> None:
        matrix = _coerce_hybrid_matrix(hybrid_vectors)
        if len(industry_partitions) != matrix.shape[0]:
            raise ValueError(
                f"industry_partitions must align with hybrid_vectors rows; got {len(industry_partitions)} labels for {matrix.shape[0]} rows."
            )

        if record_indices is None:
            resolved_indices = np.arange(matrix.shape[0], dtype=int)
        else:
            if len(record_indices) != matrix.shape[0]:
                raise ValueError(
                    f"record_indices must align with hybrid_vectors rows; got {len(record_indices)} indices for {matrix.shape[0]} rows."
                )
            resolved_indices = np.asarray(record_indices, dtype=int)

        grouped_vectors: Dict[str, List[np.ndarray]] = {}
        grouped_indices: Dict[str, List[int]] = {}
        for row_number, partition in enumerate(industry_partitions):
            normalized_partition = _normalize_partition(partition)
            grouped_vectors.setdefault(normalized_partition, []).append(matrix[row_number])
            grouped_indices.setdefault(normalized_partition, []).append(int(resolved_indices[row_number]))

        if not grouped_vectors:
            raise ValueError("At least one active partition is required to fit the KD-Tree indexer.")

        self.partition_trees = {}
        self.partition_row_indices = {}
        self.partition_counts = {}

        for partition, rows in grouped_vectors.items():
            partition_matrix = np.vstack(rows)
            self.partition_trees[partition] = KDTree(partition_matrix, leaf_size=self.leaf_size)
            self.partition_row_indices[partition] = np.asarray(grouped_indices[partition], dtype=int)
            self.partition_counts[partition] = int(partition_matrix.shape[0])

        self.fitted = True

    def active_partitions(self) -> Tuple[str, ...]:
        return tuple(sorted(self.partition_trees.keys()))

    def _fallback_candidates(self, requested_partition: str) -> List[str]:
        active = list(self.partition_counts.keys())
        if not active:
            return []

        candidates: List[str] = []
        if self.fallback_partition in self.partition_counts and self.fallback_partition != requested_partition:
            candidates.append(self.fallback_partition)

        ranked = sorted(
            (partition for partition in active if partition != requested_partition and partition not in candidates),
            key=lambda partition: (-self.partition_counts[partition], partition),
        )
        candidates.extend(ranked)
        return candidates

    def resolve_query_partition(
        self,
        requested_partition: str,
        k: int = DEFAULT_QUERY_NEIGHBORS,
        allow_fallback: bool = True,
    ) -> Dict[str, Any]:
        if not self.fitted:
            raise RuntimeError("DomainPartitionedKDTreeIndexer must be fitted before resolve_query_partition().")

        requested = _normalize_partition(requested_partition)
        requested_count = self.partition_counts.get(requested, 0)
        required_count = max(1, min(int(k), self.minimum_partition_size))

        if requested in self.partition_trees and requested_count >= required_count:
            return {
                "requested_partition": requested,
                "routed_partition": requested,
                "fallback_triggered": False,
                "reason": "requested partition has sufficient volume",
            }

        if requested in self.partition_trees and not allow_fallback:
            return {
                "requested_partition": requested,
                "routed_partition": requested,
                "fallback_triggered": False,
                "reason": "fallback disabled for low-volume partition",
            }

        if not allow_fallback and requested not in self.partition_trees:
            raise KeyError(f"No KD-Tree exists for requested partition '{requested}'.")

        for candidate in self._fallback_candidates(requested):
            if self.partition_counts.get(candidate, 0) >= 1:
                trigger_reason = (
                    "requested partition unavailable" if requested_count == 0 else "low-volume partition fallback triggered"
                )
                return {
                    "requested_partition": requested,
                    "routed_partition": candidate,
                    "fallback_triggered": True,
                    "reason": trigger_reason,
                }

        if requested in self.partition_trees:
            return {
                "requested_partition": requested,
                "routed_partition": requested,
                "fallback_triggered": False,
                "reason": "no alternate fallback partition available",
            }

        raise KeyError(f"No KD-Tree exists for requested partition '{requested}' and no fallback partition is available.")

    def query(
        self,
        query_vector: Any,
        requested_partition: str,
        k: int = DEFAULT_QUERY_NEIGHBORS,
        allow_fallback: bool = True,
    ) -> Dict[str, Any]:
        if not self.fitted:
            raise RuntimeError("DomainPartitionedKDTreeIndexer must be fitted before query().")

        resolved_query = _coerce_query_vector(query_vector)
        route = self.resolve_query_partition(requested_partition=requested_partition, k=k, allow_fallback=allow_fallback)
        routed_partition = str(route["routed_partition"])

        tree = self.partition_trees[routed_partition]
        partition_row_indices = self.partition_row_indices[routed_partition]
        neighbor_count = min(max(1, int(k)), self.partition_counts[routed_partition])

        distances, local_indices = tree.query(resolved_query.reshape(1, -1), k=neighbor_count, return_distance=True)
        local_index_array = local_indices[0]
        distance_array = distances[0]
        global_indices = partition_row_indices[local_index_array]

        return {
            **route,
            "neighbor_count": int(neighbor_count),
            "neighbor_indices": [int(index) for index in global_indices.tolist()],
            "distances": [float(value) for value in distance_array.tolist()],
        }

    def save_artifacts(self, artifact_dir: str = DEFAULT_ARTIFACT_DIR) -> None:
        if not self.fitted:
            raise RuntimeError("DomainPartitionedKDTreeIndexer must be fitted before save_artifacts().")

        os.makedirs(artifact_dir, exist_ok=True)
        artifact_path = os.path.join(artifact_dir, DEFAULT_KDTREE_ARTIFACT)
        metadata_path = os.path.join(artifact_dir, DEFAULT_KDTREE_METADATA)

        payload = {
            "leaf_size": self.leaf_size,
            "minimum_partition_size": self.minimum_partition_size,
            "fallback_partition": self.fallback_partition,
            "partition_trees": self.partition_trees,
            "partition_row_indices": self.partition_row_indices,
            "partition_counts": self.partition_counts,
            "hybrid_dimensions": self.hybrid_dimensions,
        }
        joblib.dump(payload, artifact_path)

        metadata = {
            "leaf_size": self.leaf_size,
            "minimum_partition_size": self.minimum_partition_size,
            "fallback_partition": self.fallback_partition,
            "hybrid_dimensions": self.hybrid_dimensions,
            "active_partitions": list(self.active_partitions()),
            "partition_counts": {partition: int(count) for partition, count in self.partition_counts.items()},
        }
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, sort_keys=True)

    @classmethod
    def load_artifacts(cls, artifact_dir: str = DEFAULT_ARTIFACT_DIR) -> "DomainPartitionedKDTreeIndexer":
        artifact_path = os.path.join(artifact_dir, DEFAULT_KDTREE_ARTIFACT)
        payload = joblib.load(artifact_path)

        instance = cls(
            leaf_size=int(payload.get("leaf_size", DEFAULT_LEAF_SIZE)),
            minimum_partition_size=int(payload.get("minimum_partition_size", DEFAULT_MIN_PARTITION_SIZE)),
            fallback_partition=str(payload.get("fallback_partition", DEFAULT_FALLBACK_PARTITION)),
        )
        instance.partition_trees = cast(Dict[str, KDTree], dict(payload.get("partition_trees", {})))
        instance.partition_row_indices = {
            str(partition): np.asarray(indices, dtype=int)
            for partition, indices in dict(payload.get("partition_row_indices", {})).items()
        }
        instance.partition_counts = {str(partition): int(count) for partition, count in dict(payload.get("partition_counts", {})).items()}
        instance.hybrid_dimensions = int(payload.get("hybrid_dimensions", HYBRID_VECTOR_DIMENSIONS))
        instance.fitted = True
        return instance


def _build_demo_training_data() -> Tuple[np.ndarray, List[str], np.ndarray]:
    partitions = [
        "data_ai",
        "data_ai",
        "data_ai",
        "web_backend",
        "web_backend",
        "web_backend",
        "general_tech",
        "general_tech",
        "general_tech",
        "product_management",
    ]
    centers = {
        "data_ai": 0.0,
        "web_backend": 5.0,
        "general_tech": 10.0,
        "product_management": 25.0,
    }

    rows: List[np.ndarray] = []
    for row_number, partition in enumerate(partitions):
        base = centers[partition] + (row_number % 3) * 0.1
        vector = np.zeros(HYBRID_VECTOR_DIMENSIONS, dtype=float)
        vector[0] = base
        vector[1] = base / 10.0
        vector[2] = base / 20.0
        vector[-3:] = np.array([base / 30.0, base / 40.0, base / 50.0], dtype=float)
        rows.append(vector)

    matrix = np.vstack(rows)
    query_vector = matrix[-1].copy()
    return matrix, partitions, query_vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and query domain-partitioned KD-Tree indices.")
    parser.add_argument("--mode", choices=("fit_demo", "query_demo"), default="query_demo")
    parser.add_argument("--artifact-dir", default=DEFAULT_ARTIFACT_DIR, help="Directory for saved KD-Tree artifacts")
    parser.add_argument("--leaf-size", type=int, default=DEFAULT_LEAF_SIZE, help="KD-Tree leaf size")
    parser.add_argument(
        "--min-partition-size",
        type=int,
        default=DEFAULT_MIN_PARTITION_SIZE,
        help="Minimum partition size before fallback routing is allowed",
    )
    parser.add_argument(
        "--requested-partition",
        default="product_management",
        help="Partition to query during demo mode",
    )
    parser.add_argument("--k", type=int, default=DEFAULT_QUERY_NEIGHBORS, help="Number of neighbors to retrieve")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    matrix, partitions, query_vector = _build_demo_training_data()

    indexer = DomainPartitionedKDTreeIndexer(
        leaf_size=args.leaf_size,
        minimum_partition_size=args.min_partition_size,
    )
    indexer.fit(matrix, partitions)
    indexer.save_artifacts(args.artifact_dir)
    restored = DomainPartitionedKDTreeIndexer.load_artifacts(args.artifact_dir)

    payload: Dict[str, Any] = {
        "fit_rows": int(matrix.shape[0]),
        "fit_dimensions": int(matrix.shape[1]),
        "active_partitions": list(restored.active_partitions()),
        "partition_counts": restored.partition_counts,
        "artifact_dir": args.artifact_dir,
        "leaf_size": restored.leaf_size,
        "minimum_partition_size": restored.minimum_partition_size,
    }

    if args.mode == "query_demo":
        payload["query_result"] = restored.query(
            query_vector=query_vector,
            requested_partition=args.requested_partition,
            k=args.k,
            allow_fallback=True,
        )

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()


