"""Synthetic-only checks for the #120 validation protocol."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.nlp.nlp_pipeline import TextFeatureReducer
from src.benchmarks.text_sensitivity_benchmark import CANDIDATES, run_benchmark
from tests.training.test_train_pipeline import TrainPipelineTests


class TextSensitivityBenchmarkTests(unittest.TestCase):
    first = "2025-01-15T00:00:00+00:00"
    second = "2025-02-15T00:00:00+00:00"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        macro, parquet = TrainPipelineTests()._write_input_artifacts(self.temp.name)
        self.macro, self.parquet = Path(macro), Path(parquet)
        frame = pd.read_parquet(self.parquet)
        frame["source_dataset"] = "upwork_jobs"
        frame["mentor_country_iso2"] = "KE"
        frame["client_country_iso2"] = "KE"
        frame["bilateral_arbitrage_factor"] = 1.0
        frame["observation_timestamp_utc"] = [
            ("2025-01-01T00:00:00+00:00", "2025-02-01T00:00:00+00:00",
             "2025-03-01T00:00:00+00:00")[i % 3] for i in range(len(frame))
        ]
        frame.loc[frame.index % 3 == 1, "raw_description"] += " validationonlyword"
        frame.loc[frame.index % 3 == 2, "raw_description"] += " testonlyword"
        frame.loc[1, "raw_description"] = "ultraxenonium qryptomorphism"
        frame.loc[frame.index % 3 == 1, "market_saturation_score"] = 999.0
        frame.to_parquet(self.parquet, index=False)

    @staticmethod
    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def run_research(self, name: str):
        return run_benchmark(str(self.parquet), str(self.macro), self.first, self.second,
                             "synthetic-protocol-only", self.digest(self.parquet), self.digest(self.macro),
                             str(self.root / name), samples=3)

    def test_one_variable_candidates_diagnostics_and_request_replay(self):
        report = self.run_research("first")
        frozen = json.loads((self.root / "first" / "protocol_frozen.json").read_text())
        self.assertEqual(frozen["results"], [])
        self.assertEqual(frozen["protocol"]["split_rows"], {"train": 60, "validation": 60, "test": 60})
        self.assertEqual([c["name"] for c in frozen["candidates_predeclared"]], [c.name for c in CANDIDATES])
        self.assertNotIn("test_exploratory", (self.root / "first" / "benchmark.json").read_text())
        for row in report["results"]:
            self.assertEqual(row["status"], "ok", row.get("failure"))
            self.assertEqual(row["vocabulary_size"],
                             len(TextFeatureReducer.load_artifacts(str(self.root / "first" / row["name"])).vectorizer.vocabulary_))
            self.assertEqual(row["validation_text"]["rows"], 60)
            self.assertGreater(row["validation_text"]["oov_ngrams"], 0)
            self.assertGreaterEqual(row["validation_text"]["zero_tfidf_rows"], 1)
            self.assertGreaterEqual(row["validation_text"]["zero_svd_rows"], 1)
            self.assertEqual(row["train_text"]["oov_ngrams"], 0)
            self.assertEqual(row["peer_stability_vs_baseline"]["requests"], 60)
            self.assertEqual(sum(row["train_industry_counts"].values()), 60)
            self.assertEqual(sum(group["rows"] for group in row["validation_per_industry"]), 60)
            self.assertEqual(len(row["validation_per_industry"]), 3)
            self.assertEqual(row["request_reload_parity"], True)
            self.assertEqual(row["profile_samples"], 3)
            self.assertGreater(row["artifact_bytes"], 0)
            self.assertGreater(row["training_python_peak_bytes"], 0)
            self.assertGreater(row["warm_local_inference_p95_ms"], 0)
            self.assertIn("mae", row["validation"])
            reducer = TextFeatureReducer.load_artifacts(str(self.root / "first" / row["name"]))
            self.assertEqual(reducer.tfidf_norm, row["settings"]["tfidf_norm"])
            self.assertEqual(reducer.normalize_output, row["settings"]["normalize_output"])
            self.assertEqual(reducer.reducer.n_components, 50)
            self.assertNotIn("validationonlyword", reducer.vectorizer.vocabulary_)
            self.assertNotIn("testonlyword", reducer.vectorizer.vocabulary_)
        self.assertEqual(report["results"][0]["peer_stability_vs_baseline"]["mean_top5_jaccard"], 1.0)
        self.assertFalse(list((self.root / "first").glob("*/model_manifest.json")))
        with self.assertRaisesRegex(ValueError, "empty report directory"):
            self.run_research("first")

    def test_test_outcomes_cannot_affect_validation_and_hash_is_frozen(self):
        original = self.run_research("original")
        edited = pd.read_parquet(self.parquet)
        edited.loc[edited.index % 3 == 2, "harmonized_hourly_rate"] = np.linspace(600, 33000, 60)
        edited["target_rate"] = 999999.0
        edited.to_parquet(self.parquet, index=False)
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            run_benchmark(str(self.parquet), str(self.macro), self.first, self.second,
                          "synthetic-protocol-only", original["dataset_sha256"], self.digest(self.macro),
                          str(self.root / "mismatch"), samples=2)
        self.assertFalse((self.root / "mismatch").exists())
        changed = self.run_research("different_hash")
        for left, right in zip(original["results"], changed["results"]):
            self.assertEqual(left["validation"], right["validation"])
            self.assertEqual(left["peer_stability_vs_baseline"], right["peer_stability_vs_baseline"])
        self.assertNotEqual(original["dataset_sha256"], changed["dataset_sha256"])

    def test_invalid_cutoffs_and_missing_inputs_fail_before_scores(self):
        with self.assertRaisesRegex(ValueError, "cutoffs"):
            run_benchmark(str(self.parquet), str(self.macro), "2025-01-15", self.second,
                          "synthetic", self.digest(self.parquet), self.digest(self.macro),
                          str(self.root / "bad_cutoff"))
        with self.assertRaises(FileNotFoundError):
            run_benchmark(str(self.root / "no-parquet"), str(self.macro), self.first, self.second,
                          "synthetic", "0" * 64, self.digest(self.macro), str(self.root / "missing"))
        with self.assertRaisesRegex(ValueError, "tfidf_norm"):
            TextFeatureReducer(tfidf_norm="none")

    def test_tfidf_norm_roundtrips_without_changing_old_l2_artifacts(self):
        texts = ["Build cloud architecture with Python analytics",
                 "Design software architecture and security analytics",
                 "Develop cloud software and security engineering"]
        for norm in ("l1", "l2"):
            reducer = TextFeatureReducer(n_components=2, tfidf_norm=norm)
            reducer.fit_transform(texts)
            folder = self.root / norm
            reducer.save_artifacts(str(folder))
            restored = TextFeatureReducer.load_artifacts(str(folder))
            self.assertEqual(restored.tfidf_norm, norm)
            np.testing.assert_allclose(restored.transform(["Cloud analytics architecture"]),
                                       reducer.transform(["Cloud analytics architecture"]))
        metadata = self.root / "l2" / "nlp_reducer_metadata.json"
        legacy = json.loads(metadata.read_text())
        legacy.pop("tfidf_norm")
        metadata.write_text(json.dumps(legacy))
        self.assertEqual(TextFeatureReducer.load_artifacts(str(self.root / "l2")).tfidf_norm, "l2")


if __name__ == "__main__":
    unittest.main()
