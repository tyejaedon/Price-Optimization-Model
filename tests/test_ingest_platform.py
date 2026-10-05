import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import httpx

from src.ingest_multisource import (
    MIN_DESCRIPTION_LENGTH,
    SUPPORTED_INDUSTRY_PARTITIONS,
    USD_TO_KES_RATE_ANCHOR,
    marketplace_exclusion_reason,
)
from src.ingest_platform import (
    HARMONIZED_FIELDS,
    OUTPUT_FIELDS,
    PLATFORM_CATEGORY_PARTITIONS,
    SOURCE_DATASET,
    PlatformDatasetClient,
    PlatformDatasetError,
    build_platform_records,
    platform_timestamp_utc,
    resolve_platform_partition,
)


class PlatformIngestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parent.parent
        self.cache_dir = str(self.repo_root / "tests" / "fixtures" / "platform")
        self.result = build_platform_records(self.cache_dir)
        self.by_user = {r["platform_mentor_user_id"]: r for r in self.result.records}

    # ── scope ──────────────────────────────────────────────────────────────

    def test_every_platform_category_has_an_explicit_decision(self) -> None:
        for category, target in PLATFORM_CATEGORY_PARTITIONS.items():
            self.assertTrue(target is None or target == "__by_skills__" or target in SUPPORTED_INDUSTRY_PARTITIONS, category)

    def test_partition_resolution_per_category(self) -> None:
        self.assertEqual(resolve_platform_partition("Technology & IT", "Data Analytics Agile/Scrum", "Data Analytics"), "data_ai")
        self.assertIn(resolve_platform_partition("Technology & IT", "Cybersecurity", "Cybersecurity"), SUPPORTED_INDUSTRY_PARTITIONS)
        self.assertEqual(resolve_platform_partition("Marketing & Communications", "Digital Marketing"), "digital_marketing")
        self.assertEqual(resolve_platform_partition("Business & Management", "Leadership"), "product_management")
        self.assertIsNone(resolve_platform_partition("Culinary & Hospitality", "Professional Cooking"))
        self.assertIsNone(resolve_platform_partition("Never Heard Of It", "anything"))

    def test_out_of_scope_and_out_of_bounds_mentors_are_excluded_and_counted(self) -> None:
        self.assertEqual(self.result.mentors_seen, 7)
        self.assertEqual(len(self.result.records), 4)
        self.assertEqual(self.result.excluded["out_of_scope_category"], 2)
        self.assertEqual(self.result.excluded["pre_arbitrage_kes_out_of_bounds"], 1)
        self.assertNotIn("u5", self.by_user)
        self.assertNotIn("u6", self.by_user)
        self.assertNotIn("u7", self.by_user)

    # ── harmonized shape ───────────────────────────────────────────────────

    def test_records_carry_the_harmonized_fields_and_pass_the_shared_gate(self) -> None:
        for record in self.result.records:
            for field in OUTPUT_FIELDS:
                self.assertIn(field, record)
            self.assertIsNone(marketplace_exclusion_reason(record))
            self.assertEqual(record["source_dataset"], SOURCE_DATASET)
            self.assertEqual(record["currency"], "KES")
            self.assertEqual(record["source_country"], "Kenya")
            self.assertIn(record["industry_partition"], SUPPORTED_INDUSTRY_PARTITIONS)
            self.assertGreaterEqual(len(record["raw_description"]), MIN_DESCRIPTION_LENGTH)

    def test_listed_rate_round_trips_through_the_usd_anchor(self) -> None:
        record = self.by_user["u1"]
        self.assertEqual(record["listed_hourly_rate_kes"], 5000.0)
        self.assertEqual(record["hourly_rate"], 5000.0)
        self.assertAlmostEqual(record["hourly_rate_usd"], round(5000.0 / USD_TO_KES_RATE_ANCHOR, 2))
        self.assertEqual(record["usd_to_kes_rate_anchor"], USD_TO_KES_RATE_ANCHOR)

    def test_description_is_built_from_specialization_category_and_skills(self) -> None:
        text = self.by_user["u1"]["raw_description"]
        self.assertIn("Data Analytics mentor in Technology & IT", text)
        self.assertIn("Agile/Scrum", text)
        self.assertIn("7 years", text)
        self.assertIn("Nairobi", text)

    def test_observation_timestamp_is_timezone_aware_utc(self) -> None:
        stamp = self.by_user["u1"]["observation_timestamp_utc"]
        parsed = datetime.fromisoformat(stamp)
        self.assertIsNotNone(parsed.utcoffset())
        self.assertEqual(parsed.utcoffset().total_seconds(), 0)
        self.assertEqual(platform_timestamp_utc(""), None)
        self.assertEqual(platform_timestamp_utc("not a date"), None)
        self.assertEqual(platform_timestamp_utc("2026-01-01T03:00:00+03:00"), "2026-01-01T00:00:00+00:00")

    # ── platform truth ─────────────────────────────────────────────────────

    def test_activity_enrichment_uses_completed_bookings_only(self) -> None:
        record = self.by_user["u1"]
        # 5000/60min, 7500/90min, 6000/60min -> 5000, 5000, 6000 per hour -> median 5000
        self.assertEqual(record["realised_hourly_rate_kes"], 5000.0)
        self.assertEqual(record["completed_sessions"], 3)
        # judged = 3 completed + 1 no-show + 1 cancelled; the pending booking is not judged
        self.assertEqual(record["no_show_rate"], 0.2)
        self.assertEqual(record["mean_review_rating"], 4.5)
        self.assertEqual(record["review_count"], 2)

    def test_mentor_without_activity_has_null_truth_not_zero_rate(self) -> None:
        record = self.by_user["u2"]
        self.assertIsNone(record["realised_hourly_rate_kes"])
        self.assertEqual(record["completed_sessions"], 0)
        self.assertIsNone(record["no_show_rate"])
        self.assertIsNone(record["mean_review_rating"])
        self.assertEqual(record["review_count"], 0)

    # ── client ─────────────────────────────────────────────────────────────

    def _transport(self, dataset_status: int = 200):
        seen = {"auth_header": None, "login_body": None}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/auth/login"):
                seen["login_body"] = json.loads(request.content)
                return httpx.Response(200, json={"success": True, "data": {"accessToken": "tok-123"}})
            seen["auth_header"] = request.headers.get("Authorization")
            if dataset_status != 200:
                return httpx.Response(dataset_status, json={"success": False})
            if request.url.path.endswith("/sandbox/dataset"):
                return httpx.Response(200, json={"success": True, "data": {"files": [{"file": "mentors.csv"}]}})
            return httpx.Response(200, content=b"mentor_profile_id,mentor_user_id\np1,u1\n")

        return httpx.MockTransport(handler), seen

    def test_client_logs_in_once_and_downloads_with_bearer_token(self) -> None:
        transport, seen = self._transport()
        client = PlatformDatasetClient("https://example.test/api/v1", "student@example.test", "pw", transport=transport)
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                paths = client.fetch_all(tmp_dir, names=("mentors", "reviews"))
                self.assertEqual(sorted(paths), ["mentors", "reviews"])
                with open(paths["mentors"], "r", encoding="utf-8") as handle:
                    self.assertTrue(handle.read().startswith("mentor_profile_id"))
            self.assertEqual(seen["auth_header"], "Bearer tok-123")
            self.assertEqual(seen["login_body"], {"email": "student@example.test", "password": "pw"})
            self.assertIn("files", client.index())
        finally:
            client.close()

    def test_client_explains_a_disabled_dataset(self) -> None:
        transport, _ = self._transport(dataset_status=403)
        client = PlatformDatasetClient("https://example.test/api/v1", "student@example.test", "pw", transport=transport)
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                with self.assertRaises(PlatformDatasetError) as ctx:
                    client.download("mentors", tmp_dir)
            self.assertIn("SANDBOX_ENABLED", str(ctx.exception))
        finally:
            client.close()

    def test_client_refuses_to_start_without_credentials(self) -> None:
        with self.assertRaises(ValueError):
            PlatformDatasetClient("https://example.test/api/v1", "", "")

    # ── CLI ────────────────────────────────────────────────────────────────

    def test_cli_offline_writes_csv_parquet_and_summary(self) -> None:
        import pandas as pd

        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = os.path.join(tmp_dir, "platform.csv")
            parquet_path = os.path.join(tmp_dir, "platform.parquet")
            summary_path = os.path.join(tmp_dir, "summary.json")
            completed = subprocess.run(
                [
                    sys.executable, "-m", "src.ingest_platform", "--offline",
                    "--cache-dir", self.cache_dir,
                    "--output-csv", csv_path, "--output-parquet", parquet_path, "--summary-json", summary_path,
                ],
                cwd=str(self.repo_root), capture_output=True, text=True, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

            df = pd.read_parquet(parquet_path)
            self.assertEqual(len(df), 4)
            for field in HARMONIZED_FIELDS:
                self.assertIn(field, df.columns)
            self.assertIn("realised_hourly_rate_kes", df.columns)

            with open(csv_path, "r", encoding="utf-8") as handle:
                header = handle.readline().strip().split(",")
            self.assertEqual(header, list(OUTPUT_FIELDS))

            with open(summary_path, "r", encoding="utf-8") as handle:
                summary = json.load(handle)
            self.assertEqual(summary["records_retained"], 4)
            self.assertEqual(summary["excluded_by_reason"]["out_of_scope_category"], 2)
            self.assertEqual(summary["median_listed_hourly_rate_kes"], 5000.0)


if __name__ == "__main__":
    unittest.main()
