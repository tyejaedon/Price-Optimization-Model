import tempfile
import unittest

import numpy as np

from src.macro_arbitrage import HYBRID_VECTOR_DIMENSIONS
from src.spatial_engine import DomainPartitionedKDTreeIndexer


class DomainPartitionedKDTreeIndexerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.hybrid_vectors = np.vstack(
            [
                self._make_vector(0.0),
                self._make_vector(0.2),
                self._make_vector(0.4),
                self._make_vector(10.0),
                self._make_vector(10.2),
                self._make_vector(10.4),
                self._make_vector(20.0),
                self._make_vector(20.2),
                self._make_vector(20.4),
                self._make_vector(30.0),
            ]
        )
        self.partitions = [
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
        self.verified_rates = [1200.0, 1300.0, 1400.0, 4100.0, 4200.0, 4300.0, 6100.0, 6200.0, 6300.0, 8000.0]

    @staticmethod
    def _make_vector(seed: float) -> np.ndarray:
        vector = np.zeros(HYBRID_VECTOR_DIMENSIONS, dtype=float)
        vector[0] = seed
        vector[1] = seed / 2.0
        vector[2] = seed / 4.0
        vector[-3:] = np.array([seed / 8.0, seed / 16.0, seed / 32.0], dtype=float)
        return vector

    def test_fit_builds_tree_for_each_active_partition(self) -> None:
        indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=2)

        indexer.fit(self.hybrid_vectors, self.partitions)

        self.assertEqual(
            set(indexer.active_partitions()),
            {"data_ai", "general_tech", "product_management", "web_backend"},
        )
        self.assertEqual(indexer.partition_counts["data_ai"], 3)
        self.assertEqual(indexer.partition_counts["product_management"], 1)

    def test_query_stays_inside_requested_partition_without_fallback(self) -> None:
        indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=2)
        indexer.fit(self.hybrid_vectors, self.partitions)

        result = indexer.query(self.hybrid_vectors[4], requested_partition="web_backend", k=2)

        self.assertFalse(result["fallback_triggered"])
        self.assertEqual(result["routed_partition"], "web_backend")
        self.assertEqual(result["neighbor_count"], 2)
        self.assertTrue(all(self.partitions[index] == "web_backend" for index in result["neighbor_indices"]))

    def test_query_falls_back_for_low_volume_partition(self) -> None:
        indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=2)
        indexer.fit(self.hybrid_vectors, self.partitions)

        result = indexer.query(self.hybrid_vectors[9], requested_partition="product_management", k=2)

        self.assertTrue(result["fallback_triggered"])
        self.assertEqual(result["requested_partition"], "product_management")
        self.assertEqual(result["routed_partition"], "general_tech")
        self.assertTrue(all(self.partitions[index] == "general_tech" for index in result["neighbor_indices"]))

    def test_query_without_fallback_stays_in_low_volume_partition(self) -> None:
        indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=2)
        indexer.fit(self.hybrid_vectors, self.partitions)

        result = indexer.query(self.hybrid_vectors[9], requested_partition="product_management", k=5, allow_fallback=False)

        self.assertFalse(result["fallback_triggered"])
        self.assertEqual(result["routed_partition"], "product_management")
        self.assertEqual(result["neighbor_count"], 1)
        self.assertEqual(result["neighbor_indices"], [9])

    def test_save_and_load_artifacts_preserve_query_results(self) -> None:
        indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=2)
        indexer.fit(self.hybrid_vectors, self.partitions)
        baseline = indexer.query(self.hybrid_vectors[4], requested_partition="web_backend", k=3)

        with tempfile.TemporaryDirectory() as tmp_dir:
            indexer.save_artifacts(tmp_dir)
            restored = DomainPartitionedKDTreeIndexer.load_artifacts(tmp_dir)
            reloaded = restored.query(self.hybrid_vectors[4], requested_partition="web_backend", k=3)

        self.assertEqual(baseline["requested_partition"], reloaded["requested_partition"])
        self.assertEqual(baseline["routed_partition"], reloaded["routed_partition"])
        self.assertEqual(baseline["neighbor_indices"], reloaded["neighbor_indices"])
        np.testing.assert_allclose(baseline["distances"], reloaded["distances"], atol=1e-12)

    def test_fit_rejects_wrong_hybrid_dimensions(self) -> None:
        indexer = DomainPartitionedKDTreeIndexer()

        with self.assertRaisesRegex(ValueError, str(HYBRID_VECTOR_DIMENSIONS)):
            indexer.fit(np.ones((3, HYBRID_VECTOR_DIMENSIONS - 1)), ["data_ai", "data_ai", "data_ai"])

    def test_predict_base_rate_returns_peer_payload_schema(self) -> None:
        indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=2)
        indexer.fit(self.hybrid_vectors, self.partitions, verified_rates=self.verified_rates)

        result = indexer.predict_base_rate(self.hybrid_vectors[4], requested_partition="web_backend", k=3)

        self.assertEqual(result["requested_partition"], "web_backend")
        self.assertEqual(result["routed_partition"], "web_backend")
        self.assertEqual(result["k_neighbors_used"], 3)
        self.assertEqual(len(result["nearest_neighbors"]), 3)
        self.assertEqual(result["base_predicted_rate"], 4200.0)
        first_peer = result["nearest_neighbors"][0]
        self.assertEqual(set(first_peer.keys()), {"peer_index", "distance", "verified_rate", "similarity_score", "idw_weight"})
        self.assertEqual(first_peer["peer_index"], 4)
        self.assertEqual(first_peer["verified_rate"], 4200.0)

    def test_exact_match_prediction_is_stable_and_division_safe(self) -> None:
        indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=2)
        indexer.fit(self.hybrid_vectors, self.partitions, verified_rates=self.verified_rates)

        first = indexer.predict_base_rate(self.hybrid_vectors[4], requested_partition="web_backend", k=3)
        second = indexer.predict_base_rate(self.hybrid_vectors[4], requested_partition="web_backend", k=3)

        self.assertEqual(first["base_predicted_rate"], 4200.0)
        self.assertEqual(second["base_predicted_rate"], 4200.0)
        self.assertEqual(first["nearest_neighbors"][0]["distance"], 0.0)
        self.assertEqual(first["nearest_neighbors"][0]["similarity_score"], 1.0)
        self.assertGreater(first["nearest_neighbors"][0]["idw_weight"], 0.999)

    def test_similarity_scores_stay_bounded(self) -> None:
        indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=2)
        indexer.fit(self.hybrid_vectors, self.partitions, verified_rates=self.verified_rates)

        result = indexer.predict_base_rate(self.hybrid_vectors[9], requested_partition="product_management", k=2)

        self.assertTrue(result["fallback_triggered"])
        for peer in result["nearest_neighbors"]:
            self.assertGreater(peer["similarity_score"], 0.0)
            self.assertLessEqual(peer["similarity_score"], 1.0)

    def test_predict_base_rate_requires_verified_rates(self) -> None:
        indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=2)
        indexer.fit(self.hybrid_vectors, self.partitions)

        with self.assertRaisesRegex(RuntimeError, "verified_rates"):
            indexer.predict_base_rate(self.hybrid_vectors[4], requested_partition="web_backend", k=3)

    def test_save_and_load_artifacts_preserve_prediction_results(self) -> None:
        indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=2)
        indexer.fit(self.hybrid_vectors, self.partitions, verified_rates=self.verified_rates)
        baseline = indexer.predict_base_rate(self.hybrid_vectors[4], requested_partition="web_backend", k=3)

        with tempfile.TemporaryDirectory() as tmp_dir:
            indexer.save_artifacts(tmp_dir)
            restored = DomainPartitionedKDTreeIndexer.load_artifacts(tmp_dir)
            reloaded = restored.predict_base_rate(self.hybrid_vectors[4], requested_partition="web_backend", k=3)

        self.assertEqual(baseline["base_predicted_rate"], reloaded["base_predicted_rate"])
        self.assertEqual(baseline["nearest_neighbors"], reloaded["nearest_neighbors"])

    def test_quadratic_idw_uses_epsilon_and_handles_duplicate_exact_matches(self) -> None:
        weights = DomainPartitionedKDTreeIndexer.compute_inverse_distance_weights([0.0, 0.0, 1.0])
        expected = np.array([1e6, 1e6, 1 / (1 + 1e-6)])
        np.testing.assert_allclose(weights, expected / expected.sum())
        np.testing.assert_allclose(
            DomainPartitionedKDTreeIndexer.compute_inverse_distance_weights([1.0, 2.0]),
            np.array([1 / (1 + 1e-6), 1 / (4 + 1e-6)]) / (1 / (1 + 1e-6) + 1 / (4 + 1e-6)),
        )

    def test_five_peer_fallback_requires_general_tech_capacity(self) -> None:
        vectors = np.vstack([self._make_vector(float(index)) for index in range(10)])
        indexer = DomainPartitionedKDTreeIndexer()
        indexer.fit(vectors, ["mobile"] * 4 + ["general_tech"] * 6, verified_rates=[1000.0] * 10)
        result = indexer.predict_base_rate(vectors[0], requested_partition="mobile")
        self.assertEqual(result["routed_partition"], "general_tech")
        self.assertEqual(result["k_neighbors_used"], 5)
        with self.assertRaisesRegex(KeyError, "No partition"):
            indexer.predict_base_rate(vectors[0], requested_partition="data_ai", k=7)


if __name__ == "__main__":
    unittest.main()
