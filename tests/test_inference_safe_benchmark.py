import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.inference_safe_benchmark import Candidate, _split_population, run_benchmark
from src.macro_arbitrage import ContinuousMetadataNormalizer
from src.nlp_pipeline import TextFeatureReducer
from src.train_pipeline import load_harmonized_parquet
from tests.test_train_pipeline import TrainPipelineTests


class InferenceSafeBenchmarkTests(unittest.TestCase):
    validation_cutoff = "2025-01-15T00:00:00+00:00"
    test_cutoff = "2025-02-15T00:00:00+00:00"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        macro, parquet = TrainPipelineTests()._write_input_artifacts(self.temp.name)
        self.macro = macro
        self.parquet = Path(parquet)
        frame = pd.read_parquet(self.parquet)
        frame["source_dataset"] = "upwork_jobs"
        frame["mentor_country_iso2"] = "KE"
        frame["client_country_iso2"] = "KE"
        # Keep synthetic offline bilateral metadata identical to the live query.
        frame["bilateral_arbitrage_factor"] = 1.0
        frame["observation_timestamp_utc"] = [
            ("2025-01-01T00:00:00+00:00", "2025-02-01T00:00:00+00:00", "2025-03-01T00:00:00+00:00")[i % 3]
            for i in range(len(frame))
        ]
        frame.loc[frame.index % 3 == 1, "raw_description"] += " validationonlyword"
        frame.loc[frame.index % 3 == 2, "raw_description"] += " testonlyword"
        frame.loc[frame.index % 3 == 1, "market_saturation_score"] = 999
        frame.to_parquet(self.parquet, index=False)

    def _run(self, name="run"):
        return run_benchmark(
            str(self.parquet), self.macro, self.validation_cutoff, self.test_cutoff,
            "synthetic-budget-v1", str(self.root / name),
            candidates=(Candidate("baseline_53d"), Candidate("metadata_half_53d", metadata_weight=0.5)),
            samples=2,
        )

    def test_chronology_population_group_purge_and_missing_times(self):
        frame = pd.read_parquet(self.parquet)
        frame.loc[1, "raw_description"] = frame.loc[0, "raw_description"]
        frame.loc[2, "source_dataset"] = "upwork_data_scientists"
        frame.loc[3, "harmonized_hourly_rate"] = 499.0
        frame.to_parquet(self.parquet, index=False)
        splits, provenance = _split_population(
            load_harmonized_parquet(str(self.parquet)), self.validation_cutoff, self.test_cutoff,
        )
        self.assertEqual(provenance["excluded_other_sources"], 1)
        self.assertEqual(provenance["excluded_invalid_or_out_of_bounds_post_arbitrage"], 1)
        self.assertEqual(provenance["excluded_cross_split_or_repeated_descriptions"]["validation"], 1)
        self.assertTrue(splits.train.observation_timestamp_utc.max() < splits.validation.observation_timestamp_utc.min())
        self.assertTrue(splits.validation.observation_timestamp_utc.max() < splits.test.observation_timestamp_utc.min())
        for left, right in ((splits.train, splits.validation), (splits.train, splits.test), (splits.validation, splits.test)):
            self.assertFalse(set(left.record_id) & set(right.record_id))
            self.assertFalse(set(left.raw_description.str.lower()) & set(right.raw_description.str.lower()))
        broken = pd.read_parquet(self.parquet)
        broken.loc[0, "observation_timestamp_utc"] = None
        broken.to_parquet(self.parquet, index=False)
        with self.assertRaisesRegex(ValueError, "Missing observation"):
            self._run("missing")
        broken.loc[0, "observation_timestamp_utc"] = "2025-01-01"
        broken.to_parquet(self.parquet, index=False)
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            self._run("naive")

    def test_reloaded_request_parity_train_only_fitting_and_test_not_used_for_selection(self):
        report = self._run()
        self.assertEqual(report["status"], "research_only_no_promotion")
        self.assertEqual(report["protocol"]["split_rows"], {"train": 60, "validation": 60, "test": 60})
        self.assertTrue((self.root / "run" / "selection_frozen.json").exists())
        for result in report["results"][1:]:
            self.assertTrue(result["reload_prediction_parity"])
            self.assertTrue(result["request_coordinate_parity"])
            self.assertEqual(result["warmed_query_samples"], 2)
            self.assertEqual(len(result["validation_per_industry"]), 3)
            if result["name"] in {"baseline_53d", report["selected_by_validation"]}:
                self.assertEqual(len(result["test_per_industry"]), 3)
            else:
                self.assertNotIn("test_per_industry", result)
            self.assertEqual(result["settings"]["requested_text_dimensions"], 50)
            self.assertGreater(result["artifact_bytes"], 0)
        reducer = TextFeatureReducer.load_artifacts(str(self.root / "run" / "baseline_53d"))
        self.assertNotIn("validationonlyword", reducer.vectorizer.vocabulary_)
        self.assertNotIn("testonlyword", reducer.vectorizer.vocabulary_)
        scaler = ContinuousMetadataNormalizer.load_artifacts(
            str(self.root / "run" / "baseline_53d"),
            macro_lookup_path=str(self.root / "run" / "baseline_53d" / "macro_lookup_table.json"),
        )
        self.assertLess(max(scaler.scaler.data_max_), 999)
        self.assertTrue((self.root / "run" / "benchmark.json").exists())
        config = json.loads((self.root / "run" / "metadata_half_53d" / "inference_config.json").read_text())
        self.assertEqual(config["metadata_features"], [
            "bilateral_arbitrage_factor", "market_saturation_score", "industry_relative_density",
        ])
        self.assertEqual(config["metadata_weight"], 0.5)

        changed = pd.read_parquet(self.parquet)
        changed.loc[changed.index % 3 == 2, "harmonized_hourly_rate"] = np.linspace(500, 35000, 60)
        changed["target_rate"] = 999999.0  # untrusted pre-existing target must not drive an OOT benchmark
        changed.to_parquet(self.parquet, index=False)
        altered = self._run("altered")
        self.assertEqual(report["selected_by_validation"], altered["selected_by_validation"])
        for original, repeated in zip(report["results"], altered["results"]):
            self.assertEqual(original["validation"], repeated["validation"])
        self.assertNotEqual(report["results"][0]["test"], altered["results"][0]["test"])
        self.assertNotEqual(report["dataset_sha256"], altered["dataset_sha256"])
        self.assertTrue(all(value["promotion_status"] != "promoted" for value in report["results"]))

    def test_requires_prespecified_cutoffs_version_and_empty_output(self):
        with self.assertRaisesRegex(ValueError, "dataset_version"):
            run_benchmark(str(self.parquet), self.macro, self.validation_cutoff, self.test_cutoff, "")
        for first, second in (("2025-01-01", self.test_cutoff), (self.test_cutoff, self.validation_cutoff)):
            with self.subTest(first=first), self.assertRaisesRegex(ValueError, "cutoffs"):
                run_benchmark(str(self.parquet), self.macro, first, second, "synthetic-v1")
        self._run()
        with self.assertRaisesRegex(ValueError, "empty report directory"):
            self._run()


if __name__ == "__main__":
    unittest.main()
