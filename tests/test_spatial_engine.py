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


if __name__ == "__main__":
    unittest.main()

