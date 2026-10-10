"""Synthetic records only; #117 results require the ignored dated local corpus."""

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from src.inference_safe_benchmark import _split_population
from src.macro_arbitrage import ContinuousMetadataNormalizer
from src.nlp_pipeline import TextFeatureReducer
from src.svd_dimension_benchmark import _peer_stability, _same_explanation, _vectors, run_benchmark
from src.train_pipeline import load_harmonized_parquet
from tests.test_train_pipeline import TrainPipelineTests


class SvdDimensionBenchmarkTests(unittest.TestCase):
    first = "2025-01-15T00:00:00+00:00"
    second = "2025-02-15T00:00:00+00:00"

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
            ("2025-01-01T00:00:00+00:00", "2025-02-01T00:00:00+00:00", "2025-03-01T00:00:00+00:00")[i % 3]
            for i in range(len(frame))
        ]
        frame.loc[frame.index % 3 == 1, "raw_description"] += " validationonlyword"
        frame.loc[frame.index % 3 == 2, "raw_description"] += " testonlyword"
        frame.loc[frame.index % 3 == 1, "market_saturation_score"] = 999.0
        frame.to_parquet(self.parquet, index=False)

    def run_research(self, directory: str):
        return run_benchmark(str(self.parquet), self.macro, self.first, self.second,
                             "synthetic-not-a-mentor-budget", str(self.root / directory),
                             dimensions=(25, 50), samples=3)

    def test_chronological_sweep_reloads_true_dimensions_and_tracks_peers(self):
        report = self.run_research("first")
        self.assertEqual(report["protocol"]["split_rows"], {"train": 60, "validation": 60, "test": 60})
        self.assertTrue((self.root / "first" / "validation_frozen.json").exists())
        frozen = json.loads((self.root / "first" / "validation_frozen.json").read_text())
        self.assertNotIn("test_exploratory", frozen["results"][0])
        self.assertNotIn("test_exploratory", frozen["category_mean"])
        for result, dimension in zip(report["results"], (25, 50)):
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["hybrid_dimensions"], dimension + 3)
            self.assertTrue(result["request_reload_parity"])
            self.assertEqual(result["peer_stability_vs_50d"]["requests"], 60)
            self.assertEqual(len(result["validation_per_industry"]), 3)
            self.assertEqual(len(result["test_per_industry_exploratory"]), 3)
            self.assertGreater(result["artifact_bytes"], 0)
            self.assertGreater(result["warm_local_inference_p95_ms"], 0)
            reducer = TextFeatureReducer.load_artifacts(str(self.root / "first" / f"svd_{dimension}"))
            self.assertEqual(reducer.reducer.n_components, dimension)
            self.assertNotIn("validationonlyword", reducer.vectorizer.vocabulary_)
            self.assertNotIn("testonlyword", reducer.vectorizer.vocabulary_)
        scaler = ContinuousMetadataNormalizer.load_artifacts(
            str(self.root / "first" / "svd_25"),
            macro_lookup_path=str(self.root / "first" / "svd_25" / "macro_lookup_table.json"))
        self.assertLess(max(scaler.scaler.data_max_), 999)
        base = report["results"][1]["peer_stability_vs_50d"]
        self.assertEqual(base["mean_top5_jaccard"], 1.0)
        self.assertEqual(base["mean_absolute_base_quote_change_kes"], 0.0)

        with self.assertRaisesRegex(ValueError, "empty report directory"):
            self.run_research("first")

    def test_target_fields_do_not_enter_coordinates_or_validation(self):
        split, _ = _split_population(load_harmonized_parquet(str(self.parquet)), self.first, self.second)
        text = TextFeatureReducer(n_components=25)
        text.fit_transform(split.train.raw_description.tolist())
        scaler = ContinuousMetadataNormalizer(self.macro)
        scaler.fit(cast(list[dict[str, Any]], split.train.to_dict(orient="records")))
        original = _vectors(text, scaler, split.validation, 25)
        changed = split.validation.assign(target_rate=999999, hourly_rate=888888,
                                          harmonized_hourly_rate=777777)
        np.testing.assert_array_equal(original, _vectors(text, scaler, changed, 25))
        with self.assertRaisesRegex(ValueError, r"Expected 50\+3"):
            _vectors(text, scaler, split.validation, 50)

        first = self.run_research("initial")
        edited = pd.read_parquet(self.parquet)
        edited.loc[edited.index % 3 == 2, "harmonized_hourly_rate"] += 600.0
        edited["target_rate"] = 999999.0
        edited.to_parquet(self.parquet, index=False)
        second = self.run_research("modified_test_only")
        for original, later in zip(first["results"], second["results"]):
            self.assertEqual(original["validation"], later["validation"])
            self.assertEqual(original["peer_stability_vs_50d"], later["peer_stability_vs_50d"])
            self.assertNotEqual(original["test_exploratory"], later["test_exploratory"])
        self.assertNotEqual(first["dataset_sha256"], second["dataset_sha256"])

    def test_peer_metrics_are_aggregated_without_ids(self):
        baseline = [{"ids": [1, 2], "weights": {1: .75, 2: .25},
                     "similarity": {1: .8, 2: .6}, "fallback": False}]
        trial = [{"ids": [2, 3], "weights": {2: .6, 3: .4},
                  "similarity": {2: .5, 3: .2}, "fallback": True}]
        result = _peer_stability(baseline, trial, np.array([100.]), np.array([120.]))
        self.assertEqual(result["mean_top5_jaccard"], round(1 / 3, 6))
        self.assertEqual(result["mean_absolute_base_quote_change_kes"], 20.0)
        self.assertEqual(result["fallback_mismatch_count"], 1)
        self.assertNotIn("ids", result)

    def test_parity_allows_roundoff_but_rejects_changed_peer_or_quote(self):
        original: dict[str, Any] = {"routed_partition": "data_ai", "fallback_triggered": False,
                    "base_predicted_rate": 5000.0, "nearest_neighbors": [
                        {"peer_index": 1, "verified_rate": 5000.0, "distance": .123456,
                         "idw_weight": .75, "similarity_score": .890123}]}
        near = {**original, "nearest_neighbors": [{**original["nearest_neighbors"][0], "distance": .123457}]}
        self.assertTrue(_same_explanation(original, near))
        self.assertFalse(_same_explanation(original, {**original, "base_predicted_rate": 5001.0}))
        changed = {**original, "nearest_neighbors": [{**original["nearest_neighbors"][0], "peer_index": 2}]}
        self.assertFalse(_same_explanation(original, changed))


if __name__ == "__main__":
    unittest.main()
