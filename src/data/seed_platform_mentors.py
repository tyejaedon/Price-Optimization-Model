"""Seed repository mentor profiles from platform_mentor_corpus for POST /price resolution.

Career Mentor OS platform calls ``POST /price`` with ``{"mentorId": "..."}`` and
expects `{min, max, comparables, reason}`. When client requests omit inline pricing
inputs (raw_description, selected_industry, mentor_country), the gateway resolves
them from the mentor's stored profile in the repository.

This module maps rows from ``platform_mentor_corpus`` (or raw platform cache)
into validated ``ProfileDTO`` documents and seeds them into the repository.
It ensures that both ``platform_mentor_profile_id`` (e.g. "p1") and
``platform_mentor_user_id`` (e.g. "u1") resolve to the correct mentor attributes.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.api.api_contracts import ProfileDTO
from src.data.ingest_platform import (
    DEFAULT_CACHE_DIR,
    DEFAULT_OUTPUT_CSV,
    DEFAULT_OUTPUT_PARQUET,
    build_platform_records,
)

logger = logging.getLogger(__name__)

ENV_CORPUS_PATH = "PLATFORM_MENTOR_CORPUS_PATH"
ENV_AUTO_SEED = "SEED_PLATFORM_MENTORS"


COUNTRY_TO_ISO2: Dict[str, str] = {
    "KENYA": "KE",
    "KE": "KE",
    "UNITED STATES": "US",
    "USA": "US",
    "US": "US",
    "UNITED KINGDOM": "GB",
    "UK": "GB",
    "GB": "GB",
    "UGANDA": "UG",
    "UG": "UG",
    "TANZANIA": "TZ",
    "TZ": "TZ",
    "RWANDA": "RW",
    "RW": "RW",
    "NIGERIA": "NG",
    "NG": "NG",
    "SOUTH AFRICA": "ZA",
    "ZA": "ZA",
    "INDIA": "IN",
    "IN": "IN",
    "GERMANY": "DE",
    "DE": "DE",
    "CANADA": "CA",
    "CA": "CA",
}


def _normalize_country_iso2(country_raw: Any) -> str:
    cleaned = str(country_raw or "").strip().upper()
    if len(cleaned) == 2 and cleaned.isalpha():
        return cleaned
    return COUNTRY_TO_ISO2.get(cleaned, "KE")


def mentor_record_to_profile(record: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a platform corpus record into a validated ProfileDTO payload dictionary.

    Extracts required profile fields (profile_id, full_name, email, country_code)
    and populates metadata with ``raw_description`` and ``selected_industry``
    needed by the pricing engine, along with platform provenance attributes.
    """
    profile_id = str(
        record.get("platform_mentor_profile_id")
        or record.get("profile_id")
        or ""
    ).strip()
    if not profile_id:
        raise ValueError("record is missing platform_mentor_profile_id / profile_id")

    user_id = str(
        record.get("platform_mentor_user_id")
        or record.get("user_id")
        or ""
    ).strip()

    country = _normalize_country_iso2(
        record.get("country_code")
        or record.get("source_country")
        or record.get("mentor_country")
        or "KE"
    )

    raw_description = str(record.get("raw_description") or "").strip()
    selected_industry = str(
        record.get("industry_partition")
        or record.get("selected_industry")
        or ""
    ).strip()

    full_name = str(
        record.get("full_name")
        or record.get("platform_specialization")
        or record.get("job_title")
        or f"Mentor {profile_id}"
    ).strip()

    email = str(
        record.get("email")
        or f"{profile_id.lower()}@platform.careermentor.internal"
    ).strip()

    metadata: Dict[str, Any] = {
        "raw_description": raw_description,
        "selected_industry": selected_industry,
        "platform_mentor_profile_id": profile_id,
        "platform_mentor_user_id": user_id,
        "client_country": record.get("client_country") or "KE",
    }

    # Retain optional platform metadata fields when available
    for key in (
        "platform_category",
        "platform_specialization",
        "platform_tier",
        "platform_mentor_type",
        "platform_verification_status",
        "platform_experience_years",
        "platform_city",
        "platform_rating",
        "platform_total_reviews",
        "platform_skills",
        "listed_hourly_rate_kes",
        "realised_hourly_rate_kes",
        "completed_sessions",
        "no_show_rate",
        "mean_review_rating",
        "review_count",
    ):
        val = record.get(key)
        if val is not None:
            metadata[key] = val

    payload = {
        "profile_id": profile_id,
        "full_name": full_name,
        "email": email,
        "country_code": country,
        "account_status": "active",
        "metadata": metadata,
    }

    # Validate against canonical ProfileDTO schema
    validated = ProfileDTO.model_validate(payload)
    return validated.model_dump(exclude_none=True)


def load_platform_records(
    source: Union[str, Path, List[Dict[str, Any]], None] = None,
) -> List[Dict[str, Any]]:
    """Load platform records from a parquet, csv, raw cache directory, or list.

    If source is None, checks:
    1. PLATFORM_MENTOR_CORPUS_PATH environment variable
    2. DEFAULT_OUTPUT_PARQUET (data/processed/platform_mentor_corpus.parquet)
    3. DEFAULT_OUTPUT_CSV (data/processed/platform_mentor_corpus.csv)
    4. DEFAULT_CACHE_DIR (data/raw/career_mentor_os/)
    5. tests/fixtures/platform/ (fixture fallback)
    """
    if isinstance(source, list):
        return source

    candidate_path: Optional[str] = None
    if source is not None:
        candidate_path = str(source)
    else:
        env_path = os.getenv(ENV_CORPUS_PATH, "").strip()
        if env_path and os.path.exists(env_path):
            candidate_path = env_path
        elif os.path.exists(DEFAULT_OUTPUT_PARQUET):
            candidate_path = DEFAULT_OUTPUT_PARQUET
        elif os.path.exists(DEFAULT_OUTPUT_CSV):
            candidate_path = DEFAULT_OUTPUT_CSV
        elif os.path.isdir(DEFAULT_CACHE_DIR) and os.path.exists(os.path.join(DEFAULT_CACHE_DIR, "mentors.csv")):
            candidate_path = DEFAULT_CACHE_DIR
        else:
            repo_root = Path(__file__).resolve().parents[2]
            fixture_dir = repo_root / "tests" / "fixtures" / "platform"
            if fixture_dir.is_dir() and (fixture_dir / "mentors.csv").exists():
                candidate_path = str(fixture_dir)

    if not candidate_path or not os.path.exists(candidate_path):
        logger.warning("No platform corpus source found at %s", candidate_path)
        return []

    if os.path.isdir(candidate_path):
        result = build_platform_records(candidate_path)
        return result.records

    if candidate_path.endswith(".parquet"):
        import pandas as pd
        df = pd.read_parquet(candidate_path)
        return df.to_dict(orient="records")

    if candidate_path.endswith(".csv"):
        records: List[Dict[str, Any]] = []
        with open(candidate_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(dict(row))
        return records

    raise ValueError(f"Unsupported corpus file type: {candidate_path}")


def seed_platform_mentor_profiles(
    repository: Any,
    source: Union[str, Path, List[Dict[str, Any]], None] = None,
    *,
    create_user_aliases: bool = True,
) -> Dict[str, Any]:
    """Seed repository with mentor profiles from platform corpus records.

    For each mentor record:
    1. Validates and upserts the profile under ``platform_mentor_profile_id``.
    2. If ``create_user_aliases`` is True and ``platform_mentor_user_id`` differs
       from ``profile_id``, also upserts an alias profile under ``user_id``
       so direct repository lookups by user ID resolve immediately.

    Returns summary dictionary with counts of seeded profiles and aliases.
    """
    records = load_platform_records(source)
    seeded_count = 0
    alias_count = 0
    skipped_count = 0

    for rec in records:
        try:
            profile_data = mentor_record_to_profile(rec)
            pid = profile_data["profile_id"]
            repository.upsert_profile(pid, profile_data)
            seeded_count += 1

            uid = profile_data["metadata"].get("platform_mentor_user_id")
            if create_user_aliases and uid and uid != pid:
                alias_data = dict(profile_data)
                alias_data["profile_id"] = uid
                repository.upsert_profile(uid, alias_data)
                alias_count += 1
        except Exception as exc:
            logger.warning("Failed to seed mentor record: %s (error: %s)", rec, exc)
            skipped_count += 1

    summary = {
        "records_loaded": len(records),
        "profiles_seeded": seeded_count,
        "aliases_seeded": alias_count,
        "skipped": skipped_count,
    }
    logger.info("Platform mentor profile seeding complete: %s", summary)
    return summary


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed repository mentor profiles from platform_mentor_corpus."
    )
    parser.add_argument(
        "--corpus",
        default=None,
        help="Path to platform_mentor_corpus (.parquet or .csv) or raw cache directory",
    )
    parser.add_argument(
        "--no-aliases",
        action="store_true",
        help="Do not create user_id alias profiles for mentor_profile_id",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output summary as JSON",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    from src.api.repository import InMemoryRepository

    # Default to InMemoryRepository for CLI validation
    repo = InMemoryRepository()
    summary = seed_platform_mentor_profiles(
        repo,
        source=args.corpus,
        create_user_aliases=not args.no_aliases,
    )
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"Seeded {summary['profiles_seeded']} mentor profiles "
            f"({summary['aliases_seeded']} user aliases, {summary['skipped']} skipped) "
            f"from {summary['records_loaded']} records."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
