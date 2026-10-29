r"""Partitioned peer search and inverse-distance base-rate estimation.

Training inputs are the fused hybrid feature vectors (default 53 dimensions:
50 text components plus three normalized metadata components) produced by the feature
pipeline, with support for arbitrary latent dimensions $q \in \mathbb{R}^{n+3}$.
KD-Trees / BallTrees are built independently for industry partitions so nearest
peers are normally drawn from the requested domain. Optional row-aligned
targets named ``verified_rates`` are in KES/hour; listing IDs and job titles retain peer
provenance in prediction explanations.

That historical rate name is not independent verification: training can supply
proxy budgets/asking rates. This index checks listing metadata shape; the
training exporter separately checks it against trusted root listing documents.
Distances are Euclidean, Manhattan, or Cosine in fitted feature space, not currency differences.

The command-line demo deliberately fits small synthetic vectors and rates to
exercise indexing and artifact round-trips. Those values are demonstration
data, not marketplace observations or evidence of real mentor pricing.
"""

import argparse
import json
import math
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union, cast

try:
    import joblib
    import numpy as np
    from sklearn.neighbors import BallTree, KDTree
except ImportError as exc:
    raise RuntimeError("Missing spatial-index dependencies. Install from requirements.txt") from exc

from src.data.ingest_multisource import SUPPORTED_INDUSTRY_PARTITIONS
from src.engine.interval_synthesizer import weighted_peer_stddev
from src.engine.macro_arbitrage import HYBRID_VECTOR_DIMENSIONS

DEFAULT_ARTIFACT_DIR = "artifacts"
DEFAULT_KDTREE_ARTIFACT = "industry_kdtrees.joblib"
DEFAULT_KDTREE_METADATA = "industry_kdtrees_metadata.json"
DEFAULT_LEAF_SIZE = 40
DEFAULT_MIN_PARTITION_SIZE = 5
DEFAULT_QUERY_NEIGHBORS = 5
DEFAULT_FALLBACK_PARTITION = "general_tech"
DEFAULT_IDW_EPSILON = 1e-6
DEFAULT_CROSS_DOMAIN_PENALTY = 1.25
DEFAULT_TAXONOMY_PATH = os.path.join("config", "industry_taxonomy.json")

SUPPORTED_METRICS = ("euclidean", "manhattan", "cosine")
SUPPORTED_KERNELS = ("quadratic", "linear", "power", "exponential", "gaussian", "rbf")


def _normalize_partition(partition: Any) -> str:
    normalized = str(partition or "").strip().lower()
    if normalized in SUPPORTED_INDUSTRY_PARTITIONS:
        return normalized
    return DEFAULT_FALLBACK_PARTITION


def _load_taxonomy_data(taxonomy_path: Optional[str] = None) -> Dict[str, Any]:
    target_path = taxonomy_path or DEFAULT_TAXONOMY_PATH
    if os.path.exists(target_path):
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("taxonomy", {})
        except Exception:
            return {}
    return {}


def _coerce_hybrid_matrix(hybrid_vectors: Any, expected_dimensions: int = HYBRID_VECTOR_DIMENSIONS) -> np.ndarray:
    matrix = np.asarray(hybrid_vectors, dtype=float)
    if matrix.ndim != 2:
        raise ValueError(f"hybrid_vectors must be a 2-D matrix; got shape {matrix.shape}.")
    if matrix.shape[1] != expected_dimensions:
        raise ValueError(
            f"hybrid_vectors must have {expected_dimensions} columns; got {matrix.shape[1]}."
        )
    if matrix.shape[0] == 0:
        raise ValueError("hybrid_vectors cannot be empty.")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("hybrid_vectors contains non-finite values.")
    return matrix.astype(float, copy=False)


def _coerce_query_vector(query_vector: Any, expected_dimensions: int = HYBRID_VECTOR_DIMENSIONS) -> np.ndarray:
    vector = np.asarray(query_vector, dtype=float)
    if vector.ndim == 2:
        if vector.shape[0] != 1:
            raise ValueError(f"query_vector must be a 1-D vector or single-row matrix; got shape {vector.shape}.")
        vector = vector.reshape(-1)
    elif vector.ndim != 1:
        raise ValueError(f"query_vector must be 1-D; got shape {vector.shape}.")

    if vector.size != expected_dimensions:
        raise ValueError(
            f"query_vector must contain exactly {expected_dimensions} values; got {vector.size}."
        )
    if not np.all(np.isfinite(vector)):
        raise ValueError("query_vector contains non-finite values.")
    return vector.astype(float, copy=False)


def _coerce_rate_vector(verified_rates: Sequence[float], expected_rows: int) -> np.ndarray:
    rates = np.asarray(verified_rates, dtype=float).reshape(-1)
    if rates.size != expected_rows:
        raise ValueError(
            f"verified_rates must align with hybrid_vectors rows; got {rates.size} rates for {expected_rows} rows."
        )
    if not np.all(np.isfinite(rates)):
        raise ValueError("verified_rates contains non-finite values.")
    return rates.astype(float, copy=False)


def _normalize_vector_l2(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm > 1e-12:
        return vector / norm
    return vector


def _normalize_matrix_l2(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms < 1e-12] = 1.0
    return matrix / norms


class DomainPartitionedKDTreeIndexer:
    r"""Build partition-specific KD-Trees or BallTrees over fused hybrid feature coordinates.

    Coordinates default to 53 dimensions ($q \in \mathbb{R}^{53}$): 50 text features
    followed by three normalized metadata features, and dynamically support
    arbitrary dimensions ($q \in \mathbb{R}^{n+3}$). Each tree stores only its own partition
    rows; aligned caller-supplied targets are interpreted as KES/hour, and optional
    listing IDs/titles are retained for matched-peer provenance.
    """

    def __init__(
        self,
        leaf_size: int = DEFAULT_LEAF_SIZE,
        minimum_partition_size: int = DEFAULT_MIN_PARTITION_SIZE,
        fallback_partition: str = DEFAULT_FALLBACK_PARTITION,
        vector_dimensions: Optional[int] = None,
        metric: str = "euclidean",
        kernel: str = "quadratic",
        idw_power: float = 2.0,
        decay_gamma: float = 1.0,
        rbf_sigma: Optional[float] = None,
        cross_domain_penalty: float = DEFAULT_CROSS_DOMAIN_PENALTY,
        taxonomy_path: Optional[str] = None,
    ) -> None:
        """Configure tree size, minimum partition volume, distance metric, and weighting kernel.

        ``metric`` supports 'euclidean', 'manhattan', or 'cosine'.
        ``kernel`` supports 'quadratic', 'linear', 'power', 'exponential', or 'gaussian'/'rbf'.
        """
        metric_norm = str(metric or "euclidean").strip().lower()
        if metric_norm not in SUPPORTED_METRICS:
            raise ValueError(f"Unsupported metric '{metric}'. Expected one of {SUPPORTED_METRICS}.")
        kernel_norm = str(kernel or "quadratic").strip().lower()
        if kernel_norm not in SUPPORTED_KERNELS:
            raise ValueError(f"Unsupported kernel '{kernel}'. Expected one of {SUPPORTED_KERNELS}.")

        self.leaf_size = max(1, int(leaf_size))
        self.minimum_partition_size = max(1, int(minimum_partition_size))
        self.fallback_partition = _normalize_partition(fallback_partition)
        self.hybrid_dimensions = max(1, int(vector_dimensions or HYBRID_VECTOR_DIMENSIONS))
        self.metric = metric_norm
        self.kernel = kernel_norm
        self.idw_power = float(idw_power)
        self.decay_gamma = float(decay_gamma)
        self.rbf_sigma = float(rbf_sigma) if rbf_sigma is not None else None
        self.cross_domain_penalty = max(1.0, float(cross_domain_penalty))
        self.taxonomy_path = taxonomy_path
        self.taxonomy = _load_taxonomy_data(taxonomy_path)

        self.partition_trees: Dict[str, Union[KDTree, BallTree]] = {}
        self.partition_row_indices: Dict[str, np.ndarray] = {}
        self.partition_verified_rates: Dict[str, np.ndarray] = {}
        self.partition_listing_ids: Dict[str, List[Optional[str]]] = {}
        self.partition_job_titles: Dict[str, List[Optional[str]]] = {}
        self.partition_counts: Dict[str, int] = {}

        # Global semantic index for Tier 3 cold-start fallback
        self.global_tree: Optional[Union[KDTree, BallTree]] = None
        self.global_row_indices: Optional[np.ndarray] = None
        self.global_verified_rates: Optional[np.ndarray] = None
        self.global_listing_ids: Optional[List[Optional[str]]] = None
        self.global_job_titles: Optional[List[Optional[str]]] = None
        self.global_partitions: Optional[List[str]] = None
        self.global_count: int = 0

        self.fitted = False

    def _create_tree(self, matrix: np.ndarray) -> Union[KDTree, BallTree]:
        """Instantiate appropriate tree based on metric."""
        if self.metric == "euclidean":
            return KDTree(matrix, leaf_size=self.leaf_size, metric="euclidean")
        elif self.metric == "manhattan":
            return BallTree(matrix, leaf_size=self.leaf_size, metric="manhattan")
        elif self.metric == "cosine":
            # For cosine distance, we index L2-normalized coordinates in Euclidean space
            norm_matrix = _normalize_matrix_l2(matrix)
            return BallTree(norm_matrix, leaf_size=self.leaf_size, metric="euclidean")
        raise ValueError(f"Unknown metric {self.metric}")

    def fit(
        self,
        hybrid_vectors: Any,
        industry_partitions: Sequence[str],
        record_indices: Optional[Sequence[int]] = None,
        verified_rates: Optional[Sequence[float]] = None,
        listing_ids: Optional[Sequence[Optional[str]]] = None,
        job_titles: Optional[Sequence[Optional[str]]] = None,
    ) -> None:
        """Fit one spatial tree per industry partition and a global semantic fallback tree."""
        matrix = _coerce_hybrid_matrix(hybrid_vectors, expected_dimensions=self.hybrid_dimensions)
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

        resolved_rates = _coerce_rate_vector(verified_rates, matrix.shape[0]) if verified_rates is not None else None
        if (listing_ids is None) != (job_titles is None):
            raise ValueError("listing_ids and job_titles must be supplied together")
        if listing_ids is not None and job_titles is not None:
            if len(listing_ids) != matrix.shape[0] or len(job_titles) != matrix.shape[0]:
                raise ValueError("listing provenance must align with hybrid_vectors rows")
            seen: set[str] = set()
            for listing_id, title in zip(listing_ids, job_titles):
                if listing_id is None and title is None:
                    continue
                if (not isinstance(listing_id, str) or not listing_id or listing_id != listing_id.strip()
                        or len(listing_id) > 200 or "/" in listing_id or listing_id in {".", ".."}
                        or not isinstance(title, str) or not title.strip() or len(title) > 200):
                    raise ValueError("listing provenance requires a valid listing_id and job_title")
                if listing_id in seen:
                    raise ValueError("listing_ids must be unique per peer")
                seen.add(listing_id)

        grouped_vectors: Dict[str, List[np.ndarray]] = {}
        grouped_indices: Dict[str, List[int]] = {}
        grouped_rates: Dict[str, List[float]] = {}
        grouped_listing_ids: Dict[str, List[Optional[str]]] = {}
        grouped_job_titles: Dict[str, List[Optional[str]]] = {}
        normalized_partitions_list: List[str] = []

        for row_number, partition in enumerate(industry_partitions):
            normalized_partition = _normalize_partition(partition)
            normalized_partitions_list.append(normalized_partition)
            grouped_vectors.setdefault(normalized_partition, []).append(matrix[row_number])
            grouped_indices.setdefault(normalized_partition, []).append(int(resolved_indices[row_number]))
            if resolved_rates is not None:
                grouped_rates.setdefault(normalized_partition, []).append(float(resolved_rates[row_number]))
            if listing_ids is not None and job_titles is not None:
                grouped_listing_ids.setdefault(normalized_partition, []).append(listing_ids[row_number])
                grouped_job_titles.setdefault(normalized_partition, []).append(job_titles[row_number])

        if not grouped_vectors:
            raise ValueError("At least one active partition is required to fit the spatial indexer.")

        self.partition_trees = {}
        self.partition_row_indices = {}
        self.partition_verified_rates = {}
        self.partition_listing_ids = {}
        self.partition_job_titles = {}
        self.partition_counts = {}

        for partition, rows in grouped_vectors.items():
            partition_matrix = np.vstack(rows)
            self.partition_trees[partition] = self._create_tree(partition_matrix)
            self.partition_row_indices[partition] = np.asarray(grouped_indices[partition], dtype=int)
            if resolved_rates is not None:
                self.partition_verified_rates[partition] = np.asarray(grouped_rates[partition], dtype=float)
            if listing_ids is not None:
                self.partition_listing_ids[partition] = grouped_listing_ids[partition]
                self.partition_job_titles[partition] = grouped_job_titles[partition]
            self.partition_counts[partition] = int(partition_matrix.shape[0])

        # Fit Global Semantic Tree (Tier 3 fallback)
        self.global_tree = self._create_tree(matrix)
        self.global_row_indices = resolved_indices
        self.global_verified_rates = resolved_rates
        self.global_listing_ids = list(listing_ids) if listing_ids is not None else None
        self.global_job_titles = list(job_titles) if job_titles is not None else None
        self.global_partitions = normalized_partitions_list
        self.global_count = int(matrix.shape[0])

        self.fitted = True

    def active_partitions(self) -> Tuple[str, ...]:
        """Return the fitted partition names in deterministic sorted order."""
        return tuple(sorted(self.partition_trees.keys()))

    def _fallback_candidates(self, requested_partition: str, use_taxonomy: bool = False) -> List[str]:
        """Determine candidate partitions for fallback routing."""
        active = list(self.partition_counts.keys())
        if not active:
            return []

        candidates: List[str] = []
        if use_taxonomy and self.taxonomy and requested_partition in self.taxonomy:
            spec = self.taxonomy[requested_partition]
            siblings = spec.get("siblings", [])
            for sibling in siblings:
                if sibling in active and sibling != requested_partition and sibling not in candidates:
                    candidates.append(sibling)
            parent = spec.get("parent")
            if parent and parent in active and parent != requested_partition and parent not in candidates:
                candidates.append(parent)

        if self.fallback_partition in active and self.fallback_partition != requested_partition and self.fallback_partition not in candidates:
            candidates.append(self.fallback_partition)

        return candidates

    def resolve_query_partition(
        self,
        requested_partition: str,
        k: int = DEFAULT_QUERY_NEIGHBORS,
        allow_fallback: bool = True,
        use_taxonomy: bool = False,
        allow_global_pool: bool = False,
    ) -> Dict[str, Any]:
        """Choose the partition to query, applying the multi-tier cold-start volume policy.

        Tier 1: Direct Partition Match (if partition volume >= required_count).
        Tier 2: Taxonomy Hierarchy Rollup / Fallback Partition.
        Tier 3: Global Semantic Pool across all partitions (if allow_global_pool=True).
        """
        if not self.fitted:
            raise RuntimeError("DomainPartitionedKDTreeIndexer must be fitted before resolve_query_partition().")

        requested = _normalize_partition(requested_partition)
        requested_count = self.partition_counts.get(requested, 0)
        required_count = max(1, int(k), self.minimum_partition_size)

        # Tier 1: Direct partition match
        if requested in self.partition_trees and requested_count >= required_count:
            return {
                "requested_partition": requested,
                "routed_partition": requested,
                "fallback_triggered": False,
                "fallback_tier": 1,
                "is_cold_start": False,
                "reason": "requested partition has sufficient volume",
            }

        # Fallback disabled branch
        if requested in self.partition_trees and not allow_fallback:
            return {
                "requested_partition": requested,
                "routed_partition": requested,
                "fallback_triggered": False,
                "fallback_tier": 1,
                "is_cold_start": False,
                "reason": "fallback disabled for low-volume partition",
            }

        if not allow_fallback and requested not in self.partition_trees:
            raise KeyError(f"No KD-Tree exists for requested partition '{requested}'.")

        # Tier 2: Taxonomy / Fallback partition routing
        for candidate in self._fallback_candidates(requested, use_taxonomy=use_taxonomy):
            if self.partition_counts[candidate] >= required_count:
                trigger_reason = (
                    "requested partition unavailable" if requested_count == 0 else "low-volume partition fallback triggered"
                )
                return {
                    "requested_partition": requested,
                    "routed_partition": candidate,
                    "fallback_triggered": True,
                    "fallback_tier": 2,
                    "is_cold_start": True,
                    "reason": trigger_reason,
                }

        # Tier 3: Global Semantic Pool
        if allow_global_pool and self.global_count >= required_count and self.global_tree is not None:
            return {
                "requested_partition": requested,
                "routed_partition": "__global_pool__",
                "fallback_triggered": True,
                "fallback_tier": 3,
                "is_cold_start": True,
                "reason": "global semantic pool fallback triggered",
            }

        raise KeyError(f"No partition with at least {required_count} peers exists for '{requested}'.")

    def _query_partition_tree(
        self,
        query_vector: np.ndarray,
        requested_partition: str,
        k: int = DEFAULT_QUERY_NEIGHBORS,
        allow_fallback: bool = True,
        use_taxonomy: bool = False,
        allow_global_pool: bool = False,
    ) -> Dict[str, Any]:
        route = self.resolve_query_partition(
            requested_partition=requested_partition,
            k=k,
            allow_fallback=allow_fallback,
            use_taxonomy=use_taxonomy,
            allow_global_pool=allow_global_pool,
        )
        routed_partition = str(route["routed_partition"])

        if routed_partition == "__global_pool__":
            # Tier 3 Global Tree query
            tree = cast(Union[KDTree, BallTree], self.global_tree)
            partition_row_indices = cast(np.ndarray, self.global_row_indices)
            total_count = self.global_count
            q_vec = _normalize_vector_l2(query_vector) if self.metric == "cosine" else query_vector
            neighbor_count = min(max(1, int(k)), total_count)
            raw_distances, local_indices = tree.query(q_vec.reshape(1, -1), k=neighbor_count, return_distance=True)
            local_index_array = np.asarray(local_indices[0], dtype=int)
            dist_array = np.asarray(raw_distances[0], dtype=float)

            if self.metric == "cosine":
                dist_array = np.clip(0.5 * np.square(dist_array), 0.0, 2.0)

            # Apply cross-domain distance penalty for peers from other partitions
            if self.global_partitions is not None:
                penalized_distances = []
                for idx, dist in zip(local_index_array, dist_array):
                    peer_part = self.global_partitions[idx]
                    penalty = 1.0 if peer_part == requested_partition else self.cross_domain_penalty
                    penalized_distances.append(float(dist * penalty))
                distance_array = np.asarray(penalized_distances, dtype=float)
            else:
                distance_array = dist_array

            global_indices = partition_row_indices[local_index_array]
            return {
                **route,
                "neighbor_count": int(neighbor_count),
                "local_neighbor_positions": [int(index) for index in local_index_array.tolist()],
                "neighbor_indices": [int(index) for index in global_indices.tolist()],
                "distances": [float(value) for value in distance_array.tolist()],
            }

        tree = self.partition_trees[routed_partition]
        partition_row_indices = self.partition_row_indices[routed_partition]
        neighbor_count = min(max(1, int(k)), self.partition_counts[routed_partition])

        q_vec = _normalize_vector_l2(query_vector) if self.metric == "cosine" else query_vector
        raw_distances, local_indices = tree.query(q_vec.reshape(1, -1), k=neighbor_count, return_distance=True)
        local_index_array = np.asarray(local_indices[0], dtype=int)
        dist_array = np.asarray(raw_distances[0], dtype=float)

        if self.metric == "cosine":
            dist_array = np.clip(0.5 * np.square(dist_array), 0.0, 2.0)

        global_indices = partition_row_indices[local_index_array]
        return {
            **route,
            "neighbor_count": int(neighbor_count),
            "local_neighbor_positions": [int(index) for index in local_index_array.tolist()],
            "neighbor_indices": [int(index) for index in global_indices.tolist()],
            "distances": [float(value) for value in dist_array.tolist()],
        }

    @staticmethod
    def compute_inverse_distance_weights(
        distances: Sequence[float],
        epsilon: float = DEFAULT_IDW_EPSILON,
        kernel: str = "quadratic",
        power: float = 2.0,
        gamma: float = 1.0,
        sigma: Optional[float] = None,
    ) -> np.ndarray:
        """Return normalized inverse-distance weights supporting multiple decay kernels.

        Kernels:
        - 'quadratic' (default): 1 / (d**2 + epsilon)
        - 'power' / 'linear': 1 / (d**p + epsilon)
        - 'exponential': exp(-gamma * d)
        - 'gaussian' / 'rbf': exp(-d**2 / (2 * sigma**2))
        """
        distance_array = np.asarray(distances, dtype=float).reshape(-1)
        if distance_array.size == 0:
            raise ValueError("distances cannot be empty.")
        if not np.all(np.isfinite(distance_array)):
            raise ValueError("distances contains non-finite values.")
        if np.any(distance_array < 0.0):
            raise ValueError("distances cannot contain negative values.")

        if not np.isfinite(epsilon) or epsilon <= 0:
            raise ValueError("epsilon must be finite and positive.")

        k_norm = str(kernel or "quadratic").strip().lower()

        if k_norm == "quadratic":
            raw_weights = 1.0 / (np.square(distance_array) + epsilon)
        elif k_norm == "linear":
            raw_weights = 1.0 / (distance_array + epsilon)
        elif k_norm == "power":
            p = max(0.1, float(power))
            raw_weights = 1.0 / (np.power(distance_array, p) + epsilon)
        elif k_norm == "exponential":
            g = max(0.001, float(gamma))
            raw_weights = np.exp(-g * distance_array)
        elif k_norm in ("gaussian", "rbf"):
            effective_sigma = float(sigma) if sigma is not None and sigma > 0 else max(float(np.median(distance_array)), 1e-4)
            raw_weights = np.exp(-np.square(distance_array) / (2.0 * (effective_sigma ** 2)))
        else:
            raise ValueError(f"Unsupported kernel '{kernel}'. Expected one of {SUPPORTED_KERNELS}.")

        total = np.sum(raw_weights)
        if total <= 0 or not np.isfinite(total):
            return np.full_like(raw_weights, 1.0 / raw_weights.size, dtype=float)
        return (raw_weights / total).astype(float, copy=False)

    @staticmethod
    def distance_to_similarity_score(distance: float) -> float:
        """Map a nonnegative distance to the bounded score ``1 / (1 + d)``."""
        safe_distance = max(0.0, float(distance))
        return 1.0 / (1.0 + safe_distance)

    def query(
        self,
        query_vector: Any,
        requested_partition: str,
        k: int = DEFAULT_QUERY_NEIGHBORS,
        allow_fallback: bool = True,
        use_taxonomy: bool = False,
        allow_global_pool: bool = False,
    ) -> Dict[str, Any]:
        """Return nearest-peer indices and distances for a hybrid query vector."""
        if not self.fitted:
            raise RuntimeError("DomainPartitionedKDTreeIndexer must be fitted before query().")

        resolved_query = _coerce_query_vector(query_vector, expected_dimensions=self.hybrid_dimensions)
        result = self._query_partition_tree(
            query_vector=resolved_query,
            requested_partition=requested_partition,
            k=k,
            allow_fallback=allow_fallback,
            use_taxonomy=use_taxonomy,
            allow_global_pool=allow_global_pool,
        )
        result.pop("local_neighbor_positions", None)
        return result

    def predict_base_rate(
        self,
        query_vector: Any,
        requested_partition: str,
        k: int = DEFAULT_QUERY_NEIGHBORS,
        allow_fallback: bool = True,
        epsilon: float = DEFAULT_IDW_EPSILON,
        kernel: Optional[str] = None,
        power: Optional[float] = None,
        gamma: Optional[float] = None,
        sigma: Optional[float] = None,
        use_taxonomy: bool = False,
        allow_global_pool: bool = False,
        tier4_prior_rate: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Estimate a base hourly rate from nearest peers in KES/hour.

        Supports multi-tier fallback cascade:
        - Tier 1: Direct Partition
        - Tier 2: Taxonomy Rollup / Sibling
        - Tier 3: Global Semantic Pool
        - Tier 4: Macroeconomic Empirical Prior
        """
        if not self.fitted:
            raise RuntimeError("DomainPartitionedKDTreeIndexer must be fitted before predict_base_rate().")
        if not self.partition_verified_rates and self.global_verified_rates is None:
            raise RuntimeError("DomainPartitionedKDTreeIndexer must be fitted with verified_rates before predict_base_rate().")

        resolved_query = _coerce_query_vector(query_vector, expected_dimensions=self.hybrid_dimensions)

        try:
            result = self._query_partition_tree(
                query_vector=resolved_query,
                requested_partition=requested_partition,
                k=k,
                allow_fallback=allow_fallback,
                use_taxonomy=use_taxonomy,
                allow_global_pool=allow_global_pool,
            )
        except KeyError:
            if tier4_prior_rate is not None:
                # Tier 4 Fallback: Macroeconomic Empirical Prior
                prior = float(tier4_prior_rate)
                return {
                    "requested_partition": _normalize_partition(requested_partition),
                    "routed_partition": "__prior_rate__",
                    "fallback_triggered": True,
                    "fallback_tier": 4,
                    "is_cold_start": True,
                    "reason": "Tier 4 macroeconomic prior fallback triggered",
                    "neighbor_count": 0,
                    "neighbor_indices": [],
                    "distances": [],
                    "k_neighbors_used": 0,
                    "base_predicted_rate": round(prior, 2),
                    "peer_stddev": 0.0,
                    "nearest_neighbors": [],
                    "distance_metric": self.metric,
                    "distance_kernel": kernel or self.kernel,
                }
            raise

        routed_partition = str(result["routed_partition"])
        local_neighbor_positions = np.asarray(result["local_neighbor_positions"], dtype=int)
        distance_array = np.asarray(result["distances"], dtype=float)

        if routed_partition == "__global_pool__":
            verified_rates = cast(np.ndarray, self.global_verified_rates)[local_neighbor_positions]
            listing_source = self.global_listing_ids
            job_title_source = self.global_job_titles
        else:
            verified_rates = self.partition_verified_rates[routed_partition][local_neighbor_positions]
            listing_source = self.partition_listing_ids.get(routed_partition)
            job_title_source = self.partition_job_titles.get(routed_partition)

        effective_kernel = kernel or self.kernel
        effective_power = power if power is not None else self.idw_power
        effective_gamma = gamma if gamma is not None else self.decay_gamma
        effective_sigma = sigma if sigma is not None else self.rbf_sigma

        idw_weights = self.compute_inverse_distance_weights(
            distance_array,
            epsilon=epsilon,
            kernel=effective_kernel,
            power=effective_power,
            gamma=effective_gamma,
            sigma=effective_sigma,
        )
        weighted_rate = float(np.dot(verified_rates, idw_weights))
        peer_stddev = weighted_peer_stddev(verified_rates.tolist(), idw_weights.tolist())

        nearest_neighbors: List[Dict[str, Any]] = []
        for peer_index, local_position, verified_rate, distance, weight in zip(
            result["neighbor_indices"],
            local_neighbor_positions.tolist(),
            verified_rates.tolist(),
            distance_array.tolist(),
            idw_weights.tolist(),
        ):
            peer = {
                "peer_index": int(peer_index),
                "distance": round(float(distance), 6),
                "verified_rate": round(float(verified_rate), 2),
                "similarity_score": round(self.distance_to_similarity_score(float(distance)), 6),
                "idw_weight": round(float(weight), 6),
            }
            if listing_source is not None and local_position < len(listing_source):
                listing_id = listing_source[local_position]
                if listing_id is not None:
                    peer["listing_id"] = listing_id
                    if job_title_source is not None and local_position < len(job_title_source):
                        peer["job_title"] = job_title_source[local_position]
            nearest_neighbors.append(peer)

        result.pop("local_neighbor_positions", None)
        result.update(
            {
                "k_neighbors_used": int(len(nearest_neighbors)),
                "base_predicted_rate": round(weighted_rate, 2),
                "peer_stddev": peer_stddev,
                "nearest_neighbors": nearest_neighbors,
                "distance_metric": self.metric,
                "distance_kernel": effective_kernel,
            }
        )
        return result

    def save_artifacts(self, artifact_dir: str = DEFAULT_ARTIFACT_DIR) -> None:
        """Serialize fitted trees and aligned metadata."""
        if not self.fitted:
            raise RuntimeError("DomainPartitionedKDTreeIndexer must be fitted before save_artifacts().")

        os.makedirs(artifact_dir, exist_ok=True)
        artifact_path = os.path.join(artifact_dir, DEFAULT_KDTREE_ARTIFACT)
        metadata_path = os.path.join(artifact_dir, DEFAULT_KDTREE_METADATA)

        payload = {
            "leaf_size": self.leaf_size,
            "minimum_partition_size": self.minimum_partition_size,
            "fallback_partition": self.fallback_partition,
            "hybrid_dimensions": self.hybrid_dimensions,
            "metric": self.metric,
            "kernel": self.kernel,
            "idw_power": self.idw_power,
            "decay_gamma": self.decay_gamma,
            "rbf_sigma": self.rbf_sigma,
            "cross_domain_penalty": self.cross_domain_penalty,
            "partition_trees": self.partition_trees,
            "partition_row_indices": self.partition_row_indices,
            "partition_verified_rates": self.partition_verified_rates,
            "partition_listing_ids": self.partition_listing_ids,
            "partition_job_titles": self.partition_job_titles,
            "partition_counts": self.partition_counts,
            "global_tree": self.global_tree,
            "global_row_indices": self.global_row_indices,
            "global_verified_rates": self.global_verified_rates,
            "global_listing_ids": self.global_listing_ids,
            "global_job_titles": self.global_job_titles,
            "global_partitions": self.global_partitions,
            "global_count": self.global_count,
        }
        joblib.dump(payload, artifact_path)

        metadata = {
            "leaf_size": self.leaf_size,
            "minimum_partition_size": self.minimum_partition_size,
            "fallback_partition": self.fallback_partition,
            "hybrid_dimensions": self.hybrid_dimensions,
            "metric": self.metric,
            "kernel": self.kernel,
            "active_partitions": list(self.active_partitions()),
            "has_verified_rates": bool(self.partition_verified_rates),
            "has_listing_provenance": any(any(ids) for ids in self.partition_listing_ids.values()),
            "partition_counts": {partition: int(count) for partition, count in self.partition_counts.items()},
            "global_count": self.global_count,
        }
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, sort_keys=True)

    @classmethod
    def load_artifacts(cls, artifact_dir: str = DEFAULT_ARTIFACT_DIR) -> "DomainPartitionedKDTreeIndexer":
        """Restore a saved index bundle."""
        artifact_path = os.path.join(artifact_dir, DEFAULT_KDTREE_ARTIFACT)
        payload = joblib.load(artifact_path)

        instance = cls(
            leaf_size=int(payload.get("leaf_size", DEFAULT_LEAF_SIZE)),
            minimum_partition_size=int(payload.get("minimum_partition_size", DEFAULT_MIN_PARTITION_SIZE)),
            fallback_partition=str(payload.get("fallback_partition", DEFAULT_FALLBACK_PARTITION)),
            vector_dimensions=int(payload.get("hybrid_dimensions", HYBRID_VECTOR_DIMENSIONS)),
            metric=str(payload.get("metric", "euclidean")),
            kernel=str(payload.get("kernel", "quadratic")),
            idw_power=float(payload.get("idw_power", 2.0)),
            decay_gamma=float(payload.get("decay_gamma", 1.0)),
            rbf_sigma=float(payload["rbf_sigma"]) if payload.get("rbf_sigma") is not None else None,
            cross_domain_penalty=float(payload.get("cross_domain_penalty", DEFAULT_CROSS_DOMAIN_PENALTY)),
        )
        instance.partition_trees = dict(payload.get("partition_trees", {}))
        instance.partition_row_indices = {
            str(partition): np.asarray(indices, dtype=int)
            for partition, indices in dict(payload.get("partition_row_indices", {})).items()
        }
        instance.partition_verified_rates = {
            str(partition): np.asarray(rates, dtype=float)
            for partition, rates in dict(payload.get("partition_verified_rates", {})).items()
        }
        instance.partition_listing_ids = dict(payload.get("partition_listing_ids", {}))
        instance.partition_job_titles = dict(payload.get("partition_job_titles", {}))
        instance.partition_counts = {
            str(partition): int(count) for partition, count in dict(payload.get("partition_counts", {})).items()
        }
        instance.global_tree = payload.get("global_tree")
        instance.global_row_indices = payload.get("global_row_indices")
        instance.global_verified_rates = payload.get("global_verified_rates")
        instance.global_listing_ids = payload.get("global_listing_ids")
        instance.global_job_titles = payload.get("global_job_titles")
        instance.global_partitions = payload.get("global_partitions")
        instance.global_count = int(payload.get("global_count", 0))
        instance.fitted = True
        return instance


def _build_demo_training_data() -> Tuple[np.ndarray, List[str], np.ndarray, np.ndarray]:
    """Construct synthetic 53D rows, partitions, KES/hour rates, and one query."""
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
    verified_rates: List[float] = []
    for row_number, partition in enumerate(partitions):
        base = centers[partition] + (row_number % 3) * 0.1
        vector = np.zeros(HYBRID_VECTOR_DIMENSIONS, dtype=float)
        vector[0] = base
        vector[1] = base / 10.0
        vector[2] = base / 20.0
        vector[-3:] = np.array([base / 30.0, base / 40.0, base / 50.0], dtype=float)
        rows.append(vector)
        verified_rates.append(round(2500.0 + (base * 120.0), 2))

    matrix = np.vstack(rows)
    query_vector = matrix[-1].copy()
    return matrix, partitions, np.asarray(verified_rates, dtype=float), query_vector


def parse_args() -> argparse.Namespace:
    """Parse options for the synthetic demonstration."""
    parser = argparse.ArgumentParser(description="Build and query domain-partitioned spatial indices.")
    parser.add_argument("--mode", choices=("fit_demo", "query_demo", "idw_demo"), default="query_demo")
    parser.add_argument("--artifact-dir", default=DEFAULT_ARTIFACT_DIR, help="Directory for saved artifacts")
    parser.add_argument("--leaf-size", type=int, default=DEFAULT_LEAF_SIZE, help="Spatial tree leaf size")
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
    parser.add_argument("--metric", choices=SUPPORTED_METRICS, default="euclidean", help="Distance metric")
    parser.add_argument("--kernel", choices=SUPPORTED_KERNELS, default="quadratic", help="IDW weighting kernel")
    return parser.parse_args()


def main() -> None:
    """Fit, persist, reload, and query the synthetic demonstration index."""
    args = parse_args()
    matrix, partitions, verified_rates, query_vector = _build_demo_training_data()

    indexer = DomainPartitionedKDTreeIndexer(
        leaf_size=args.leaf_size,
        minimum_partition_size=args.min_partition_size,
        metric=args.metric,
        kernel=args.kernel,
    )
    indexer.fit(matrix, partitions, verified_rates=verified_rates)
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
        "metric": restored.metric,
        "kernel": restored.kernel,
    }

    if args.mode == "query_demo":
        payload["query_result"] = restored.query(
            query_vector=query_vector,
            requested_partition=args.requested_partition,
            k=args.k,
            allow_fallback=True,
        )
    if args.mode == "idw_demo":
        payload["prediction_result"] = restored.predict_base_rate(
            query_vector=query_vector,
            requested_partition=args.requested_partition,
            k=args.k,
            allow_fallback=True,
        )

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
