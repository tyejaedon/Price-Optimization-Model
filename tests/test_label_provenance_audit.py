import csv
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.ingest_multisource import (
    build_harmonized_marketplace_records,
    build_macro_lookup,
    export_harmonized_records_parquet,
    marketplace_exclusion_reason,
    parse_observation_timestamp_utc,
)
from src.label_provenance_audit import audit_label_provenance


class LabelProvenanceAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw_fixture = Path(__file__).resolve().parent / "fixtures" / "raw"

    def _build(self, tmp: str) -> tuple[str, str]:
        raw_dir = os.path.join(tmp, "raw")
        shutil.copytree(self.raw_fixture, raw_dir)
        macro = os.path.join(tmp, "macro.json")
        parquet = os.path.join(tmp, "corpus.parquet")
        build_macro_lookup(raw_dir, macro)
        export_harmonized_records_parquet(build_harmonized_marketplace_records(raw_dir, macro), parquet)
        return raw_dir, parquet

    def test_source_timestamp_requires_timezone_and_is_not_ingestion_time(self) -> None:
        self.assertEqual(parse_observation_timestamp_utc("2024-02-17 09:09:54+00:00"),
                         "2024-02-17T09:09:54+00:00")
        self.assertEqual(parse_observation_timestamp_utc("2024-02-17T12:09:54+03:00"),
                         "2024-02-17T09:09:54+00:00")
        self.assertIsNone(parse_observation_timestamp_utc("2026-01-05"))
        self.assertIsNone(parse_observation_timestamp_utc("not a time"))

    def test_pre_arbitrage_policy_is_inclusive_and_reasoned(self) -> None:
        row = {"raw_description": "A sufficiently long description for a priced job listing.",
               "industry_partition": "data_ai", "hourly_rate_usd": 500 / 130}
        self.assertIsNone(marketplace_exclusion_reason(row))
        self.assertIsNone(marketplace_exclusion_reason({**row, "hourly_rate_usd": 35000 / 130}))
        self.assertEqual(marketplace_exclusion_reason({**row, "hourly_rate_usd": 1}),
                         "pre_arbitrage_kes_out_of_bounds")
        self.assertEqual(marketplace_exclusion_reason({**row, "raw_description": "short"}),
                         "short_description")

    def test_aggregate_flow_uses_unmodified_source_data_and_reports_missing_dates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw, parquet = self._build(tmp)
            report = audit_label_provenance(raw, parquet)
            self.assertEqual(report["processed_rows"], 3)
            self.assertTrue(report["decision"]["raw_candidate_counts_match_parquet"])
            self.assertFalse(report["decision"]["current_parquet_can_support_oot"])
            self.assertFalse(report["decision"]["mentor_rate_oot_supported"])
            self.assertEqual(report["timestamp_coverage"]["processed_missing"], 3)
            self.assertEqual(report["sources"]["upwork_jobs"]["valid_raw_observation_dates"], 0)
            self.assertEqual(sum(g["processed_rows"] for g in report["source_industry_flow"].values()), 3)
            self.assertIn("upwork_data_scientists/data_ai", report["source_industry_flow"])
            self.assertEqual(sum(report["processed_source_country_counts"].values()), 3)
            self.assertEqual(sum(report["exclusions_by_source_industry_reason"].values()),
                             sum(g["excluded_before_arbitrage"] for g in report["source_industry_flow"].values()))
            self.assertNotIn("raw_description", str(report))
            self.assertNotIn("example.com", str(report))

    def test_aware_job_publication_date_survives_parquet_and_counts_for_oot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw, parquet = self._build(tmp)
            jobs = Path(raw) / "upwork-jobs.csv" / "upwork-jobs.csv"
            with jobs.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["published_date"] = "2024-02-17T12:09:54+03:00"
            rows[0]["hourly_low"] = "10"
            rows[0]["hourly_high"] = "20"
            rows[-1]["published_date"] = "2024-02-18T12:09:54+03:00"
            with jobs.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            macro = os.path.join(tmp, "macro.json")
            export_harmonized_records_parquet(build_harmonized_marketplace_records(raw, macro), parquet)
            frame = pd.read_parquet(parquet)
            self.assertEqual(frame.loc[frame.source_dataset == "upwork_data_scientists",
                                       "observation_timestamp_utc"].notna().sum(), 0)
            report = audit_label_provenance(raw, parquet)
            self.assertEqual(report["timestamp_coverage"]["processed_valid"], 2)
            self.assertTrue(report["decision"]["current_parquet_can_support_oot"])
            self.assertEqual(report["proposed_oot_policy"]["retained_job_budget_rows_with_timestamp_and_post_bounds"], 2)

    def test_audit_rejects_corrupted_label_and_target_derived_features(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw, parquet = self._build(tmp)
            frame = pd.read_parquet(parquet)
            frame.loc[0, "harmonized_hourly_rate"] += 1000
            frame.to_parquet(parquet, index=False)
            with self.assertRaisesRegex(ValueError, "rate transformation"):
                audit_label_provenance(raw, parquet)
            frame.loc[0, "harmonized_hourly_rate"] -= 1000
            frame["target_rate"] = frame["harmonized_hourly_rate"] + 1000
            frame.to_parquet(parquet, index=False)
            with self.assertRaisesRegex(ValueError, "target_rate overrides"):
                audit_label_provenance(raw, parquet)
            with patch("src.label_provenance_audit.DEFAULT_FEATURE_NAMES", ("hourly_rate",)):
                with self.assertRaisesRegex(ValueError, "Target-derived"):
                    audit_label_provenance(raw, parquet)


if __name__ == "__main__":
    unittest.main()
