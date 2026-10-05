import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from src.ingest_multisource import build_macro_lookup
from src.macro_arbitrage import DEFAULT_FEATURE_NAMES, ContinuousMetadataNormalizer
from src.nlp_pipeline import TextFeatureReducer, sanitize_many
from src.train_pipeline import load_harmonized_parquet
from src.validation_diagnostics import (
    _oot_availability,
    _segment_errors,
    build_description_group_splits,
    compute_confidence_interval,
    detect_duplicate_records,
    run_industry_error_diagnostics,
)
from tests.test_train_pipeline import TrainPipelineTests


class ValidationDiagnosticsTests(unittest.TestCase):
    def test_duplicate_detection_reports_normalized_duplicate_rows(self) -> None:
        frame = pd.DataFrame(
            [
                {"raw_description": " Senior Python Mentor ", "target_rate": 2500.0},
                {"raw_description": "senior   python mentor", "target_rate": 2500.0},
                {"raw_description": "Different mentor", "target_rate": 3000.0},
            ]
        )

        result = detect_duplicate_records(frame)

        self.assertEqual(result["duplicate_rows"], 2)
        self.assertEqual(result["duplicate_groups"], 1)
        self.assertGreater(result["duplicate_rate"], 0.0)

    def test_confidence_interval_is_finite_and_deterministic(self) -> None:
        result = compute_confidence_interval([0.5, 0.6, 0.7, 0.8])

        self.assertEqual(result["samples"], 4)
        self.assertAlmostEqual(result["mean"], 0.65, places=6)
        self.assertLess(result["ci_lower"], result["mean"])
        self.assertGreater(result["ci_upper"], result["mean"])
        self.assertTrue(all(pd.notna(value) for value in result.values() if isinstance(value, (int, float))))

    def test_description_groups_and_ids_are_disjoint_even_with_conflicting_rates(self) -> None:
        frame = TrainPipelineTests()._build_synthetic_harmonized_frame()
        duplicate = frame.iloc[[0]].copy()
        duplicate["raw_description"] = "  " + str(duplicate.iloc[0]["raw_description"]).upper() + " https://example.org  "
        duplicate["harmonized_hourly_rate"] = 30000.0
        frame = pd.concat([frame, duplicate], ignore_index=True)
        frame["record_id"] = np.arange(len(frame))
        first = build_description_group_splits(frame, seed=42)
        second = build_description_group_splits(frame, seed=42)
        self.assertEqual(first.train.record_id.tolist(), second.train.record_id.tolist())
        self.assertEqual(sum(len(part) for part in (first.train, first.validation, first.test)), len(frame))
        for column in ("record_id", "raw_description"):
            sets = [
                set(sanitize_many(part[column].tolist())) if column == "raw_description" else set(part[column].tolist())
                for part in (first.train, first.validation, first.test)
            ]
            self.assertFalse(sets[0] & sets[1] or sets[0] & sets[2] or sets[1] & sets[2])
        self.assertTrue(any({0, len(frame) - 1}.issubset(set(part.record_id)) for part in (first.train, first.validation, first.test)))

    def test_sparse_and_constant_label_error_cohorts_are_still_counted(self) -> None:
        metrics = _segment_errors(
            np.array([400.0, 400.0]), np.array([600.0, 6400.0]), np.array([400.0, 400.0]),
            total_squared_error=36040000.0,
        )
        self.assertIsNone(metrics["r2"])
        self.assertEqual(metrics["high_error_rows"], 1)
        self.assertEqual(metrics["out_of_post_arbitrage_bounds_rows"], 2)
        self.assertEqual(metrics["squared_error_share"], 1.0)

    def test_industry_report_is_deterministic_aggregate_only_and_train_fitted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            macro = path / "macro.json"
            parquet = path / "input.parquet"
            build_macro_lookup(str(Path(__file__).parent / "fixtures" / "raw"), str(macro))
            frame = TrainPipelineTests()._build_synthetic_harmonized_frame()
            frame["source_dataset"] = "upwork_jobs"
            frame.loc[:4, "source_dataset"] = "upwork_data_scientists"
            frame["market_saturation_score"] = 999.0
            frame["industry_relative_density"] = 999.0
            frame["harmonized_hourly_rate"] += np.arange(len(frame)) * 5.0
            frame["target_rate"] = -12345.0  # Never use an untrusted target_rate override.
            frame.to_parquet(parquet, index=False)
            prepared = load_harmonized_parquet(str(parquet))
            split = build_description_group_splits(prepared, seed=42)
            fitted_texts = []
            fitted_records = []
            text_fit = TextFeatureReducer.fit_transform
            metadata_fit = ContinuousMetadataNormalizer.fit_transform

            def spy_text(reducer, texts):
                fitted_texts.extend(texts)
                return text_fit(reducer, texts)

            def spy_metadata(normalizer, records):
                fitted_records.extend(records)
                return metadata_fit(normalizer, records)

            with patch.object(TextFeatureReducer, "fit_transform", spy_text), patch.object(
                ContinuousMetadataNormalizer, "fit_transform", spy_metadata,
            ):
                report = run_industry_error_diagnostics(
                    str(parquet), str(macro), str(path / "report"), dataset_version="synthetic-v1",
                    seeds=(42,), n_components=5, k_neighbors=2,
                )
            self.assertEqual(fitted_texts, split.train.raw_description.tolist())
            self.assertEqual(len(fitted_records), len(split.train))
            counts = split.train.industry_partition.value_counts()
            for record in fitted_records:
                self.assertEqual(record["industry_frequency"], int(counts[record["industry_partition"]]))
                self.assertEqual(record["market_saturation_score"], round(counts[record["industry_partition"]] / len(split.train), 6))
                self.assertNotEqual(record["industry_relative_density"], 999.0)
                self.assertEqual(record["target_rate"], record["harmonized_hourly_rate"])
            self.assertFalse(set(DEFAULT_FEATURE_NAMES) & {"target_rate", "hourly_rate", "harmonized_hourly_rate"})

            segments = report["reference_validation_segments"]
            for dimension in ("industry", "source", "source_industry"):
                self.assertEqual(sum(row["population_rows"] for row in segments[dimension]), len(frame))
                self.assertEqual(sum(row["validation_rows"] for row in segments[dimension]), report["reference_split_rows"]["validation"])
                self.assertAlmostEqual(sum(row["errors"]["squared_error_share"] for row in segments[dimension] if row["errors"]), 1.0, places=5)
            self.assertTrue(any(row["sparse_validation"] for row in segments["source"]))
            self.assertEqual(report["oot_evaluation"]["status"], "not_run")
            self.assertEqual(report["oot_evaluation"]["timestamped_rows"], 0)
            self.assertEqual(report["evaluation_protocol"], "exploratory_description_group_disjoint_random_70_15_15")
            self.assertEqual(report["dataset_version"], "synthetic-v1")
            self.assertGreater(report["seed_metrics"][0]["model_validation"]["rmse"], 0)
            self.assertNotIn("test_metrics", report)

            serialized = (path / "report" / "industry_error_diagnostics.json").read_text(encoding="utf-8")
            self.assertEqual(json.loads(serialized), report)
            self.assertNotIn("raw_description", serialized)
            self.assertNotIn(str(frame.iloc[0]["raw_description"]), serialized)
            self.assertNotIn("record_id", serialized)
            second = run_industry_error_diagnostics(
                str(parquet), str(macro), str(path / "second"), dataset_version="synthetic-v1",
                seeds=(42,), n_components=5, k_neighbors=2,
            )
            self.assertEqual(report, second)
            self.assertEqual(serialized, (path / "second" / "industry_error_diagnostics.json").read_text(encoding="utf-8"))

    def test_oot_is_not_claimed_just_because_timestamps_are_present(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            macro = path / "macro.json"
            parquet = path / "input.parquet"
            build_macro_lookup(str(Path(__file__).parent / "fixtures" / "raw"), str(macro))
            frame = TrainPipelineTests()._build_synthetic_harmonized_frame()
            frame["observation_timestamp_utc"] = "2025-01-01T00:00:00+00:00"
            frame.to_parquet(parquet, index=False)
            report = run_industry_error_diagnostics(str(parquet), str(macro), str(path / "report"), seeds=(42,), n_components=5, k_neighbors=2)
            self.assertEqual(report["oot_evaluation"]["timestamped_rows"], len(frame))
            self.assertEqual(report["oot_evaluation"]["status"], "not_run")
            self.assertIn("#81", report["oot_evaluation"]["reason"])

    def test_invalid_harmonized_labels_are_not_silently_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            frame = TrainPipelineTests()._build_synthetic_harmonized_frame()
            frame.loc[0, "harmonized_hourly_rate"] = np.nan
            parquet = path / "input.parquet"
            frame.to_parquet(parquet, index=False)
            with self.assertRaisesRegex(ValueError, "Non-finite harmonized rates"):
                run_industry_error_diagnostics(str(parquet), str(path / "unused_macro.json"), str(path / "report"))
            self.assertFalse((path / "report").exists())

    def test_partial_timestamp_coverage_is_explicit_and_not_oot(self) -> None:
        status = _oot_availability(pd.DataFrame({"observation_timestamp_utc": ["2025-01-01T00:00:00+00:00", None]}))
        self.assertEqual(status["timestamped_rows"], 1)
        self.assertEqual(status["status"], "not_run")
        self.assertIn("1 of 2", status["reason"])


if __name__ == "__main__":
    unittest.main()

