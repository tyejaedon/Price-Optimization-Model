"""Tests for seeding platform mentor profiles (#172, M11.7)."""

import os
import tempfile
import unittest

from src.api.repository import InMemoryRepository
from src.data.seed_platform_mentors import (
    build_mentor_profiles,
    export_profiles_json,
    load_cached_profiles,
    seed_repository,
)


class SeedPlatformMentorsTests(unittest.TestCase):
    def test_build_mentor_profiles_from_actual_datasets(self) -> None:
        profiles = build_mentor_profiles()
        self.assertGreaterEqual(len(profiles), 222)

        # Check in-scope vs out-of-scope segregation
        in_scope = [p for p in profiles if p.get("metadata", {}).get("is_in_scope")]
        out_of_scope = [p for p in profiles if not p.get("metadata", {}).get("is_in_scope")]

        self.assertGreaterEqual(len(in_scope), 52)
        self.assertGreaterEqual(len(out_of_scope), 170)

        # Check in-scope profile structure
        sample_in = in_scope[0]
        self.assertTrue(sample_in["profile_id"])
        self.assertEqual(sample_in["country_code"], "KE")
        self.assertIn("raw_description", sample_in["metadata"])
        self.assertIn("selected_industry", sample_in["metadata"])
        self.assertTrue(sample_in["metadata"]["selected_industry"])

        # Check out-of-scope profile structure
        sample_out = out_of_scope[0]
        self.assertTrue(sample_out["profile_id"])
        self.assertFalse(sample_out["metadata"]["is_in_scope"])
        self.assertIn("out_of_scope_reason", sample_out["metadata"])
        self.assertIsNone(sample_out["metadata"]["selected_industry"])

    def test_export_and_load_cached_profiles(self) -> None:
        profiles = build_mentor_profiles()
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_path = os.path.join(tmp_dir, "profiles.json")
            export_profiles_json(profiles, json_path)
            self.assertTrue(os.path.exists(json_path))

            loaded = load_cached_profiles(json_path)
            self.assertEqual(len(loaded), len(profiles))
            self.assertEqual(loaded[0]["profile_id"], profiles[0]["profile_id"])

    def test_seed_repository(self) -> None:
        repo = InMemoryRepository()
        self.assertEqual(len(repo.list_profiles()), 0)

        count = seed_repository(repo)
        self.assertGreaterEqual(count, 222)
        self.assertEqual(len(repo.list_profiles()), count)

        # Direct get_profile check
        first_id = repo.list_profiles()[0]["profile_id"]
        profile = repo.get_profile(first_id)
        self.assertIsNotNone(profile)
        self.assertEqual(profile["profile_id"], first_id)

    def test_build_mentor_profiles_from_fixtures(self) -> None:
        fixture_path = os.path.join("tests", "fixtures", "platform", "mentors.csv")
        profiles = build_mentor_profiles(raw_mentors_csv=fixture_path, corpus_csv="nonexistent.csv")
        self.assertGreaterEqual(len(profiles), 7)
        in_scope = [p for p in profiles if p.get("metadata", {}).get("is_in_scope")]
        out_of_scope = [p for p in profiles if not p.get("metadata", {}).get("is_in_scope")]
        # u5, u6 are vocational in fixture
        self.assertGreaterEqual(len(out_of_scope), 2)
        voc_cats = {p["metadata"]["platform_category"] for p in out_of_scope}
        self.assertIn("Culinary & Hospitality", voc_cats)

    def test_get_profile_supports_whitespace_and_secondary_id(self) -> None:
        repo = InMemoryRepository()
        seed_repository(repo)
        sample = repo.list_profiles()[0]
        user_id = sample["profile_id"]
        prof_id = sample["metadata"].get("platform_mentor_profile_id")

        # Whitespace tolerance
        self.assertIsNotNone(repo.get_profile(f"  {user_id}  "))

        # Secondary mentor_profile_id resolution
        if prof_id and prof_id != user_id:
            resolved_by_prof = repo.get_profile(prof_id)
            self.assertIsNotNone(resolved_by_prof)
            self.assertEqual(resolved_by_prof["profile_id"], user_id)


if __name__ == "__main__":
    unittest.main()
