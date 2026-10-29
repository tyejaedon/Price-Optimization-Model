"""Unit tests for Milestone 16 spatial engine refactorings.

Validates:
- Alternative distance metrics: Manhattan (L1) and Cosine (angular)
- Modular IDW weighting kernels: Linear, Power, Exponential, Gaussian RBF
- Cold-start fallback cascade: Tier 1, Tier 2 (Taxonomy Rollup), Tier 3 (Global Semantic Pool), Tier 4 (Macro Prior)
- Arbitrary latent dimensionality: n-dimensional embeddings fused with metadata (q in R^{n+3})
"""

import os
import tempfile
import unittest
import numpy as np

from src.engine.spatial_engine import DomainPartitionedKDTreeIndexer


class SpatialEngineMilestone16Tests(unittest.TestCase):
    def setUp(self) -> None:
        np.random.seed(42)
        self.dim = 30  # Arbitrary test dimension (e.g. 27 text + 3 metadata)
        self.vectors = np.random.randn(12, self.dim)
        self.partitions = [
            "data_ai", "data_ai", "data_ai",
            "web_backend", "web_backend", "web_backend",
            "mobile",
            "general_tech", "general_tech", "general_tech",
            "product_management", "digital_marketing"
        ]
        self.rates = [1000.0, 1100.0, 1200.0, 2000.0, 2100.0, 2200.0, 3000.0, 4000.0, 4100.0, 4200.0, 5000.0, 6000.0]

    def test_alternative_metric_manhattan(self) -> None:
        indexer = DomainPartitionedKDTreeIndexer(
            vector_dimensions=self.dim,
            metric="manhattan",
            minimum_partition_size=2,
        )
        indexer.fit(self.vectors, self.partitions, verified_rates=self.rates)
        result = indexer.predict_base_rate(self.vectors[0], requested_partition="data_ai", k=2)

        self.assertEqual(result["distance_metric"], "manhattan")
        self.assertEqual(result["routed_partition"], "data_ai")
        self.assertEqual(result["nearest_neighbors"][0]["distance"], 0.0)
        self.assertEqual(result["nearest_neighbors"][0]["verified_rate"], 1000.0)

    def test_alternative_metric_cosine(self) -> None:
        indexer = DomainPartitionedKDTreeIndexer(
            vector_dimensions=self.dim,
            metric="cosine",
            minimum_partition_size=2,
        )
        indexer.fit(self.vectors, self.partitions, verified_rates=self.rates)
        result = indexer.predict_base_rate(self.vectors[0], requested_partition="data_ai", k=2)

        self.assertEqual(result["distance_metric"], "cosine")
        self.assertEqual(result["routed_partition"], "data_ai")
        # Self-distance under cosine should be 0.0
        self.assertAlmostEqual(result["nearest_neighbors"][0]["distance"], 0.0, places=4)
        self.assertEqual(result["nearest_neighbors"][0]["verified_rate"], 1000.0)

    def test_modular_weighting_kernels(self) -> None:
        distances = [0.1, 0.5, 1.0, 2.0]

        # Linear kernel: 1 / (d + eps)
        w_linear = DomainPartitionedKDTreeIndexer.compute_inverse_distance_weights(distances, kernel="linear")
        self.assertAlmostEqual(float(np.sum(w_linear)), 1.0)
        self.assertTrue(w_linear[0] > w_linear[1] > w_linear[2] > w_linear[3])

        # Power kernel: 1 / (d^p + eps) with p=3.0
        w_power = DomainPartitionedKDTreeIndexer.compute_inverse_distance_weights(distances, kernel="power", power=3.0)
        self.assertAlmostEqual(float(np.sum(w_power)), 1.0)
        self.assertTrue(w_power[0] > w_power[1])

        # Exponential kernel: exp(-gamma * d)
        w_exp = DomainPartitionedKDTreeIndexer.compute_inverse_distance_weights(distances, kernel="exponential", gamma=2.0)
        self.assertAlmostEqual(float(np.sum(w_exp)), 1.0)
        self.assertTrue(w_exp[0] > w_exp[1] > w_exp[2] > w_exp[3])

        # Gaussian RBF kernel: exp(-d^2 / (2 * sigma^2))
        w_rbf = DomainPartitionedKDTreeIndexer.compute_inverse_distance_weights(distances, kernel="gaussian", sigma=1.0)
        self.assertAlmostEqual(float(np.sum(w_rbf)), 1.0)
        self.assertTrue(w_rbf[0] > w_rbf[1] > w_rbf[2] > w_rbf[3])

    def test_cold_start_fallback_cascade_tier2_taxonomy(self) -> None:
        # "mobile" has only 1 peer. Sibling is "web_backend" which has 3 peers.
        indexer = DomainPartitionedKDTreeIndexer(
            vector_dimensions=self.dim,
            minimum_partition_size=2,
            fallback_partition="general_tech",
        )
        indexer.fit(self.vectors, self.partitions, verified_rates=self.rates)

        # Without taxonomy, falls back to general_tech
        res_default = indexer.resolve_query_partition("mobile", k=2, use_taxonomy=False)
        self.assertEqual(res_default["routed_partition"], "general_tech")
        self.assertEqual(res_default["fallback_tier"], 2)

        # With taxonomy rollup, routes to sibling "web_backend"
        res_tax = indexer.resolve_query_partition("mobile", k=2, use_taxonomy=True)
        self.assertEqual(res_tax["routed_partition"], "web_backend")
        self.assertEqual(res_tax["fallback_tier"], 2)
        self.assertTrue(res_tax["is_cold_start"])

    def test_cold_start_fallback_cascade_tier3_global_pool(self) -> None:
        # Request k=5. Neither mobile (1), web_backend (3), nor general_tech (3) has 5 peers.
        # But global dataset has 12 peers!
        indexer = DomainPartitionedKDTreeIndexer(
            vector_dimensions=self.dim,
            minimum_partition_size=2,
        )
        indexer.fit(self.vectors, self.partitions, verified_rates=self.rates)

        # Without global pool, raises KeyError
        with self.assertRaises(KeyError):
            indexer.resolve_query_partition("mobile", k=5, allow_global_pool=False)

        # With global pool, routes to Tier 3 __global_pool__
        route_tier3 = indexer.resolve_query_partition("mobile", k=5, allow_global_pool=True)
        self.assertEqual(route_tier3["routed_partition"], "__global_pool__")
        self.assertEqual(route_tier3["fallback_tier"], 3)
        self.assertTrue(route_tier3["is_cold_start"])

        # Predict base rate with Tier 3 global pool and cross-domain penalty
        pred_tier3 = indexer.predict_base_rate(self.vectors[6], requested_partition="mobile", k=5, allow_global_pool=True)
        self.assertEqual(pred_tier3["routed_partition"], "__global_pool__")
        self.assertEqual(pred_tier3["k_neighbors_used"], 5)
        self.assertGreater(pred_tier3["base_predicted_rate"], 0.0)

    def test_cold_start_fallback_cascade_tier4_prior_rate(self) -> None:
        # Request k=20 when total rows = 12.
        indexer = DomainPartitionedKDTreeIndexer(
            vector_dimensions=self.dim,
            minimum_partition_size=2,
        )
        indexer.fit(self.vectors, self.partitions, verified_rates=self.rates)

        # Without tier4 prior rate, raises KeyError
        with self.assertRaises(KeyError):
            indexer.predict_base_rate(self.vectors[0], requested_partition="mobile", k=20, allow_global_pool=True)

        # With tier4 prior rate, returns empirical prior rate gracefully
        pred_tier4 = indexer.predict_base_rate(
            self.vectors[0],
            requested_partition="mobile",
            k=20,
            allow_global_pool=True,
            tier4_prior_rate=3500.0,
        )
        self.assertEqual(pred_tier4["fallback_tier"], 4)
        self.assertTrue(pred_tier4["is_cold_start"])
        self.assertEqual(pred_tier4["base_predicted_rate"], 3500.0)
        self.assertEqual(pred_tier4["k_neighbors_used"], 0)
        self.assertEqual(pred_tier4["nearest_neighbors"], [])

    def test_save_and_load_artifacts_roundtrip_with_m16_metadata(self) -> None:
        indexer = DomainPartitionedKDTreeIndexer(
            vector_dimensions=self.dim,
            metric="manhattan",
            kernel="exponential",
            decay_gamma=1.5,
            minimum_partition_size=2,
        )
        indexer.fit(self.vectors, self.partitions, verified_rates=self.rates)

        with tempfile.TemporaryDirectory() as tmp_dir:
            indexer.save_artifacts(tmp_dir)
            restored = DomainPartitionedKDTreeIndexer.load_artifacts(tmp_dir)

            self.assertEqual(restored.metric, "manhattan")
            self.assertEqual(restored.kernel, "exponential")
            self.assertEqual(restored.decay_gamma, 1.5)
            self.assertEqual(restored.global_count, 12)

            # Check query parity
            res_orig = indexer.predict_base_rate(self.vectors[0], "data_ai", k=2)
            res_rest = restored.predict_base_rate(self.vectors[0], "data_ai", k=2)
            self.assertEqual(res_orig["base_predicted_rate"], res_rest["base_predicted_rate"])
            self.assertEqual(res_orig["distance_metric"], res_rest["distance_metric"])
            self.assertEqual(res_orig["distance_kernel"], res_rest["distance_kernel"])


    def test_dynamic_vector_fusion_supports_arbitrary_latent_dimensions(self) -> None:
        from src.engine.macro_arbitrage import fuse_coordinates, fuse_coordinate_batches

        # 384 text dimensions (e.g. all-MiniLM-L6-v2) + 3 metadata = 387D hybrid
        text_vec = np.ones(384)
        meta_vec = np.array([0.5, 0.6, 0.7])
        fused = fuse_coordinates(text_vec, meta_vec, expected_text_dimensions=384, expected_metadata_dimensions=3)
        self.assertEqual(fused.shape, (387,))
        self.assertEqual(fused[0], 1.0)
        self.assertEqual(fused[-1], 0.7)

        # Batch fusion
        text_batch = np.ones((5, 384))
        meta_batch = np.ones((5, 3)) * 0.5
        fused_batch = fuse_coordinate_batches(text_batch, meta_batch, expected_text_dimensions=384, expected_metadata_dimensions=3)
        self.assertEqual(fused_batch.shape, (5, 387))


if __name__ == "__main__":
    unittest.main()
