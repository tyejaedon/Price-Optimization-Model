"""Small synthetic job budgets only; no local ignored data needed in CI."""

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from src.macro_arbitrage import ContinuousMetadataNormalizer
from src.nlp_pipeline import TextFeatureReducer
from src.svd_dimension_benchmark import PREVIOUSLY_OPENED_DATASET_SHA256
from src.svd_rolling_benchmark import (
    _bounds, _paired_uncertainty, _population, _validation_vectors, _window, run_rolling_benchmark,
)
from src.train_pipeline import load_harmonized_parquet
from tests.test_train_pipeline import TrainPipelineTests


class SvdRollingBenchmarkTests(unittest.TestCase):
    windows = (("2025-02-10T00:00:00+00:00", "2025-02-11T00:00:00+00:00"),
               ("2025-02-11T00:00:00+00:00", "2025-02-12T00:00:00+00:00"))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.macro, parquet = TrainPipelineTests()._write_input_artifacts(self.temp.name)
        self.parquet = Path(parquet)
        frame = pd.read_parquet(self.parquet)
        frame["source_dataset"] = "upwork_jobs"
        frame["mentor_country_iso2"] = "KE"
        frame["client_country_iso2"] = "KE"
        frame["bilateral_arbitrage_factor"] = 1.0
        frame["observation_timestamp_utc"] = [
            ("2025-02-08T12:00:00+00:00", "2025-02-09T12:00:00+00:00",
             "2025-02-10T12:00:00+00:00", "2025-02-11T12:00:00+00:00",
             "2025-02-12T12:00:00+00:00")[i % 5] for i in range(len(frame))
        ]
        frame.to_parquet(self.parquet, index=False)

    def test_no_reopening_known_oot_window_and_validated_boundaries(self):
        with self.assertRaisesRegex(ValueError, "#93 snapshot"):
            _bounds((("2024-02-19T00:00:00+00:00", "2024-02-20T00:00:00+00:00"),
                     ("2024-02-20T00:00:00+00:00", "2024-02-21T00:00:00+00:00")),
                    PREVIOUSLY_OPENED_DATASET_SHA256)
        for windows in (
            (("2025-02-08", "2025-02-09"), ("2025-02-09", "2025-02-10")),
            (("2025-02-08T00:00:00Z", "2025-02-09T00:00:00Z"),
             ("2025-02-10T00:00:00Z", "2025-02-11T00:00:00Z")),
        ):
            with self.assertRaisesRegex(ValueError, "contiguous.*timezone-aware"):
                _bounds(windows, "synthetic")

    def test_population_excludes_future_labels_and_purges_descriptions(self):
        frame = load_harmonized_parquet(str(self.parquet))
        future = frame.observation_timestamp_utc.eq("2025-02-12T12:00:00+00:00")
        jobs, original = _population(frame, pd.Timestamp(self.windows[-1][1]))
        altered = frame.copy()
        altered.loc[future, "harmonized_hourly_rate"] = 999999.0
        again, provenance = _population(altered, pd.Timestamp(self.windows[-1][1]))
        pd.testing.assert_frame_equal(jobs, again)
        self.assertEqual(original, provenance)
        self.assertTrue(provenance["future_rows_excluded_before_rate_inspection"])
        first = jobs.iloc[0]
        duplicate = frame.copy()
        index = duplicate.index[duplicate.observation_timestamp_utc.eq("2025-02-11T12:00:00+00:00")][0]
        duplicate.loc[index, "raw_description"] = first.raw_description
        purged, counts = _population(duplicate, pd.Timestamp(self.windows[-1][1]))
        self.assertEqual(counts["excluded_repeated_descriptions"], 1)
        self.assertEqual(len(purged), len(jobs) - 1)
        split = _window(purged, *(_bounds(self.windows, "synthetic")[-1]))
        self.assertFalse(set(split.train.record_id) & set(split.validation.record_id))
        self.assertLess(pd.Timestamp(split.train.observation_timestamp_utc.max()).timestamp(),
                        pd.Timestamp(split.validation.observation_timestamp_utc.min()).timestamp())

    def test_day_block_uncertainty_is_paired_and_reproducible(self):
        pairs = [(np.array([10.]), np.array([11.]), np.array([13.]), ["2025-02-10"]),
                 (np.array([20.]), np.array([19.]), np.array([18.]), ["2025-02-11"])]
        result = _paired_uncertainty(pairs, 42, repetitions=50)
        self.assertEqual(result, _paired_uncertainty(pairs, 42, repetitions=50))
        self.assertEqual(result["mae_delta_vs_50d_kes"], -1.5)
        self.assertEqual(result["calendar_days"], 2)
        self.assertEqual(result["validation_windows_with_lower_mae"], 2)
        self.assertLess(result["mae_delta_95pct_day_block_bootstrap_kes"][1], 0)
        with self.assertRaisesRegex(ValueError, "aligned"):
            _paired_uncertainty([(np.array([1.]), np.array([1., 2.]), np.array([1.]), ["2025-02-10"])], 42)

    def test_validation_coordinates_recalculate_live_country_factor(self):
        frame = load_harmonized_parquet(str(self.parquet))
        jobs, _ = _population(frame, pd.Timestamp(self.windows[-1][1]))
        split = _window(jobs, *_bounds(self.windows, "synthetic")[0])
        reducer = TextFeatureReducer(n_components=25)
        reducer.fit_transform(split.train.raw_description.tolist())
        normalizer = ContinuousMetadataNormalizer(self.macro)
        normalizer.fit(cast(list[dict[str, Any]], split.train.to_dict(orient="records")))
        changed = split.validation.assign(bilateral_arbitrage_factor=1.123456)
        live = _validation_vectors(reducer, normalizer, changed, 25)
        self.assertEqual(live.shape, (36, 28))
        np.testing.assert_array_equal(live[:, -3:], _validation_vectors(reducer, normalizer, split.validation, 25)[:, -3:])
        self.assertFalse(np.allclose(live[:, -3], normalizer.transform(
            cast(list[dict[str, Any]], changed.to_dict(orient="records")))[:, 0]))

    def test_two_window_two_seed_aggregate_only_run(self):
        report_dir = self.root / "rolling"
        report = run_rolling_benchmark(str(self.parquet), self.macro, "synthetic-v1", str(report_dir),
                                       windows=self.windows, dimensions=(25, 50), seeds=(42, 7), samples=2)
        self.assertEqual(len(report["results"]), 4)
        self.assertEqual(report["split_rows"], [{"train": 72, "validation": 36},
                                                {"train": 108, "validation": 36}])
        self.assertIn("NEVER scored", report["test_policy"])
        self.assertTrue((report_dir / "protocol_frozen.json").is_file())
        saved = json.loads((report_dir / "benchmark.json").read_text())
        self.assertTrue(all("mae" in row["candidates"][0]["validation"] for row in saved["results"]))
        self.assertEqual(saved["paired_vs_50d"]["42"]["25"]["matched_jobs"], 72)
        self.assertEqual(saved["paired_vs_50d"]["7"]["50"]["mae_delta_vs_50d_kes"], 0.0)
        for row in saved["results"]:
            for candidate in row["candidates"]:
                self.assertEqual(candidate["status"], "ok")
                self.assertTrue(candidate["request_reload_parity"])
                self.assertEqual(candidate["peer_stability_vs_50d"]["requests"], 36)
        self.assertNotIn("test_exploratory", json.dumps(saved))
        self.assertNotIn("raw_description", json.dumps(saved))
        self.assertNotIn("record_id", json.dumps(saved))
        self.assertEqual(sorted(path.name for path in report_dir.iterdir()), ["benchmark.json", "protocol_frozen.json"])
        with self.assertRaisesRegex(ValueError, "empty report directory"):
            run_rolling_benchmark(str(self.parquet), self.macro, "synthetic-v1", str(report_dir),
                                  windows=self.windows, dimensions=(25, 50), seeds=(42,), samples=2)


if __name__ == "__main__":
    unittest.main()
