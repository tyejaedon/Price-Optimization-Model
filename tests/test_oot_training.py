import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.ingest_multisource import build_macro_lookup
from src.macro_arbitrage import ContinuousMetadataNormalizer
from src.nlp_pipeline import TextFeatureReducer
from src.spatial_engine import DomainPartitionedKDTreeIndexer
from src.train_pipeline import build_chronological_splits, evaluate_chronological_oot, load_harmonized_parquet
from tests.test_train_pipeline import TrainPipelineTests


class OotTrainingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        fixture = Path(__file__).resolve().parent / "fixtures" / "raw"
        self.macro = self.root / "macro.json"
        build_macro_lookup(str(fixture), str(self.macro))
        self.parquet = self.root / "input.parquet"
        frame = TrainPipelineTests()._build_synthetic_harmonized_frame()
        frame["observation_timestamp_utc"] = [
            "2025-03-01T00:00:00+00:00" if i % 7 == 0 else "2025-01-01T00:00:00+00:00"
            for i in range(len(frame))
        ]
        frame.to_parquet(self.parquet, index=False)
        self.cutoff = "2025-02-01T00:00:00+00:00"
        self.out = self.root / "model"

    def _run(self):
        return evaluate_chronological_oot(
            str(self.parquet), str(self.macro), self.cutoff, str(self.out), "synthetic-v1",
        )

    def test_duplicate_timestamps_stay_together_and_order_is_strict(self):
        splits = build_chronological_splits(load_harmonized_parquet(str(self.parquet)), self.cutoff)
        self.assertTrue(pd.Timestamp(splits.train.observation_timestamp_utc.max()) < pd.Timestamp(splits.test.observation_timestamp_utc.min()))
        self.assertFalse(set(splits.train.record_id) & set(splits.test.record_id))
        frame = pd.read_parquet(self.parquet)
        frame.loc[:5, "observation_timestamp_utc"] = self.cutoff
        frame.to_parquet(self.parquet, index=False)
        splits = build_chronological_splits(load_harmonized_parquet(str(self.parquet)), self.cutoff)
        self.assertTrue(set(range(6)).issubset(set(splits.train.record_id)))

    def test_rejects_missing_naive_or_insufficient_timestamps_and_missing_version(self):
        frame = pd.read_parquet(self.parquet)
        with self.assertRaisesRegex(ValueError, "dataset_version"):
            evaluate_chronological_oot(str(self.parquet), str(self.macro), self.cutoff, str(self.out))
        for value, message in [(None, "Missing observation"), ("2025-01-01", "timezone-aware")]:
            broken = frame.copy()
            broken.loc[0, "observation_timestamp_utc"] = value
            broken.to_parquet(self.parquet, index=False)
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, message):
                self._run()
        frame.drop(columns=["observation_timestamp_utc"]).to_parquet(self.parquet, index=False)
        with self.assertRaisesRegex(ValueError, "cannot support chronological OOT"):
            self._run()
        frame["observation_timestamp_utc"] = "2025-01-01T00:00:00+00:00"
        frame.to_parquet(self.parquet, index=False)
        with self.assertRaisesRegex(ValueError, "strictly later"):
            self._run()
        self.assertFalse(self.out.exists())

    def test_train_only_transform_and_indexer_and_reload(self):
        frame = pd.read_parquet(self.parquet)
        late = frame.observation_timestamp_utc.str.startswith("2025-03")
        frame.loc[late, "raw_description"] += " futureonlytoken"
        frame.loc[late, "market_saturation_score"] = 999.0
        frame.loc[late, "industry_relative_density"] = 999.0
        frame.to_parquet(self.parquet, index=False)
        report = self._run()
        self.assertEqual(report["evaluation_protocol"], "chronological_out_of_time")
        self.assertEqual(report["quality_gate"]["metric"], "test_r2")
        self.assertTrue(report["quality_gate"]["passed"])
        self.assertEqual(report["split_rows"], {"train": int((~late).sum()), "test": int(late.sum())})
        self.assertEqual(report, json.loads((self.out / "training_summary.json").read_text()))
        reducer = TextFeatureReducer.load_artifacts(str(self.out))
        self.assertNotIn("futureonlytoken", reducer.vectorizer.vocabulary_)
        scaler = ContinuousMetadataNormalizer.load_artifacts(str(self.out), macro_lookup_path=str(self.out / "macro_lookup_table.json"))
        self.assertLess(scaler.scaler.data_max_.max(), 999.0)
        self.assertTrue(all(0 <= value <= 1 for value in json.loads((self.out / "inference_config.json").read_text())["partition_density"].values()))
        index = DomainPartitionedKDTreeIndexer.load_artifacts(str(self.out))
        train_ids = set(np.flatnonzero(~late).tolist())
        self.assertEqual(set().union(*(set(indices) for indices in index.partition_row_indices.values())), train_ids)
        self.assertEqual(sum(index.partition_counts.values()), int((~late).sum()))

    def test_rate_bounds_and_low_volume_partition_fallback(self):
        frame = pd.read_parquet(self.parquet)
        frame.loc[1, "harmonized_hourly_rate"] = 499.0
        frame.loc[2, "harmonized_hourly_rate"] = 35001.0
        frame.loc[0, "industry_partition"] = "mobile"  # test-only partition: fallback absent -> diagnostic
        frame.to_parquet(self.parquet, index=False)
        with self.assertRaisesRegex(KeyError, "No partition"):
            self._run()
        self.assertFalse(self.out.exists())
        frame.loc[0, "industry_partition"] = "data_ai"
        frame.to_parquet(self.parquet, index=False)
        report = self._run()
        self.assertEqual(report["rate_policy"]["excluded_out_of_bounds_or_invalid"], 2)

    def test_ignores_untrusted_target_rate_override(self):
        frame = pd.read_parquet(self.parquet)
        frame["target_rate"] = 900000.0
        frame.to_parquet(self.parquet, index=False)
        report = self._run()
        self.assertEqual(report["rate_policy"]["excluded_out_of_bounds_or_invalid"], 0)
        self.assertTrue(report["quality_gate"]["passed"])

    def test_gate_uses_future_raw_labels_and_never_exports_failure(self):
        frame = pd.read_parquet(self.parquet)
        future = frame.observation_timestamp_utc.str.startswith("2025-03")
        frame.loc[future, "harmonized_hourly_rate"] = np.linspace(500.0, 35000.0, future.sum())
        frame.to_parquet(self.parquet, index=False)
        with self.assertRaisesRegex(RuntimeError, "Quality gate failed.*acquire reliable labels"):
            self._run()
        report = json.loads((self.out / "training_summary.json").read_text())
        self.assertLess(report["test"]["r2"], 0.75)
        self.assertFalse(report["quality_gate"]["passed"])
        self.assertFalse((self.out / "industry_kdtrees.joblib").exists())
        self.assertFalse((self.out / "tfidf_vectorizer.joblib").exists())


if __name__ == "__main__":
    unittest.main()
