"""Synthetic-only tests for #119; no measured mentor-price evidence."""

import json
import shutil
import unittest
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

from src.benchmarks.alpha_sensitivity_benchmark import (
    ALPHAS, _country_coverage, _scenario, run_benchmark,
)
from src.data.ingest_multisource import build_macro_lookup, load_macro_lookup_table, map_country_to_iso2
from src.engine.macro_arbitrage import ContinuousMetadataNormalizer
from src.nlp.nlp_pipeline import TextFeatureReducer
from tests.training.test_train_pipeline import TrainPipelineTests


class AlphaSensitivityTests(unittest.TestCase):
    def setUp(self):
        self.root = Path("reports") / f"test_alpha_119_{uuid.uuid4().hex}"
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root)
        self.macro = self.root / "macro.json"
        build_macro_lookup("tests/fixtures/raw", str(self.macro))
        self.records = load_macro_lookup_table(str(self.macro))
        frame = TrainPipelineTests()._build_synthetic_harmonized_frame()
        frame["source_dataset"] = "upwork_jobs"
        frame["mentor_country_iso2"] = "KE"
        frame["source_country"] = [["Kenya", "India", "not a country",
                                    "India", "not a country", "Kenya"][i % 6]
                                   for i in range(len(frame))]
        frame["client_country_iso2"] = frame["source_country"].map(map_country_to_iso2)
        frame["observation_timestamp_utc"] = [
            ("2024-02-19T00:00:00+00:00", "2024-02-21T00:00:00+00:00",
             "2024-02-23T00:00:00+00:00")[i % 3] for i in range(len(frame))
        ]
        frame = _scenario(frame, self.records, 0.5)
        frame["harmonized_hourly_rate"] = frame["target_rate"]
        frame["arbitrage_alpha"] = 0.5
        self.parquet = self.root / "corpus.parquet"
        frame.to_parquet(self.parquet, index=False)

    def run_research(self, name: str = "run"):
        return run_benchmark(str(self.parquet), str(self.macro), str(self.root / name),
                             samples=2, allow_other_snapshot=True, dataset_version="synthetic-test-not-93")

    def test_sweep_freezes_cohort_recalculates_targets_and_features(self):
        report = self.run_research()
        self.assertEqual(report["snapshot"], "other_snapshot_not_93")
        self.assertEqual(report["predeclared_alphas"], list(ALPHAS))
        self.assertEqual([row["status"] for row in report["results"]], ["ok"] * 5)
        self.assertEqual(report["protocol"]["split_rows"], {"train": 60, "validation": 60, "test": 60})
        self.assertEqual(report["country_coverage"]["validation"]["fallback_events"],
                         {"source_country_unknown_or_missing_to_KE": 30})
        self.assertEqual(report["country_coverage"]["validation"]["country_pairs"],
                         {"KE->IN": 30, "KE->KE": 30})
        self.assertTrue((self.root / "run" / "protocol_frozen.json").exists())
        frozen = json.loads((self.root / "run" / "protocol_frozen.json").read_text())
        self.assertEqual(frozen["results"], [])
        for row in report["results"]:
            self.assertTrue(row["request_reload_parity"])
            self.assertEqual(row["profile_samples"], 2)
            self.assertEqual(row["validation_rows"], 60)
            self.assertNotIn("test", row)
            self.assertNotIn("r2", json.dumps(row).lower())
            self.assertEqual(row["vs_alpha_0_50"]["same_country_factor_changes"], 0)
            self.assertEqual(row["vs_alpha_0_50"]["same_country_label_changes"], 0)
            meta = ContinuousMetadataNormalizer.load_artifacts(
                str(self.root / "run" / f"alpha_{row['alpha']:.2f}"),
                str(self.root / "run" / f"alpha_{row['alpha']:.2f}" / "macro_lookup_table.json"))
            self.assertEqual(meta.alpha, row["alpha"])
            self.assertEqual(meta.scaler.n_features_in_, 3)
        self.assertEqual(report["results"][2]["vs_alpha_0_50"]["mean_absolute_factor_change"], 0)
        self.assertGreater(report["results"][0]["vs_alpha_0_50"]["mean_absolute_label_change_kes"], 0)
        self.assertGreater(report["results"][4]["vs_alpha_0_50"]["mean_absolute_factor_change"], 0)
        pairs = report["results"][0]["vs_alpha_0_50"]["validation_country_pair_sensitivity"]
        self.assertEqual(pairs["KE->KE"]["mean_absolute_factor_change"], 0)
        self.assertGreater(pairs["KE->IN"]["mean_absolute_scenario_target_change_kes"], 0)
        text = TextFeatureReducer.load_artifacts(str(self.root / "run" / "alpha_0.50"))
        self.assertEqual(text.reducer.n_components, 50)
        with self.assertRaisesRegex(ValueError, "empty report directory"):
            self.run_research()

    def test_rejects_unmatched_hash_edited_roles_and_alpha_labels(self):
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            run_benchmark(str(self.parquet), str(self.macro), str(self.root / "strict"))
        with self.assertRaisesRegex(ValueError, "dataset_version"):
            run_benchmark(str(self.parquet), str(self.macro), str(self.root / "unversioned"),
                          allow_other_snapshot=True)
        original = pd.read_parquet(self.parquet)
        modified = original.copy()
        modified.loc[0, "harmonized_hourly_rate"] += 20
        modified.to_parquet(self.parquet, index=False)
        with self.assertRaisesRegex(ValueError, "labels do not match"):
            self.run_research("bad_labels")
        modified = original.copy()
        modified.loc[0, "mentor_country_iso2"] = "UG"
        modified.to_parquet(self.parquet, index=False)
        with self.assertRaisesRegex(ValueError, "Country roles"):
            self.run_research("bad_roles")
        modified = original.copy()
        modified["arbitrage_alpha"] = 0.75
        modified.to_parquet(self.parquet, index=False)
        with self.assertRaisesRegex(ValueError, "frozen alpha"):
            self.run_research("bad_alpha")

    def test_targets_do_not_enter_coordinates_or_fitted_extrema(self):
        original = pd.read_parquet(self.parquet)
        case = original.iloc[:60].copy()
        case["market_saturation_score"] = 0.2
        trial = _scenario(case, self.records, 0.0)
        self.assertTrue(np.allclose(trial["target_rate"],
                                    np.round(case.hourly_rate * trial.bilateral_arbitrage_factor, 2)))
        normalizer = ContinuousMetadataNormalizer(str(self.macro), alpha=0)
        normalizer.fit(trial.to_dict(orient="records"))
        first = normalizer.transform(trial.to_dict(orient="records"))
        changed = trial.assign(hourly_rate=99999, harmonized_hourly_rate=1,
                               target_rate=9, market_saturation_score=0.2)
        np.testing.assert_array_equal(first, normalizer.transform(changed.to_dict(orient="records")))
        self.assertEqual(_country_coverage(case, self.records)["same_country_rows"], 40)
        without_india = {code: value for code, value in self.records.items() if code != "IN"}
        self.assertEqual(_country_coverage(case, without_india)["fallback_events"]["client_macro_lookup_to_KE"], 20)
        invalid = {**self.records, "IN": {**self.records["IN"], "cost_of_living_index": None}}
        self.assertEqual(_country_coverage(case, invalid)["fallback_events"]
                         ["client_cost_of_living_index_default_to_1"], 20)
        with self.assertRaisesRegex(ValueError, "invalid pre-arbitrage"):
            _scenario(case.assign(hourly_rate=np.nan), self.records, 0.25)

    def test_test_window_prealpha_rates_are_not_read_by_scenarios(self):
        baseline = self.run_research("unmodified")
        frame = pd.read_parquet(self.parquet)
        frame.loc[frame.observation_timestamp_utc.eq("2024-02-23T00:00:00+00:00"),
                  "hourly_rate"] = 0
        frame.to_parquet(self.parquet, index=False)
        changed = self.run_research("test_rates_changed")
        self.assertNotEqual(baseline["input_sha256"]["parquet"], changed["input_sha256"]["parquet"])
        for original, later in zip(baseline["results"], changed["results"]):
            self.assertEqual(original["validation_mean_scenario_target_kes"],
                             later["validation_mean_scenario_target_kes"])
            self.assertEqual(original["vs_alpha_0_50"], later["vs_alpha_0_50"])


if __name__ == "__main__":
    unittest.main()
