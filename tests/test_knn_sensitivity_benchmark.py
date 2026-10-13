"""Synthetic-only checks for the non-promoting #121 research runner."""

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.knn_sensitivity_benchmark import _peer_changes, run_benchmark
from src.nlp_pipeline import TextFeatureReducer
from src.spatial_engine import DomainPartitionedKDTreeIndexer
from tests.test_train_pipeline import TrainPipelineTests


class KnnSensitivityTests(unittest.TestCase):
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
        frame.to_parquet(self.parquet, index=False)

    def run_research(self, output):
        return run_benchmark(str(self.parquet), self.macro, "2025-01-15T00:00:00+00:00",
                             "2025-02-15T00:00:00+00:00", "synthetic-only",
                             str(self.root / output), samples=2)

    def test_frozen_single_variable_series_and_validation_only(self):
        report = self.run_research("run")
        self.assertEqual(report["protocol"]["split_rows"], {"train": 60, "validation": 60, "test": 60})
        self.assertEqual(len(report["results"]), 5)
        self.assertTrue((self.root / "run" / "protocol_frozen.json").exists())
        frozen = json.loads((self.root / "run" / "protocol_frozen.json").read_text())
        self.assertNotIn("fit", frozen)
        self.assertNotIn("results", frozen["results"][0] if frozen["results"] else {})
        self.assertEqual([entry["status"] for entry in report["results"]], ["ok"] * 5)
        self.assertTrue(all(entry["reload_parity"] for entry in report["results"]))
        self.assertTrue(all(entry["profile_samples"] == 2 for entry in report["results"]))
        self.assertTrue(all(np.isfinite(entry["validation"]["rmse"]) for entry in report["results"]))
        self.assertTrue(all(len(entry["validation_per_industry"]) == 3 for entry in report["results"]))
        self.assertTrue(all(entry["warm_local_query_p95_ms"] > 0 for entry in report["results"]))
        self.assertEqual(report["results"][0]["vs_k5_epsilon_1e-6"]["mean_peer_jaccard"], 1)
        self.assertEqual(report["results"][3]["epsilon"], 1e-8)
        self.assertEqual(report["results"][4]["epsilon"], 1e-4)
        self.assertNotIn("test", json.dumps(report["results"]))
        self.assertEqual(len(report["zero_distance_synthetic_probe"]), 5)
        self.assertTrue(all(probe["zero_distance_peers"] == 2
                            for probe in report["zero_distance_synthetic_probe"]))
        reducer = TextFeatureReducer.load_artifacts(str(self.root / "run" / "research_artifacts"))
        self.assertNotIn("validationonlyword", reducer.vectorizer.vocabulary_)
        self.assertNotIn("testonlyword", reducer.vectorizer.vocabulary_)
        with self.assertRaisesRegex(ValueError, "empty report directory"):
            self.run_research("run")

    def test_test_labels_never_affect_validation(self):
        original = self.run_research("first")
        changed = pd.read_parquet(self.parquet)
        changed.loc[changed.index % 3 == 2, "harmonized_hourly_rate"] += 600
        changed.to_parquet(self.parquet, index=False)
        later = self.run_research("later")
        for base, trial in zip(original["results"], later["results"]):
            self.assertEqual(base["validation"], trial["validation"])
            self.assertEqual(base["vs_k5_epsilon_1e-6"], trial["vs_k5_epsilon_1e-6"])
        self.assertNotEqual(original["dataset_sha256"], later["dataset_sha256"])

    def test_parameter_guards_and_exact_match(self):
        kwargs = (str(self.parquet), self.macro, "2025-01-15T00:00:00+00:00",
                  "2025-02-15T00:00:00+00:00", "synthetic", str(self.root / "bad"))
        with self.assertRaisesRegex(ValueError, "vary only"):
            run_benchmark(*kwargs, k_series=((5, 1e-6), (3, 1e-4)))
        with self.assertRaisesRegex(ValueError, "vary only"):
            run_benchmark(*kwargs, epsilon_series=((5, 1e-6), (3, 1e-4)))
        vectors = np.zeros((5, 53))
        vectors[2:, 0] = [1, 2, 3]
        engine = DomainPartitionedKDTreeIndexer()
        engine.fit(vectors, ["general_tech"] * 5, verified_rates=[100, 300, 500, 600, 700])
        for epsilon in (1e-8, 1e-6, 1e-4):
            result = engine.predict_base_rate(np.zeros(53), "general_tech", k=5, epsilon=epsilon)
            self.assertTrue(np.isfinite(result["base_predicted_rate"]))
            self.assertEqual(result["nearest_neighbors"][0]["distance"], 0)
            self.assertAlmostEqual(sum(peer["idw_weight"] for peer in result["nearest_neighbors"]), 1, places=5)
        # The runner never emits peer IDs, even when metrics compare different k.
        baseline = engine.predict_base_rate(np.zeros(53), "general_tech", k=5)
        trial = engine.predict_base_rate(np.zeros(53), "general_tech", k=3)
        baseline["corridor_width"] = 100
        trial["corridor_width"] = 120
        self.assertNotIn("peer_index", _peer_changes([baseline], [trial]))

    def test_higher_k_can_change_fallback_routing(self):
        vectors = np.zeros((16, 53))
        vectors[:, 0] = np.arange(16, dtype=float)
        index = DomainPartitionedKDTreeIndexer()
        index.fit(vectors, ["data_ai"] * 6 + ["general_tech"] * 10,
                  verified_rates=[100.0] * 16)
        baseline = index.predict_base_rate(vectors[0], "data_ai", k=5)
        larger_k = index.predict_base_rate(vectors[0], "data_ai", k=10)
        self.assertFalse(baseline["fallback_triggered"])
        self.assertTrue(larger_k["fallback_triggered"])
        self.assertEqual(larger_k["routed_partition"], "general_tech")
        self.assertEqual(larger_k["k_neighbors_used"], 10)


if __name__ == "__main__":
    unittest.main()
