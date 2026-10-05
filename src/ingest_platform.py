"""Ingest the Career Mentor OS platform dataset as a second pricing source.

The engine trains on Upwork and freelancer CSVs. The platform it quotes for
publishes its own dataset (mentors, skills, bookings, reviews) as CSV from
its staging API, behind an ordinary login. This module fetches those files,
caches them under ``data/raw/``, and maps each mentor into the harmonized
record shape that ``ingest_multisource`` already produces, so the output
parquet drops into the existing training path unchanged.

Two things the Upwork corpus never had come along for free: the rate the
mentor *lists* on the platform, and the rate clients *actually paid* in
completed bookings. Both are kept so a quote can be judged against either.

Scope is handled honestly. The engine's industry partitions are technical
(data_ai, web_backend, mobile, ...). Most platform mentors are vocational.
Those are excluded with a counted reason rather than forced into
``general_tech``, which would poison the nearest-neighbour index.

Every row in the dataset is synthetic. Say so in anything you report.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import httpx

from src.ingest_multisource import (
    MAX_ACCEPTED_HOURLY_RATE_KES,
    MIN_ACCEPTED_HOURLY_RATE_KES,
    MIN_DESCRIPTION_LENGTH,
    SUPPORTED_INDUSTRY_PARTITIONS,
    USD_TO_KES_RATE_ANCHOR,
    _normalize_text,
    _safe_float_any,
    export_harmonized_records_parquet,
    map_industry_partition,
    marketplace_exclusion_reason,
)

SOURCE_DATASET = "career_mentor_os_sandbox"
PLATFORM_COUNTRY = "Kenya"

# Environment only. The staging URL is public; the account is whatever login
# the student was given. Nothing here is a secret worth committing, but the
# password still never goes in a file.
PLATFORM_BASE_URL_ENV = "PLATFORM_API_BASE_URL"
PLATFORM_EMAIL_ENV = "PLATFORM_API_EMAIL"
PLATFORM_PASSWORD_ENV = "PLATFORM_API_PASSWORD"
DEFAULT_PLATFORM_BASE_URL = "https://api-career-mentor.webmasterskenya.com/api/v1"

DEFAULT_CACHE_DIR = os.path.join("data", "raw", "career_mentor_os")
DEFAULT_OUTPUT_CSV = os.path.join("data", "processed", "platform_mentor_corpus.csv")
DEFAULT_OUTPUT_PARQUET = os.path.join("data", "processed", "platform_mentor_corpus.parquet")

DATASET_FILES = ("mentors", "mentor_skills", "skills", "bookings", "reviews")

# Platform category -> engine partition. ``None`` means the category is
# outside what the engine prices and the mentor is excluded, counted under
# ``out_of_scope_category``. "Technology & IT" is resolved from the mentor's
# skills text with the same keyword mapper the Upwork sources use, so a data
# analyst lands in data_ai and a cloud engineer in devops_cloud.
PLATFORM_CATEGORY_PARTITIONS: Dict[str, Optional[str]] = {
    "Technology & IT": "__by_skills__",
    "Marketing & Communications": "digital_marketing",
    "Business & Management": "product_management",
    "Agriculture & Farming": None,
    "Automotive & Mechanics": None,
    "Beauty & Cosmetology": None,
    "Construction & Building": None,
    "Culinary & Hospitality": None,
    "Education & Academia": None,
    "Electrical & Electronics": None,
    "Fashion & Textiles": None,
    "Finance & Accounting": None,
    "Healthcare & Medical": None,
    "Legal & Compliance": None,
    "Personal Development": None,
    "Transport & Logistics": None,
}

TIER_TEXT = {
    "CERTIFIED": "Certified mentor",
    "EXPERIENCED": "Experienced mentor",
    "ENTRY_LEVEL": "Entry-level mentor",
}

HARMONIZED_FIELDS = (
    "source_dataset",
    "job_title",
    "raw_description",
    "source_country",
    "industry_partition",
    "hourly_rate",
    "hourly_rate_usd",
    "currency",
    "usd_to_kes_rate_anchor",
    "observation_timestamp_utc",
)

PLATFORM_FIELDS = (
    "platform_mentor_profile_id",
    "platform_mentor_user_id",
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
)

OUTPUT_FIELDS = HARMONIZED_FIELDS + PLATFORM_FIELDS


# ── fetching ────────────────────────────────────────────────────────────────


class PlatformDatasetError(RuntimeError):
    """Raised when the platform API refuses or the dataset is not served."""


class PlatformDatasetClient:
    """Logs in once and streams dataset files to disk.

    Pass ``transport`` in tests (``httpx.MockTransport``) so nothing touches
    the network. The access token lives only in this object's headers and is
    never logged or written.
    """

    def __init__(
        self,
        base_url: str,
        email: str,
        password: str,
        timeout_seconds: float = 120.0,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError(f"{PLATFORM_BASE_URL_ENV} is empty")
        if not email.strip() or not password:
            raise ValueError(f"{PLATFORM_EMAIL_ENV} and {PLATFORM_PASSWORD_ENV} are both required to fetch the dataset")
        self._email = email.strip()
        self._password = password
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_seconds, transport=transport)
        self._authenticated = False

    @classmethod
    def from_env(cls, transport: Optional[httpx.BaseTransport] = None) -> "PlatformDatasetClient":
        return cls(
            base_url=os.getenv(PLATFORM_BASE_URL_ENV, DEFAULT_PLATFORM_BASE_URL),
            email=os.getenv(PLATFORM_EMAIL_ENV, ""),
            password=os.getenv(PLATFORM_PASSWORD_ENV, ""),
            transport=transport,
        )

    def login(self) -> None:
        response = self._client.post("/auth/login", json={"email": self._email, "password": self._password})
        if response.status_code != 200 and response.status_code != 201:
            raise PlatformDatasetError(f"platform login failed with HTTP {response.status_code}")
        try:
            token = response.json()["data"]["accessToken"]
        except (ValueError, KeyError, TypeError) as exc:
            raise PlatformDatasetError("platform login response did not carry data.accessToken") from exc
        self._client.headers["Authorization"] = f"Bearer {token}"
        self._authenticated = True

    def index(self) -> Dict[str, Any]:
        self._ensure_login()
        response = self._client.get("/sandbox/dataset")
        self._raise_for_dataset(response)
        return response.json()["data"]

    def download(self, name: str, dest_dir: str) -> str:
        """Stream ``<name>.csv`` to ``dest_dir`` and return the path."""
        self._ensure_login()
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, f"{name}.csv")
        with self._client.stream("GET", f"/sandbox/dataset/{name}.csv") as response:
            self._raise_for_dataset(response)
            with open(dest_path, "wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
        return dest_path

    def fetch_all(self, dest_dir: str, names: Iterable[str] = DATASET_FILES) -> Dict[str, str]:
        return {name: self.download(name, dest_dir) for name in names}

    def close(self) -> None:
        self._client.close()

    def _ensure_login(self) -> None:
        if not self._authenticated:
            self.login()

    @staticmethod
    def _raise_for_dataset(response: httpx.Response) -> None:
        if response.status_code == 403:
            raise PlatformDatasetError(
                "the platform refused the dataset (HTTP 403): SANDBOX_ENABLED is off on that deployment, "
                "or it is production, where the dataset is never served"
            )
        if response.status_code == 401:
            raise PlatformDatasetError("the platform rejected the login token (HTTP 401)")
        if response.status_code == 404:
            raise PlatformDatasetError("no such dataset file (HTTP 404); see the index at /sandbox/dataset")
        if response.status_code != 200:
            raise PlatformDatasetError(f"platform dataset request failed with HTTP {response.status_code}")


# ── reading the cache ───────────────────────────────────────────────────────


def _read_csv(cache_dir: str, name: str) -> List[Dict[str, str]]:
    path = os.path.join(cache_dir, f"{name}.csv")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"{path} is missing; run without --offline to fetch it")
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def platform_timestamp_utc(value: Any) -> Optional[str]:
    """Platform timestamps arrive naive (``2026-09-21 14:04:02.134``) and are stored in UTC.

    ``parse_observation_timestamp_utc`` rightly refuses naive instants, so the
    UTC offset is attached here, where the assumption is known to hold.
    """
    text = _normalize_text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def resolve_platform_partition(category: Any, skills_text: str, specialization: Any = "") -> Optional[str]:
    """Engine partition for a platform category, or ``None`` when out of scope."""
    mapped = PLATFORM_CATEGORY_PARTITIONS.get(_normalize_text(category).strip())
    if mapped == "__by_skills__":
        partition = map_industry_partition(f"{_normalize_text(specialization)} {skills_text}".strip())
        return partition if partition in SUPPORTED_INDUSTRY_PARTITIONS else "general_tech"
    return mapped


def build_description(mentor: Dict[str, str], skills: List[str]) -> str:
    """Text the TF-IDF sees. Built from structured fields; the platform has no free-text bio in the export."""
    specialization = _normalize_text(mentor.get("specialization")).strip()
    category = _normalize_text(mentor.get("category")).strip()
    tier = TIER_TEXT.get(_normalize_text(mentor.get("tier")).strip(), "Mentor")
    experience = _safe_float_any(mentor.get("experience_years"))
    city = _normalize_text(mentor.get("city")).strip() or "Kenya"
    parts = [f"{specialization} mentor in {category}."]
    if skills:
        parts.append("Skills: " + ", ".join(skills) + ".")
    if experience is not None:
        parts.append(f"{tier} with {int(experience)} years of experience, based in {city}, Kenya.")
    else:
        parts.append(f"{tier} based in {city}, Kenya.")
    return " ".join(parts)


@dataclass
class PlatformActivity:
    completed_rates: List[float] = field(default_factory=list)
    completed: int = 0
    no_shows: int = 0
    judged: int = 0
    review_ratings: List[float] = field(default_factory=list)


def summarise_activity(bookings: List[Dict[str, str]], reviews: List[Dict[str, str]]) -> Dict[str, PlatformActivity]:
    """Per mentor: what clients actually paid per hour, how often they turned up, how they rated it.

    ``no_show_rate`` is NO_SHOW over every booking that reached a verdict
    (COMPLETED, NO_SHOW or CANCELLED); bookings still pending are not judged.
    """
    activity: Dict[str, PlatformActivity] = defaultdict(PlatformActivity)
    for row in bookings:
        mentor_id = _normalize_text(row.get("mentor_user_id")).strip()
        status = _normalize_text(row.get("booking_status")).strip().upper()
        if not mentor_id or status not in {"COMPLETED", "NO_SHOW", "CANCELLED"}:
            continue
        record = activity[mentor_id]
        record.judged += 1
        if status == "NO_SHOW":
            record.no_shows += 1
        if status == "COMPLETED":
            record.completed += 1
            amount = _safe_float_any(row.get("amount_kes"))
            minutes = _safe_float_any(row.get("duration_minutes"))
            if amount is not None and minutes and minutes > 0:
                record.completed_rates.append(amount / (minutes / 60.0))
    for row in reviews:
        mentor_id = _normalize_text(row.get("mentor_user_id")).strip()
        rating = _safe_float_any(row.get("rating"))
        if mentor_id and rating is not None:
            activity[mentor_id].review_ratings.append(rating)
    return activity


def _skills_by_profile(mentor_skills: List[Dict[str, str]]) -> Dict[str, List[str]]:
    skills: Dict[str, List[str]] = defaultdict(list)
    for row in mentor_skills:
        profile_id = _normalize_text(row.get("mentor_profile_id")).strip()
        skill = _normalize_text(row.get("skill")).strip()
        if profile_id and skill and skill not in skills[profile_id]:
            skills[profile_id].append(skill)
    return skills


# ── building records ────────────────────────────────────────────────────────


@dataclass
class PlatformIngestResult:
    records: List[Dict[str, Any]]
    mentors_seen: int
    excluded: Counter
    partitions: Counter

    def summary(self) -> Dict[str, Any]:
        listed = [r["listed_hourly_rate_kes"] for r in self.records]
        realised = [r["realised_hourly_rate_kes"] for r in self.records if r["realised_hourly_rate_kes"] is not None]
        return {
            "source_dataset": SOURCE_DATASET,
            "mentors_seen": self.mentors_seen,
            "records_retained": len(self.records),
            "excluded_by_reason": dict(sorted(self.excluded.items())),
            "retained_by_partition": dict(sorted(self.partitions.items())),
            "median_listed_hourly_rate_kes": round(statistics.median(listed), 2) if listed else None,
            "median_realised_hourly_rate_kes": round(statistics.median(realised), 2) if realised else None,
            "mentors_with_completed_sessions": len(realised),
        }


def build_platform_records(
    cache_dir: str,
    usd_to_kes_rate_anchor: float = USD_TO_KES_RATE_ANCHOR,
    min_description_length: int = MIN_DESCRIPTION_LENGTH,
    min_hourly_rate_kes: float = MIN_ACCEPTED_HOURLY_RATE_KES,
    max_hourly_rate_kes: float = MAX_ACCEPTED_HOURLY_RATE_KES,
) -> PlatformIngestResult:
    mentors = _read_csv(cache_dir, "mentors")
    skills_by_profile = _skills_by_profile(_read_csv(cache_dir, "mentor_skills"))
    activity = summarise_activity(_read_csv(cache_dir, "bookings"), _read_csv(cache_dir, "reviews"))

    records: List[Dict[str, Any]] = []
    excluded: Counter = Counter()
    partitions: Counter = Counter()

    for mentor in mentors:
        profile_id = _normalize_text(mentor.get("mentor_profile_id")).strip()
        user_id = _normalize_text(mentor.get("mentor_user_id")).strip()
        skills = skills_by_profile.get(profile_id, [])
        partition = resolve_platform_partition(mentor.get("category"), " ".join(skills), mentor.get("specialization"))
        if partition is None:
            excluded["out_of_scope_category"] += 1
            continue

        listed_kes = _safe_float_any(mentor.get("hourly_rate_kes"))
        if listed_kes is None or listed_kes <= 0:
            excluded["invalid_hourly_usd"] += 1
            continue

        description = build_description(mentor, skills)
        staged = {
            "source_dataset": SOURCE_DATASET,
            "job_title": _normalize_text(mentor.get("specialization")).strip(),
            "raw_description": description,
            "source_country": PLATFORM_COUNTRY,
            "hourly_rate_usd": listed_kes / float(usd_to_kes_rate_anchor),
            "industry_partition": partition,
            "observation_timestamp_utc": platform_timestamp_utc(mentor.get("joined_at")),
        }
        # Same gate as every other source, so nothing reaches training that
        # the Upwork rows would not have been allowed to.
        reason = marketplace_exclusion_reason(
            staged, usd_to_kes_rate_anchor, min_description_length, min_hourly_rate_kes, max_hourly_rate_kes
        )
        if reason is not None:
            excluded[reason] += 1
            continue

        act = activity.get(user_id, PlatformActivity())
        hourly_rate_usd = float(staged["hourly_rate_usd"])
        records.append(
            {
                "source_dataset": SOURCE_DATASET,
                "job_title": staged["job_title"],
                "raw_description": description,
                "source_country": PLATFORM_COUNTRY,
                "industry_partition": partition,
                "hourly_rate": round(hourly_rate_usd * float(usd_to_kes_rate_anchor), 2),
                "hourly_rate_usd": round(hourly_rate_usd, 2),
                "currency": "KES",
                "usd_to_kes_rate_anchor": float(usd_to_kes_rate_anchor),
                "observation_timestamp_utc": staged["observation_timestamp_utc"],
                "platform_mentor_profile_id": profile_id,
                "platform_mentor_user_id": user_id,
                "platform_category": _normalize_text(mentor.get("category")).strip(),
                "platform_specialization": staged["job_title"],
                "platform_tier": _normalize_text(mentor.get("tier")).strip(),
                "platform_mentor_type": _normalize_text(mentor.get("mentor_type")).strip(),
                "platform_verification_status": _normalize_text(mentor.get("verification_status")).strip(),
                "platform_experience_years": _safe_float_any(mentor.get("experience_years")),
                "platform_city": _normalize_text(mentor.get("city")).strip(),
                "platform_rating": _safe_float_any(mentor.get("rating")),
                "platform_total_reviews": _safe_float_any(mentor.get("total_reviews")),
                "platform_skills": "|".join(skills),
                "listed_hourly_rate_kes": round(listed_kes, 2),
                "realised_hourly_rate_kes": round(statistics.median(act.completed_rates), 2) if act.completed_rates else None,
                "completed_sessions": act.completed,
                "no_show_rate": round(act.no_shows / act.judged, 4) if act.judged else None,
                "mean_review_rating": round(statistics.fmean(act.review_ratings), 2) if act.review_ratings else None,
                "review_count": len(act.review_ratings),
            }
        )
        partitions[partition] += 1

    return PlatformIngestResult(records=records, mentors_seen=len(mentors), excluded=excluded, partitions=partitions)


def export_platform_records_csv(records: List[Dict[str, Any]], output_path: str) -> None:
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(OUTPUT_FIELDS))
        writer.writeheader()
        for row in records:
            writer.writerow(row)


# ── CLI ─────────────────────────────────────────────────────────────────────


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch the Career Mentor OS platform dataset and harmonize its mentors for pricing.")
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR, help="where the raw CSVs are written and read")
    parser.add_argument("--offline", action="store_true", help="read the cache directory; do not call the platform API")
    parser.add_argument("--output-csv", default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--output-parquet", default=DEFAULT_OUTPUT_PARQUET)
    parser.add_argument("--usd-to-kes-rate-anchor", type=float, default=USD_TO_KES_RATE_ANCHOR)
    parser.add_argument("--summary-json", default=None, help="optional path for the run summary")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    if not args.offline:
        client = PlatformDatasetClient.from_env()
        try:
            fetched = client.fetch_all(args.cache_dir)
        finally:
            client.close()
        for name, path in fetched.items():
            print(f"fetched {name}.csv -> {path}")

    result = build_platform_records(args.cache_dir, usd_to_kes_rate_anchor=args.usd_to_kes_rate_anchor)
    export_platform_records_csv(result.records, args.output_csv)
    export_harmonized_records_parquet(result.records, args.output_parquet)

    summary = result.summary()
    summary["output_csv"] = args.output_csv
    summary["output_parquet"] = args.output_parquet
    if args.summary_json:
        os.makedirs(os.path.dirname(args.summary_json) or ".", exist_ok=True)
        with open(args.summary_json, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2, sort_keys=True)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
