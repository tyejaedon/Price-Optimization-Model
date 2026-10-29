"""Seed repository mentor profiles from platform_mentor_corpus (#172, M11.7).

The platform adapter calls ``POST /price`` with ``{"mentorId": "<id>"}`` where
``<id>`` is the mentor's platform user ID (``platform_mentor_user_id``).
Without seeded profiles, the route returns 422 because neither description
nor industry nor country can be resolved.

This module loads the platform mentors (both in-scope technical mentors from
``data/processed/platform_mentor_corpus.csv`` and vocational/out-of-scope mentors
from ``data/raw/career_mentor_os/mentors.csv``), converts them to valid
``ProfileDTO`` records, and seeds any ``Repository`` implementation.

In-scope mentors are seeded with their harmonized description and partition.
Vocational / out-of-scope mentors are seeded with ``metadata.is_in_scope = False``
and an explicit ``metadata.out_of_scope_reason``, enabling ``POST /price`` to
return a clean "outside scope" response rather than a 422 or nonsense quote.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from typing import Any, Dict, List, Optional

import pandas as pd

from src.api.api_contracts import ProfileDTO
from src.api.repository import InMemoryRepository, Repository

logger = logging.getLogger(__name__)

DEFAULT_RAW_MENTORS_CSV = os.path.join("data", "raw", "career_mentor_os", "mentors.csv")
DEFAULT_CORPUS_CSV = os.path.join("data", "processed", "platform_mentor_corpus.csv")
DEFAULT_PROFILES_JSON = os.path.join("data", "processed", "platform_mentor_profiles.json")
DEFAULT_FIXTURE_MENTORS_CSV = os.path.join("tests", "fixtures", "platform", "mentors.csv")


def build_mentor_profiles(
    raw_mentors_csv: str = DEFAULT_RAW_MENTORS_CSV,
    corpus_csv: str = DEFAULT_CORPUS_CSV,
) -> List[Dict[str, Any]]:
    """Build canonical ProfileDTO dictionaries for all platform mentors.

    Merges in-scope features from ``corpus_csv`` with mentor metadata from
    ``raw_mentors_csv``. Every record validates against ``ProfileDTO``.
    If raw CSV is missing, attempts live ingestion with credentials or falls back
    to committed test fixtures for sandboxed execution.
    """
    if not os.path.exists(raw_mentors_csv):
        # 1. Attempt live ingestion if supervisor credentials are provided
        if os.getenv("PLATFORM_API_EMAIL") and os.getenv("PLATFORM_API_PASSWORD"):
            try:
                from src.data.ingest_platform import main as ingest_main
                logger.info("Raw mentors CSV missing. Fetching via ingest_platform...")
                ingest_main()
            except Exception as exc:
                logger.warning("Auto-ingestion from platform API failed: %s", exc)

        # 2. Check fixture fallback if raw data is still absent (e.g. CI / fresh clone)
        if not os.path.exists(raw_mentors_csv) and os.path.exists(DEFAULT_FIXTURE_MENTORS_CSV):
            logger.info("Using test fixture mentors CSV: %s", DEFAULT_FIXTURE_MENTORS_CSV)
            raw_mentors_csv = DEFAULT_FIXTURE_MENTORS_CSV

    if not os.path.exists(raw_mentors_csv):
        raise FileNotFoundError(f"Raw mentors CSV not found: {raw_mentors_csv}")

    raw_df = pd.read_csv(raw_mentors_csv)

    corpus_map: Dict[str, Dict[str, Any]] = {}
    if os.path.exists(corpus_csv):
        corpus_df = pd.read_csv(corpus_csv)
        for _, row in corpus_df.iterrows():
            corpus_map[str(row["platform_mentor_user_id"])] = row.to_dict()

    profiles: List[Dict[str, Any]] = []

    for _, row in raw_df.iterrows():
        user_id = str(row["mentor_user_id"]).strip()
        profile_id = str(row["mentor_profile_id"]).strip()
        first_name = str(row["first_name"]).strip() if pd.notna(row.get("first_name")) else ""
        last_name = str(row["last_name"]).strip() if pd.notna(row.get("last_name")) else ""
        full_name = f"{first_name} {last_name}".strip() or "Platform Mentor"
        email = f"{user_id[:8]}@career-mentor-os.co.ke"

        category = str(row.get("category", "")).strip()
        specialization = str(row.get("specialization", "")).strip()
        mentor_type = str(row.get("mentor_type", "")).strip()
        tier = str(row.get("tier", "")).strip()
        city = str(row.get("city", "")).strip()
        hourly_rate = float(row["hourly_rate_kes"]) if pd.notna(row.get("hourly_rate_kes")) else None

        if user_id in corpus_map:
            c = corpus_map[user_id]
            realised = float(c["realised_hourly_rate_kes"]) if pd.notna(c.get("realised_hourly_rate_kes")) else None
            metadata = {
                "platform_mentor_user_id": user_id,
                "platform_mentor_profile_id": profile_id,
                "raw_description": str(c["raw_description"]),
                "selected_industry": str(c["industry_partition"]),
                "platform_category": str(c.get("platform_category", category)),
                "platform_specialization": str(c.get("platform_specialization", specialization)),
                "platform_tier": str(c.get("platform_tier", tier)),
                "platform_city": str(c.get("platform_city", city)),
                "listed_hourly_rate_kes": float(c.get("listed_hourly_rate_kes", hourly_rate or 0.0)),
                "realised_hourly_rate_kes": realised,
                "is_in_scope": True,
                "mentor_type": mentor_type or "PROFESSIONAL",
            }
        else:
            # Out-of-scope / vocational mentor
            metadata = {
                "platform_mentor_user_id": user_id,
                "platform_mentor_profile_id": profile_id,
                "raw_description": f"{specialization} mentor in {category}. Based in {city or 'Kenya'}, Kenya.",
                "selected_industry": None,
                "platform_category": category,
                "platform_specialization": specialization,
                "platform_tier": tier,
                "platform_city": city,
                "listed_hourly_rate_kes": hourly_rate,
                "realised_hourly_rate_kes": None,
                "is_in_scope": False,
                "out_of_scope_reason": f"Category '{category}' ({mentor_type}) is outside the technical model scope",
                "mentor_type": mentor_type or "VOCATIONAL",
            }

        profile_payload = {
            "profile_id": user_id,
            "full_name": full_name,
            "email": email,
            "country_code": "KE",
            "account_status": "active",
            "metadata": metadata,
        }

        # Validate against schema
        dto = ProfileDTO.model_validate(profile_payload)
        profiles.append(dto.model_dump())

    return profiles


def export_profiles_json(
    profiles: List[Dict[str, Any]],
    output_path: str = DEFAULT_PROFILES_JSON,
) -> str:
    """Save profiles list to JSON for fast zero-overhead startup loading."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2)
    logger.info("Exported %d profiles to %s", len(profiles), output_path)
    return output_path


def load_cached_profiles(profiles_json_path: str = DEFAULT_PROFILES_JSON) -> List[Dict[str, Any]]:
    """Load pre-generated profiles JSON if it exists."""
    if os.path.exists(profiles_json_path):
        with open(profiles_json_path, encoding="utf-8") as f:
            return json.load(f)
    return []


def seed_repository(
    repository: Repository,
    profiles: Optional[List[Dict[str, Any]]] = None,
    profiles_json_path: str = DEFAULT_PROFILES_JSON,
) -> int:
    """Seed a repository instance with platform mentor profiles.

    Loads from cached JSON if profiles is not provided, or builds them from CSVs.
    Returns the count of successfully upserted profiles.
    """
    if profiles is None:
        profiles = load_cached_profiles(profiles_json_path)
        if not profiles:
            profiles = build_mentor_profiles()
            export_profiles_json(profiles, profiles_json_path)

    seeded_count = 0
    for profile in profiles:
        pid = profile["profile_id"]
        repository.upsert_profile(pid, profile)
        seeded_count += 1

    logger.info("Seeded repository with %d mentor profiles.", seeded_count)
    return seeded_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed repository mentor profiles from platform corpus (#172).")
    parser.add_argument("--raw-mentors-csv", default=DEFAULT_RAW_MENTORS_CSV, help="Raw mentors CSV path.")
    parser.add_argument("--corpus-csv", default=DEFAULT_CORPUS_CSV, help="Platform mentor corpus CSV path.")
    parser.add_argument("--output-json", default=DEFAULT_PROFILES_JSON, help="Export JSON path.")
    parser.add_argument("--firestore", action="store_true", help="Also seed configured Firestore repository.")
    args = parser.parse_args()

    profiles = build_mentor_profiles(args.raw_mentors_csv, args.corpus_csv)
    export_profiles_json(profiles, args.output_json)
    print(f"Successfully processed and exported {len(profiles)} platform mentor profiles to {args.output_json}")

    in_scope_count = sum(1 for p in profiles if p.get("metadata", {}).get("is_in_scope"))
    out_of_scope_count = len(profiles) - in_scope_count
    print(f"  - In-Scope Technical Profiles: {in_scope_count}")
    print(f"  - Out-of-Scope Vocational Profiles: {out_of_scope_count}")

    if args.firestore:
        from src.api.repository import FirestoreRepository
        repo = FirestoreRepository()
        count = seed_repository(repo, profiles)
        print(f"Seeded {count} profiles into Firestore collection 'mentors'.")


if __name__ == "__main__":
    main()
