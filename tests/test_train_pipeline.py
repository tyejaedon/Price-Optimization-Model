import os
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.ingest_multisource import build_macro_lookup
from src.experiment_reporting import run_experiment_report, run_feature_ablation_report
from src.train_pipeline import (
    DEFAULT_TRAINING_SUMMARY_ARTIFACT,
    _metric_summary,
    build_stratified_splits,
    evaluate_and_serialize_training,
    inverse_target_log1p,
    load_harmonized_parquet,
    orchestrate_training,
    transform_target_log1p,
)


class TrainPipelineTests(unittest.TestCase):
    @staticmethod
    def _alpha_token(index: int) -> str:
        alphabet = "abcdefghijklmnopqrstuvwxyz"
        chars = []
        value = index
        base = len(alphabet)
        while True:
            chars.append(alphabet[value % base])
            value //= base
            if value == 0:
                break
        return "tok" + "".join(chars)

    def _build_synthetic_harmonized_frame(self) -> pd.DataFrame:
        rows = []
        partitions = (
            ("data_ai", 90, 4500.0),
            ("web_backend", 54, 3800.0),
            ("design_creative", 36, 3200.0),
        )

        row_id = 0
        for partition, count, base_rate in partitions:
            for i in range(count):
                bucket = i % 6
                bucket_token = self._alpha_token(bucket)
                tok_a = self._alpha_token(row_id)
                tok_b = self._alpha_token(row_id + 200)
                tok_c = self._alpha_token(row_id + 400)
                bilateral = 1.0 + (bucket * 0.06)
                saturation = (count / 180.0) + (bucket * 0.002)
                density = (count / 90.0) + (bucket * 0.015)
                target_rate = base_rate + float(bucket) * 320.0
                rows.append(
                    {
                        "raw_description": (
                            f"{partition} mentoring python analytics skill{bucket_token} "
                            f"cluster{bucket_token} {tok_a} {tok_b} {tok_c}"
                        ),
                        "industry_partition": partition,
                        "bilateral_arbitrage_factor": bilateral,
                        "market_saturation_score": saturation,
                        "industry_relative_density": density,
                        "harmonized_hourly_rate": target_rate,
                        "hourly_rate": base_rate,
                    }
                )
                row_id += 1

        return pd.DataFrame(rows)

    def _write_input_artifacts(self, tmp_dir: str) -> tuple[str, str]:
        repo_root = Path(__file__).resolve().parent.parent
        raw_fixture_dir = str(repo_root / "tests" / "fixtures" / "raw")
        macro_lookup_path = os.path.join(tmp_dir, "macro_lookup_table.json")
        parquet_path = os.path.join(tmp_dir, "harmonized_marketplace_corpus.parquet")

        build_macro_lookup(raw_fixture_dir, macro_lookup_path)
        frame = self._build_synthetic_harmonized_frame()
        frame.to_parquet(parquet_path, index=False)
        return macro_lookup_path, parquet_path

    def test_build_stratified_splits_are_disjoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            _, parquet_path = self._write_input_artifacts(tmp_dir)
            frame = load_harmonized_parquet(parquet_path)

            splits = build_stratified_splits(frame, train_ratio=0.70, validation_ratio=0.15, test_ratio=0.15, random_state=42)

            self.assertEqual(len(frame), len(splits.train) + len(splits.validation) + len(splits.test))
            train_ids = set(splits.train["record_id"].tolist())
            validation_ids = set(splits.validation["record_id"].tolist())
            test_ids = set(splits.test["record_id"].tolist())
            self.assertFalse(train_ids & validation_ids)
            self.assertFalse(train_ids & test_ids)
            self.assertFalse(validation_ids & test_ids)

    def test_partition_distribution_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            _, parquet_path = self._write_input_artifacts(tmp_dir)
            frame = load_harmonized_parquet(parquet_path)
            splits = build_stratified_splits(frame, train_ratio=0.70, validation_ratio=0.15, test_ratio=0.15, random_state=42)

            full_dist = frame["industry_partition"].value_counts(normalize=True).to_dict()
            for split_frame in (splits.train, splits.validation, splits.test):
                split_dist = split_frame["industry_partition"].value_counts(normalize=True).to_dict()
                for partition_name, full_ratio in full_dist.items():
                    self.assertIn(partition_name, split_dist)
                    self.assertLess(abs(float(split_dist[partition_name]) - float(full_ratio)), 0.08)

    def test_orchestration_runs_end_to_end_to_feature_matrices(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            macro_lookup_path, parquet_path = self._write_input_artifacts(tmp_dir)
            artifact_dir = os.path.join(tmp_dir, "artifacts")

            payload = orchestrate_training(
                harmonized_parquet_path=parquet_path,
                macro_lookup_path=macro_lookup_path,
                artifact_dir=artifact_dir,
                save_artifacts=True,
                random_state=42,
            )

            self.assertFalse(payload["has_split_overlap"])
            self.assertEqual(payload["feature_shapes"]["x_train"][1], 53)
            self.assertEqual(payload["feature_shapes"]["x_validation"][1], 53)
            self.assertEqual(payload["feature_shapes"]["x_test"][1], 53)
            self.assertEqual(payload["feature_shapes"]["x_train"][0], payload["feature_shapes"]["y_train"])
            self.assertEqual(payload["feature_shapes"]["x_validation"][0], payload["feature_shapes"]["y_validation"])
            self.assertEqual(payload["feature_shapes"]["x_test"][0], payload["feature_shapes"]["y_test"])

            self.assertTrue(os.path.exists(os.path.join(artifact_dir, "tfidf_vectorizer.joblib")))
            self.assertTrue(os.path.exists(os.path.join(artifact_dir, "svd_reducer.joblib")))
            self.assertTrue(os.path.exists(os.path.join(artifact_dir, "metadata_scaler.joblib")))

    def test_evaluation_writes_metrics_and_training_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            macro_lookup_path, parquet_path = self._write_input_artifacts(tmp_dir)
            artifact_dir = os.path.join(tmp_dir, "artifacts")

            payload = evaluate_and_serialize_training(
                harmonized_parquet_path=parquet_path,
                macro_lookup_path=macro_lookup_path,
                artifact_dir=artifact_dir,
                quality_gate_r2=0.0,
                enforce_quality_gate=True,
            )

            self.assertIn("model_metrics", payload)
            self.assertIn("validation", payload["model_metrics"])
            self.assertIn("test", payload["model_metrics"])
            self.assertIn("baseline_metrics", payload)
            self.assertIn("baseline_comparison", payload)
            self.assertIn("quality_gate", payload)
            self.assertIn("target_transformation_comparison", payload)
            self.assertEqual(payload["target_transformation_comparison"]["log1p"]["transformation"], "log1p")
            self.assertEqual(payload["target_transformation_comparison"]["log1p"]["inverse_transformation"], "expm1")
            self.assertFalse(payload["has_split_overlap"])

            summary_path = os.path.join(artifact_dir, DEFAULT_TRAINING_SUMMARY_ARTIFACT)
            self.assertTrue(os.path.exists(summary_path))
            self.assertTrue(os.path.exists(os.path.join(artifact_dir, "industry_kdtrees.joblib")))

    def test_log_target_round_trip_and_robust_metrics_are_finite(self) -> None:
        target = pd.Series([166.9, 2500.0, 60000.0, 343823.36], dtype=float).to_numpy()
        transformed = transform_target_log1p(target)
        restored = inverse_target_log1p(transformed)

        pd.testing.assert_series_equal(pd.Series(restored), pd.Series(target), check_exact=False, rtol=1e-12, atol=1e-12)
        metrics = _metric_summary(target, restored)
        self.assertEqual(set(metrics), {"rmse", "mae", "median_absolute_error", "smape_percent", "r2"})
        self.assertTrue(all(pd.notna(value) and value >= 0.0 for value in metrics.values() if value != metrics["r2"]))
        self.assertTrue(pd.notna(metrics["r2"]))

    def test_log_target_rejects_negative_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-negative"):
            transform_target_log1p(pd.Series([1.0, -0.5]).to_numpy(dtype=float))

    def test_feature_ablation_report_is_leakage_safe_and_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            macro_lookup_path, parquet_path = self._write_input_artifacts(tmp_dir)
            report_dir = os.path.join(tmp_dir, "feature_ablations")
            payload = run_feature_ablation_report(
                harmonized_parquet_path=parquet_path,
                macro_lookup_path=macro_lookup_path,
                output_dir=report_dir,
                k_neighbors=2,
                groups=("macro_enrichment", "partition_statistics"),
            )
            self.assertTrue(os.path.exists(os.path.join(report_dir, "metadata_enrichment_metadata.json")))
            self.assertTrue(os.path.exists(os.path.join(report_dir, "feature_ablation_results.csv")))
            self.assertTrue(os.path.exists(os.path.join(report_dir, "feature_ablation_report.md")))
            self.assertEqual(payload["k_neighbors"], 2)
            self.assertEqual(payload["selected_groups"], ["macro_enrichment", "partition_statistics"])
            self.assertIn("best_validation_ablation", payload)
    def test_quality_gate_is_enforced_programmatically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            macro_lookup_path, parquet_path = self._write_input_artifacts(tmp_dir)
            artifact_dir = os.path.join(tmp_dir, "artifacts")

            with self.assertRaisesRegex(RuntimeError, "Quality gate failed"):
                evaluate_and_serialize_training(
                    harmonized_parquet_path=parquet_path,
                    macro_lookup_path=macro_lookup_path,
                    artifact_dir=artifact_dir,
                    quality_gate_r2=1.01,
                    enforce_quality_gate=True,
                )

    def test_experiment_report_writes_tuning_tables_and_diagrams(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            macro_lookup_path, parquet_path = self._write_input_artifacts(tmp_dir)
            report_dir = os.path.join(tmp_dir, "model_evaluation")

            payload = run_experiment_report(
                harmonized_parquet_path=parquet_path,
                macro_lookup_path=macro_lookup_path,
                output_dir=report_dir,
                k_values=(1, 3),
            )

            expected_files = {
                "hyperparameter_results.csv",
                "independent_variable_summary.csv",
                "dependent_variable_summary.csv",
                "target_transformation_results.csv",
                "hybrid_distance_results.csv",
                "experiment_report.md",
                "experiment_report.json",
                "hyperparameter_trends.png",
                "model_progress.png",
                "variable_effects.png",
                "target_transformation_comparison.png",
            }
            self.assertTrue(expected_files.issubset(set(os.listdir(report_dir))))
            self.assertEqual(payload["config"]["independent_variable_dimensions"], 53)
            self.assertEqual(payload["config"]["dependent_variable"], "target_rate")
            self.assertIn("best_log_configuration", payload)
            self.assertIn("best_hybrid_configuration", payload)
            self.assertEqual(payload["target_transformation"]["log"], "log1p")
            self.assertEqual(payload["target_transformation"]["inverse"], "expm1")
            self.assertEqual(len(pd.read_csv(os.path.join(report_dir, "hyperparameter_results.csv"))), 2)
            self.assertEqual(len(pd.read_csv(os.path.join(report_dir, "target_transformation_results.csv"))), 2)
            self.assertEqual(len(pd.read_csv(os.path.join(report_dir, "hybrid_distance_results.csv"))), 2)
            report_text = Path(report_dir, "experiment_report.md").read_text(encoding="utf-8")
            self.assertIn("Hyperparameter results", report_text)
            self.assertIn("Raw versus log1p target comparison", report_text)
            self.assertIn("Hybrid-distance tuning results", report_text)


if __name__ == "__main__":
    unittest.main()

