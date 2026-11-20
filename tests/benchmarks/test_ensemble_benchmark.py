import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.benchmarks.ensemble_benchmark import render_markdown_report, run_ensemble_benchmark
from tests.training.test_train_pipeline import TrainPipelineTests as _TrainPipelineTests


class EnsembleBenchmarkTests(unittest.TestCase):
    validation_cutoff = "2025-01-15T00:00:00+00:00"
    test_cutoff = "2025-02-15T00:00:00+00:00"

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        macro, parquet = _TrainPipelineTests()._write_input_artifacts(self.temp.name)
        self.macro = macro
        self.parquet = Path(parquet)

        frame = pd.read_parquet(self.parquet)
        frame["source_dataset"] = "upwork_jobs"
        frame["mentor_country_iso2"] = "KE"
        frame["client_country_iso2"] = "KE"
        frame["bilateral_arbitrage_factor"] = 1.0
        frame["observation_timestamp_utc"] = [
            ("2025-01-01T00:00:00+00:00", "2025-02-01T00:00:00+00:00", "2025-03-01T00:00:00+00:00")[i % 3]
            for i in range(len(frame))
        ]
        frame.loc[frame.index % 3 == 1, "raw_description"] += " validationonlyword"
        frame.loc[frame.index % 3 == 2, "raw_description"] += " testonlyword"
        frame.to_parquet(self.parquet, index=False)

    def test_ensemble_benchmark_end_to_end(self) -> None:
        small_grids = {
            "ridge": [{"alpha": 1.0}, {"alpha": 10.0}],
            "random_forest": [{"n_estimators": 10, "max_depth": 5, "min_samples_leaf": 2}],
            "xgboost": [{"n_estimators": 10, "learning_rate": 0.1, "max_depth": 3, "subsample": 1.0}],
        }
        report = run_ensemble_benchmark(
            parquet_path=self.parquet,
            macro_lookup_path=self.macro,
            validation_cutoff=self.validation_cutoff,
            test_cutoff=self.test_cutoff,
            seeds=(42, 123, 999),
            param_grids=small_grids,
            max_latency_samples=5,
            max_shap_samples=10,
        )

        self.assertEqual(report["benchmark"], "M16.1_ensemble_vs_knn")
        self.assertEqual(report["environment"]["seeds"], [42, 123, 999])
        self.assertGreater(report["splits"]["train_rows"], 0)
        self.assertGreater(report["splits"]["validation_rows"], 0)
        self.assertGreater(report["splits"]["test_rows"], 0)

        model_keys = {m["model_key"] for m in report["models"]}
        expected_keys = {
            "category_mean_raw",
            "knn_idw_raw",
            "knn_idw_log1p",
            "ridge_raw",
            "ridge_log1p",
            "random_forest_raw",
            "random_forest_log1p",
            "xgboost_raw",
            "xgboost_log1p",
        }
        self.assertEqual(model_keys, expected_keys)

        required_metrics = {"rmse", "mae", "median_absolute_error", "smape_percent", "r2"}
        for m in report["models"]:
            self.assertTrue(required_metrics.issubset(m["validation_metrics"].keys()))
            self.assertTrue(required_metrics.issubset(m["test_metrics"].keys()))
            self.assertIn("p50_ms", m["latency"])
            self.assertIn("p95_ms", m["latency"])
            self.assertIn("p99_ms", m["latency"])
            self.assertIn("artifact_size_mb", m)
            self.assertIn("spearman_abs_res_vs_pred_rho", m["heteroscedasticity"])
            if m["family"] in {"ridge", "random_forest", "xgboost"}:
                self.assertEqual(len(m["multi_seed_test"]), 3)

        interp = report["interpretability"]
        self.assertIn("ridge_global", interp)
        self.assertIn("random_forest_shap", interp)
        self.assertIn("xgboost_shap", interp)
        self.assertGreater(len(interp["knn_comparables"]), 0)
        self.assertGreater(len(interp["knn_comparables"][0]["comparables"]), 0)

        md = render_markdown_report(report)
        self.assertIn("## 2. Overall Validation & Test Accuracy Comparison", md)
        self.assertIn("## 5. Accuracy vs. Interpretability Trade-Off", md)
        self.assertIn("## 6. Single-Threaded Inference Latency & Resource Footprint", md)


if __name__ == "__main__":
    unittest.main()
