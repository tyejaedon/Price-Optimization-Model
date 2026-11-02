"""Unit tests for Milestone 16: Advanced Algorithmic Optimization, Vector Search Scaling & Continuous MLOps."""

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.benchmarks.advanced_algorithmic_scaling import (
    audit_coordinate_and_concept_drift,
    benchmark_vector_scaling,
    compute_calibrated_confidence,
    cosine_idw_weights,
    euclidean_idw_weights,
    local_ridge_prediction,
    run_m16_comprehensive_benchmark,
    softmax_kernel_weights,
)


class AdvancedAlgorithmicScalingTests(unittest.TestCase):
    def test_euclidean_idw_properties(self) -> None:
        distances = np.array([0.1, 0.2, 0.5])
        weights = euclidean_idw_weights(distances)
        self.assertAlmostEqual(float(np.sum(weights)), 1.0, places=6)
        self.assertGreater(weights[0], weights[1])
        self.assertGreater(weights[1], weights[2])

    def test_cosine_idw_properties(self) -> None:
        query = np.array([1.0, 0.0, 0.0])
        neighbors = np.array([
            [1.0, 0.0, 0.0],  # identical
            [0.707, 0.707, 0.0],  # 45 deg
            [0.0, 1.0, 0.0],  # orthogonal
        ])
        weights = cosine_idw_weights(query, neighbors)
        self.assertAlmostEqual(float(np.sum(weights)), 1.0, places=6)
        self.assertGreater(weights[0], weights[1])
        self.assertGreater(weights[1], weights[2])

    def test_softmax_kernel_weights(self) -> None:
        distances = np.array([0.0, 1.0, 2.0])
        weights = softmax_kernel_weights(distances, bandwidth=1.0)
        self.assertAlmostEqual(float(np.sum(weights)), 1.0, places=6)
        self.assertGreater(weights[0], weights[1])
        self.assertGreater(weights[1], weights[2])
        self.assertTrue(all(w > 0 for w in weights))

    def test_local_ridge_bounds(self) -> None:
        query = np.array([0.5, 0.5])
        neighbors = np.array([[0.1, 0.2], [0.4, 0.6], [0.8, 0.9]])
        rates = np.array([3000.0, 5000.0, 7000.0])
        pred = local_ridge_prediction(query, neighbors, rates, alpha=0.5)
        self.assertGreaterEqual(pred, 3000.0)
        self.assertLessEqual(pred, 7000.0)

    def test_calibrated_confidence_bounds_and_behavior(self) -> None:
        # High consensus (identical rates, low distance) -> high confidence
        high_conf = compute_calibrated_confidence([5000.0, 5000.0, 5000.0], [0.05, 0.08, 0.1])
        self.assertGreaterEqual(high_conf, 0.85)

        # High dispersion (rates all over the place) -> lower confidence
        low_conf = compute_calibrated_confidence([1000.0, 9000.0, 2500.0], [0.8, 0.9, 1.2])
        self.assertLess(low_conf, high_conf)

        # Edge cases
        self.assertEqual(compute_calibrated_confidence([], []), 0.0)
        self.assertEqual(compute_calibrated_confidence([5000.0], [0.1]), 0.5)

    def test_vector_search_scaling_benchmark(self) -> None:
        results = benchmark_vector_scaling(
            corpus_sizes=(500, 1500),
            dimensions=20,
            k=3,
            n_queries=15,
            seed=123,
        )
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertGreater(r.exact_build_time_ms, 0.0)
            self.assertGreater(r.ann_build_time_ms, 0.0)
            self.assertLessEqual(r.exact_query_p50_ms, r.exact_query_p95_ms)
            self.assertLessEqual(r.exact_query_p95_ms, r.exact_query_p99_ms)
            self.assertGreaterEqual(r.recall_at_k, 0.90)
            self.assertGreater(r.memory_mb, 0.0)

    def test_drift_auditing_stable_vs_shifted(self) -> None:
        rng = np.random.default_rng(42)
        baseline = rng.standard_normal((500, 10))
        identical = baseline.copy()
        rates_base = rng.uniform(3000.0, 6000.0, size=500)
        rates_same = rates_base.copy()

        stable_summary = audit_coordinate_and_concept_drift(
            baseline, identical, rates_base, rates_same
        )
        self.assertEqual(stable_summary.action_decision, "PIPELINE_STABLE")
        self.assertEqual(stable_summary.drifted_dimensions_count, 0)
        self.assertAlmostEqual(stable_summary.rate_drift_percent, 0.0, places=2)

        # Shifted production sample
        shifted = rng.standard_normal((500, 10))
        shifted[:, :5] += 2.0  # 50% of coordinates undergo large mean shift
        rates_shifted = rates_base * 1.5  # 50% rate inflation

        retrain_summary = audit_coordinate_and_concept_drift(
            baseline, shifted, rates_base, rates_shifted
        )
        self.assertEqual(retrain_summary.action_decision, "RETRAIN_RECOMMENDED")
        self.assertGreaterEqual(retrain_summary.drifted_dimensions_count, 4)
        self.assertGreater(retrain_summary.rate_drift_percent, 25.0)

    def test_run_m16_comprehensive_benchmark_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            report = run_m16_comprehensive_benchmark(output_dir=tmpdir, seed=42)
            self.assertIn("milestone", report)
            self.assertIn("algorithmic_optimization", report)
            self.assertIn("vector_search_scaling", report)
            self.assertIn("continuous_mlops_drift_audit", report)

            out_path = Path(tmpdir)
            self.assertTrue((out_path / "m16_benchmark_results.json").is_file())
            self.assertTrue((out_path / "m16_research_report.md").is_file())

            json_content = json.loads((out_path / "m16_benchmark_results.json").read_text())
            self.assertEqual(json_content["milestone"], report["milestone"])

            md_content = (out_path / "m16_research_report.md").read_text()
            self.assertIn("Milestone 16 Research Report", md_content)
            self.assertIn("Vector Search Scaling Benchmark", md_content)


if __name__ == "__main__":
    unittest.main()
