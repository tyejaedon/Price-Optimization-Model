"""Tests for M11.7: Seeding repository mentor profiles from platform_mentor_corpus."""

import os
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from src.api.api_contracts import PricingQueryDTO
from src.api.repository import InMemoryRepository
from src.api.serve import create_app
from src.data.seed_platform_mentors import (
    load_platform_records,
    mentor_record_to_profile,
    seed_platform_mentor_profiles,
)

PLATFORM_KEY = "test-platform-pricing-key"
ADMIN_TOKEN = "test-mlops-admin-token"


def mock_inference(query: PricingQueryDTO) -> Dict[str, Any]:
    assert isinstance(query, PricingQueryDTO)
    assert query.raw_description
    assert query.selected_industry
    return {
        "base_predicted_rate": 4500.0,
        "mpesa_tariff_surcharge": 57.0,
        "final_quoted_rate": 4557.0,
        "currency": "KES",
        "mentor_country_iso2": query.mentor_country,
        "nearest_neighbors": [
            {
                "peer_index": 1,
                "distance": 0.15,
                "verified_rate": 4200.0,
                "similarity_score": 0.88,
                "idw_weight": 0.6,
            },
            {
                "peer_index": 2,
                "distance": 0.25,
                "verified_rate": 4800.0,
                "similarity_score": 0.79,
                "idw_weight": 0.4,
            },
        ],
    }


class SeedPlatformMentorsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]
        self.fixtures_dir = str(self.repo_root / "tests" / "fixtures" / "platform")

    def test_mentor_record_to_profile_validation(self) -> None:
        rec = {
            "platform_mentor_profile_id": "p1",
            "platform_mentor_user_id": "u1",
            "source_country": "Kenya",
            "raw_description": "Data Analytics mentor specializing in SQL and Python.",
            "industry_partition": "data_ai",
            "platform_specialization": "Data Analytics",
            "listed_hourly_rate_kes": 5000.0,
        }
        profile = mentor_record_to_profile(rec)
        self.assertEqual(profile["profile_id"], "p1")
        self.assertEqual(profile["country_code"], "KE")
        self.assertEqual(profile["metadata"]["raw_description"], rec["raw_description"])
        self.assertEqual(profile["metadata"]["selected_industry"], "data_ai")
        self.assertEqual(profile["metadata"]["platform_mentor_user_id"], "u1")

    def test_mentor_record_missing_id_raises(self) -> None:
        with self.assertRaises(ValueError):
            mentor_record_to_profile({"source_country": "KE"})

    def test_load_records_from_fixtures(self) -> None:
        records = load_platform_records(self.fixtures_dir)
        self.assertGreaterEqual(len(records), 4)
        profile_ids = [r.get("platform_mentor_profile_id") for r in records]
        self.assertIn("p1", profile_ids)
        self.assertIn("p2", profile_ids)

    def test_load_records_from_parquet_and_csv(self) -> None:
        records = load_platform_records(self.fixtures_dir)
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "corpus.csv")
            parquet_path = os.path.join(tmpdir, "corpus.parquet")
            df = pd.DataFrame(records)
            df.to_csv(csv_path, index=False)
            df.to_parquet(parquet_path, index=False)

            from_csv = load_platform_records(csv_path)
            self.assertEqual(len(from_csv), len(records))

            from_parquet = load_platform_records(parquet_path)
            self.assertEqual(len(from_parquet), len(records))

    def test_seed_platform_mentor_profiles_in_memory(self) -> None:
        repo = InMemoryRepository()
        summary = seed_platform_mentor_profiles(repo, source=self.fixtures_dir)
        self.assertEqual(summary["profiles_seeded"], 4)
        self.assertEqual(summary["aliases_seeded"], 4)
        self.assertEqual(summary["skipped"], 0)

        profiles = repo.list_profiles()
        p_ids = {p["profile_id"] for p in profiles}
        # Profiles by profile_id and user aliases
        self.assertTrue({"p1", "p2", "p3", "p4"}.issubset(p_ids))
        self.assertTrue({"u1", "u2", "u3", "u4"}.issubset(p_ids))

        # Idempotent re-seed
        summary2 = seed_platform_mentor_profiles(repo, source=self.fixtures_dir)
        self.assertEqual(summary2["profiles_seeded"], 4)

    def test_seed_without_aliases(self) -> None:
        repo = InMemoryRepository()
        summary = seed_platform_mentor_profiles(
            repo, source=self.fixtures_dir, create_user_aliases=False
        )
        self.assertEqual(summary["profiles_seeded"], 4)
        self.assertEqual(summary["aliases_seeded"], 0)
        p_ids = {p["profile_id"] for p in repo.list_profiles()}
        self.assertTrue({"p1", "p2", "p3", "p4"}.issubset(p_ids))
        self.assertNotIn("u1", p_ids)

    def test_post_price_resolution_with_seeded_profile_id(self) -> None:
        repo = InMemoryRepository()
        seed_platform_mentor_profiles(repo, source=self.fixtures_dir)

        app = create_app(
            inference=mock_inference,
            repository=repo,
        )
        with patch.dict(os.environ, {"PLATFORM_PRICE_KEY": PLATFORM_KEY}):
            with TestClient(app) as client:
                # Platform sends only mentorId (p1)
                resp = client.post(
                    "/price",
                    json={"mentorId": "p1"},
                    headers={"X-Platform-Key": PLATFORM_KEY},
                )
                self.assertEqual(resp.status_code, 200, resp.text)
                body = resp.json()
                self.assertEqual(body["min"], 4200.0)
                self.assertEqual(body["max"], 4800.0)
                self.assertIn("4557.00 KES", body["reason"])
                self.assertEqual(len(body["comparables"]), 2)

    def test_post_price_resolution_with_seeded_user_id_alias(self) -> None:
        repo = InMemoryRepository()
        seed_platform_mentor_profiles(repo, source=self.fixtures_dir)

        app = create_app(
            inference=mock_inference,
            repository=repo,
        )
        with patch.dict(os.environ, {"PLATFORM_PRICE_KEY": PLATFORM_KEY}):
            with TestClient(app) as client:
                # Platform sends user ID (u1) instead of profile ID (p1)
                resp = client.post(
                    "/price",
                    json={"mentorId": "u1"},
                    headers={"X-Platform-Key": PLATFORM_KEY},
                )
                self.assertEqual(resp.status_code, 200, resp.text)
                body = resp.json()
                self.assertEqual(body["min"], 4200.0)
                self.assertIn("4557.00 KES", body["reason"])

    def test_post_price_unseeded_mentor_returns_422(self) -> None:
        repo = InMemoryRepository()
        seed_platform_mentor_profiles(repo, source=self.fixtures_dir)

        app = create_app(
            inference=mock_inference,
            repository=repo,
        )
        with patch.dict(os.environ, {"PLATFORM_PRICE_KEY": PLATFORM_KEY}):
            with TestClient(app) as client:
                resp = client.post(
                    "/price",
                    json={"mentorId": "unknown-mentor-999"},
                    headers={"X-Platform-Key": PLATFORM_KEY},
                )
                self.assertEqual(resp.status_code, 422)
                detail = resp.json()["detail"]
                self.assertEqual(detail["mentorId"], "unknown-mentor-999")
                self.assertIn("raw_description", detail["missing"])

    def test_admin_seed_platform_mentors_endpoint(self) -> None:
        repo = InMemoryRepository()
        app = create_app(
            inference=mock_inference,
            repository=repo,
            admin_token=ADMIN_TOKEN,
        )
        with patch.dict(os.environ, {"PLATFORM_PRICE_KEY": PLATFORM_KEY}):
            with TestClient(app) as client:
                # Unauthorized call is rejected
                unauth = client.post("/api/v1/admin/seed-platform-mentors")
                self.assertIn(unauth.status_code, (401, 403))

                # Authorized call seeds successfully
                resp = client.post(
                    "/api/v1/admin/seed-platform-mentors",
                    params={"corpus_path": self.fixtures_dir},
                    headers={"X-Admin-Token": ADMIN_TOKEN},
                )
                self.assertEqual(resp.status_code, 200, resp.text)
                summary = resp.json()
                self.assertEqual(summary["profiles_seeded"], 4)

                # Now POST /price works for seeded mentor
                price_resp = client.post(
                    "/price",
                    json={"mentorId": "p3"},
                    headers={"X-Platform-Key": PLATFORM_KEY},
                )
                self.assertEqual(price_resp.status_code, 200)

    def test_auto_seed_on_startup(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PLATFORM_PRICE_KEY": PLATFORM_KEY,
                "SEED_PLATFORM_MENTORS": "true",
                "PLATFORM_MENTOR_CORPUS_PATH": self.fixtures_dir,
            },
        ):
            app = create_app(
                inference=mock_inference,
                repository=InMemoryRepository(),
            )
            with TestClient(app) as client:
                resp = client.post(
                    "/price",
                    json={"mentorId": "p2"},
                    headers={"X-Platform-Key": PLATFORM_KEY},
                )
                self.assertEqual(resp.status_code, 200, resp.text)

    def test_seed_vocational_mentors_and_price_resolution(self) -> None:
        repo = InMemoryRepository()
        summary = seed_platform_mentor_profiles(
            repo, source=self.fixtures_dir, include_vocational=True
        )
        self.assertGreaterEqual(summary["profiles_seeded"], 6)

        app = create_app(
            inference=mock_inference,
            repository=repo,
        )
        with patch.dict(os.environ, {"PLATFORM_PRICE_KEY": PLATFORM_KEY}):
            with TestClient(app) as client:
                # p5 is Esther Wanjiru, Culinary & Hospitality (VOCATIONAL)
                resp = client.post(
                    "/price",
                    json={"mentorId": "p5"},
                    headers={"X-Platform-Key": PLATFORM_KEY},
                )
                self.assertEqual(resp.status_code, 200, resp.text)
                body = resp.json()
                self.assertEqual(body["min"], 0.0)
                self.assertEqual(body["max"], 0.0)
                self.assertEqual(body["comparables"], [])
                self.assertIn("Culinary & Hospitality", body["reason"])
                self.assertIn("outside technical pricing scope", body["reason"])

                # Also resolves via user alias u5
                alias_resp = client.post(
                    "/price",
                    json={"mentorId": "u5"},
                    headers={"X-Platform-Key": PLATFORM_KEY},
                )
                self.assertEqual(alias_resp.status_code, 200)
                self.assertEqual(alias_resp.json()["min"], 0.0)
                self.assertIn("Culinary & Hospitality", alias_resp.json()["reason"])


if __name__ == "__main__":
    unittest.main()
