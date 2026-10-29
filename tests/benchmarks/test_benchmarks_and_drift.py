"""Unit tests for Milestone 16 benchmarks and MLOps drift monitor."""

import unittest
import numpy as np

from src.benchmarks.ensemble_benchmark import (
    compute_mape,
    generate_synthetic_benchmark_dataset,
    run_ensemble_comparison,
)
from src.benchmarks.ann_benchmark import (
    InvertedProjectionANN,
    evaluate_ann_scale,
)
from src.drift_monitor import (
    compute_psi,
    compute_kolmogorov_smirnov,
    compute_wasserstein,
    evaluate_retraining_trigger,
    analyze_transaction_drift,
)


class EnsembleBenchmarkTests(unittest.TestCase):
    def test_compute_mape(self) -> None:
        y_true = np.array([100.0, 200.0, 300.0])
        y_pred = np.array([110.0, 190.0, 300.0])
        mape = compute_mape(y_true, y_pred)
        # abs errors: 10/100 = 10%, 10/200 = 5%, 0 = 0%. Mean = 5%
        self.assertAlmostEqual(mape, 5.0, places=2)

    def test_run_ensemble_comparison(self) -> None:
        X_train, y_train, X_test, y_test = generate_synthetic_benchmark_dataset(n_samples=100, random_state=42)
        results = run_ensemble_comparison(X_train, y_train, X_test, y_test, k=3, random_state=42)

        expected_models = {"knn_idw", "ridge_regression", "random_forest", "gradient_boosting"}
        self.assertEqual(set(results.keys()), expected_models)

        for model_name, metrics in results.items():
            self.assertIn("mae_kes", metrics)
            self.assertIn("rmse_kes", metrics)
            self.assertIn("mape_percent", metrics)
            self.assertIn("inference_latency_ms", metrics)
            self.assertIn("interpretability_score", metrics)
            self.assertGreater(metrics["mae_kes"], 0.0)

        # KNN should have highest interpretability score
        self.assertEqual(results["knn_idw"]["interpretability_score"], 1.0)
        self.assertLess(results["gradient_boosting"]["interpretability_score"], 1.0)


class ANNBenchmarkTests(unittest.TestCase):
    def test_inverted_projection_ann_fit_and_query(self) -> None:
        rng = np.random.RandomState(42)
        data = rng.randn(50, 10)
        ann = InvertedProjectionANN(n_projections=8, n_features=10, random_state=42)
        ann.fit(data)

        query_vec = data[0]
        dists, indices = ann.query(query_vec, k=3)
        self.assertEqual(len(indices), 3)
        # Closest neighbor should be the point itself (index 0) with distance ~0
        self.assertEqual(indices[0], 0)
        self.assertAlmostEqual(float(dists[0]), 0.0, places=4)

    def test_evaluate_ann_scale(self) -> None:
        report = evaluate_ann_scale(n_samples=100, n_features=20, k=3, n_queries=5)
        self.assertEqual(report["n_samples"], 100)
        self.assertIn("exact_kdtree", report)
        self.assertIn("ann", report)
        self.assertIn("recall_at_k", report["ann"])
        self.assertGreaterEqual(report["ann"]["recall_at_k"], 0.0)
        self.assertLessEqual(report["ann"]["recall_at_k"], 1.0)


class DriftMonitorTests(unittest.TestCase):
    def test_compute_psi_identical_distributions(self) -> None:
        data = [100.0, 105.0, 110.0, 115.0, 120.0, 125.0, 130.0, 135.0, 140.0, 145.0] * 5
        psi = compute_psi(data, data)
        self.assertAlmostEqual(psi, 0.0, places=3)

    def test_compute_psi_shifted_distributions(self) -> None:
        ref = np.random.normal(100.0, 10.0, size=200)
        cur = np.random.normal(250.0, 15.0, size=200)
        psi = compute_psi(ref, cur)
        self.assertGreater(psi, 0.2)

    def test_statistical_distance_functions(self) -> None:
        ref = [10.0, 20.0, 30.0, 40.0]
        cur = [15.0, 25.0, 35.0, 45.0]

        ks_stat, ks_p = compute_kolmogorov_smirnov(ref, cur)
        self.assertGreaterEqual(ks_stat, 0.0)
        self.assertLessEqual(ks_stat, 1.0)

        w_dist = compute_wasserstein(ref, cur)
        self.assertAlmostEqual(w_dist, 5.0, places=4)

    def test_evaluate_retraining_trigger_stable_and_drift(self) -> None:
        # Stable case
        stable_dec = evaluate_retraining_trigger(
            target_psi=0.04,
            feature_psis={"feature_a": 0.03, "feature_b": 0.05},
        )
        self.assertEqual(stable_dec["status"], "STABLE")
        self.assertFalse(stable_dec["trigger_retrain"])

        # Severe target drift case
        drift_dec = evaluate_retraining_trigger(
            target_psi=0.35,
            feature_psis={"feature_a": 0.05, "feature_b": 0.05},
        )
        self.assertEqual(drift_dec["status"], "DRIFT_DETECTED")
        self.assertTrue(drift_dec["trigger_retrain"])

    def test_analyze_transaction_drift_integration(self) -> None:
        ref_txs = [
            {"final_quoted_rate": 3000.0 + i * 10, "base_predicted_rate": 2950.0, "mpesa_tariff_surcharge": 50.0}
            for i in range(50)
        ]
        cur_txs = [
            {"final_quoted_rate": 4500.0 + i * 10, "base_predicted_rate": 4450.0, "mpesa_tariff_surcharge": 50.0}
            for i in range(50)
        ]

        report = analyze_transaction_drift(ref_txs, cur_txs)
        self.assertEqual(report["status"], "DRIFT_DETECTED")
        self.assertTrue(report["trigger_retrain"])
        self.assertGreater(report["target_rate_psi"], 0.20)
        self.assertIn("target_ks_statistic", report)
        self.assertIn("target_wasserstein_distance", report)


if __name__ == "__main__":
    unittest.main()
