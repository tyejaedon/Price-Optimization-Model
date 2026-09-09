import os
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.ingest_multisource import build_macro_lookup
from src.train_pipeline import (
    DEFAULT_TRAINING_SUMMARY_ARTIFACT,
    build_stratified_splits,
    evaluate_and_serialize_training,
    load_harmonized_parquet,
    orchestrate_training,
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
            self.assertFalse(payload["has_split_overlap"])

            summary_path = os.path.join(artifact_dir, DEFAULT_TRAINING_SUMMARY_ARTIFACT)
            self.assertTrue(os.path.exists(summary_path))
            self.assertTrue(os.path.exists(os.path.join(artifact_dir, "industry_kdtrees.joblib")))

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


if __name__ == "__main__":
    unittest.main()

