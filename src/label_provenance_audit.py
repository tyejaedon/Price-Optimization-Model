"""Issue #91: aggregate label provenance and observation-time readiness audit."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.ingest_multisource import (
    BILATERAL_ALPHA,
    MAX_ACCEPTED_HOURLY_RATE_KES,
    MIN_ACCEPTED_HOURLY_RATE_KES,
    MIN_DESCRIPTION_LENGTH,
    USD_TO_KES_RATE_ANCHOR,
    find_file_in_dir,
    marketplace_exclusion_reason,
    parse_data_scientist_upwork_dataset,
    parse_observation_timestamp_utc,
    parse_upwork_jobs_dataset,
)
from src.macro_arbitrage import DEFAULT_FEATURE_NAMES

SOURCES = {
    "upwork_jobs": ("upwork-jobs.csv", "upwork-jobs", parse_upwork_jobs_dataset, "posted_hourly_budget_midpoint_usd"),
    "upwork_data_scientists": (
        "Data_Scientist_Upwork", "upwork_data_scientists", parse_data_scientist_upwork_dataset,
        "self_reported_profile_hourly_rate_usd",
    ),
}
FORBIDDEN_FEATURES = frozenset({"target_rate", "hourly_rate", "hourly_rate_usd", "harmonized_hourly_rate"})


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stats(values: Any) -> dict[str, Any]:
    numeric = pd.Series(pd.to_numeric(values, errors="coerce"), dtype=float).replace(
        [np.inf, -np.inf], np.nan
    ).dropna()
    if numeric.empty:
        return {"count": 0, "min": None, "p25": None, "median": None, "p75": None, "max": None}
    return {
        "count": len(numeric), "min": round(float(numeric.min()), 2),
        "p25": round(float(numeric.quantile(0.25)), 2),
        "median": round(float(numeric.median()), 2),
        "p75": round(float(numeric.quantile(0.75)), 2),
        "max": round(float(numeric.max()), 2),
    }


def _group(rows: pd.DataFrame) -> dict[str, Any]:
    result = {}
    for (source, industry), group in rows.groupby(["source_dataset", "industry_partition"], dropna=False):
        timestamps = pd.to_datetime(group.get("observation_timestamp_utc", pd.Series(index=group.index)),
                                    errors="coerce", utc=True)
        pre = pd.Series(pd.to_numeric(group["hourly_rate"], errors="coerce"), index=group.index)
        post = pd.Series(pd.to_numeric(group["harmonized_hourly_rate"], errors="coerce"), index=group.index)
        pre_in_bounds = (pre >= MIN_ACCEPTED_HOURLY_RATE_KES) & (pre <= MAX_ACCEPTED_HOURLY_RATE_KES)
        post_in_bounds = (post >= MIN_ACCEPTED_HOURLY_RATE_KES) & (post <= MAX_ACCEPTED_HOURLY_RATE_KES)
        eligible = pre_in_bounds & post_in_bounds & timestamps.notna()
        result[f"{source}/{industry}"] = {
            "rows": len(group),
            "source_timestamp_present": int(timestamps.notna().sum()),
            "pre_arbitrage_kes": _stats(pre),
            "post_arbitrage_kes": _stats(post),
            "outside_post_bounds": int((~post_in_bounds).sum()),
            "proposed_oot_eligible": int(eligible.sum()),
        }
    return result


def audit_label_provenance(raw_dir: str, parquet_path: str) -> dict[str, Any]:
    """Never export individual rows, raw text, job links, or candidate timestamps."""
    if FORBIDDEN_FEATURES.intersection(DEFAULT_FEATURE_NAMES):
        raise ValueError("Target-derived fields cannot be model metadata features")
    raw_root = Path(raw_dir)
    source_summary: dict[str, Any] = {}
    candidate_counts: Counter[tuple[str, str]] = Counter()
    exclusion_counts: Counter[tuple[str, str, str]] = Counter()
    retained_counts: Counter[tuple[str, str]] = Counter()
    retained_timestamp_counts: Counter[tuple[str, str]] = Counter()
    retained_dates: dict[str, set[str]] = {source: set() for source in SOURCES}
    for source, (folder, token, parse, label_kind) in SOURCES.items():
        path = Path(find_file_in_dir(str(raw_root / folder), token))
        with path.open(encoding="utf-8-sig", newline="") as handle:
            raw_rows = 0
            valid_raw_dates = 0
            for raw in csv.DictReader(handle):
                raw_rows += 1
                valid_raw_dates += bool(parse_observation_timestamp_utc(raw.get("published_date")))
        candidates = parse(str(path))
        for row in candidates:
            key = (source, str(row["industry_partition"]))
            candidate_counts[key] += 1
            reason = marketplace_exclusion_reason(row)
            if reason:
                exclusion_counts[(*key, reason)] += 1
            else:
                retained_counts[key] += 1
                observed = parse_observation_timestamp_utc(row.get("observation_timestamp_utc"))
                if observed:
                    retained_timestamp_counts[key] += 1
                    retained_dates[source].add(observed)
        source_summary[source] = {
            "raw_rows": raw_rows, "priced_candidates": len(candidates),
            "unpriced_or_unparseable": raw_rows - len(candidates),
            "label_kind": label_kind,
            "source_timestamp_column": "published_date" if source == "upwork_jobs" else None,
            "valid_raw_observation_dates": valid_raw_dates,
            "retained_distinct_observation_dates": len(retained_dates[source]),
            "retained_earliest_utc": min(retained_dates[source], default=None),
            "retained_latest_utc": max(retained_dates[source], default=None),
            "source_sha256": _hash_file(path),
        }

    frame = pd.read_parquet(parquet_path)
    required = {"source_dataset", "industry_partition", "hourly_rate_usd", "hourly_rate",
                "harmonized_hourly_rate", "bilateral_arbitrage_factor", "usd_to_kes_rate_anchor"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Missing provenance columns: {sorted(required - set(frame.columns))}")
    if frame.empty or not set(frame.source_dataset).issubset(SOURCES):
        raise ValueError("Empty corpus or unknown pricing-label source")

    usd = pd.to_numeric(frame.hourly_rate_usd, errors="coerce")
    anchor = pd.to_numeric(frame.usd_to_kes_rate_anchor, errors="coerce")
    pre = pd.to_numeric(frame.hourly_rate, errors="coerce")
    post = pd.to_numeric(frame.harmonized_hourly_rate, errors="coerce")
    factor = pd.to_numeric(frame.bilateral_arbitrage_factor, errors="coerce")
    # Both USD and the stored factor are rounded on export; allow only that rounding error.
    valid_pre = np.isfinite(usd) & np.isfinite(anchor) & np.isclose(pre, usd * anchor, atol=0.65, rtol=0)
    valid_post = np.isfinite(factor) & np.isclose(post, pre * factor, atol=0.02, rtol=0)
    if not bool(np.all(valid_pre & valid_post)):
        raise ValueError("Parquet contains invalid USD->KES or bilateral rate transformation")
    if "target_rate" in frame.columns:
        target = pd.to_numeric(frame["target_rate"], errors="coerce")
        if not bool(np.all(np.isfinite(target) & np.isclose(target, post, atol=0.005, rtol=0))):
            raise ValueError("Explicit target_rate overrides the audited harmonized label")

    processed_counts = Counter((str(r.source_dataset), str(r.industry_partition)) for r in
                               frame[["source_dataset", "industry_partition"]].itertuples(index=False))
    rebuild_matches = processed_counts == retained_counts
    group_keys = sorted(set(candidate_counts) | set(processed_counts))
    by_source_industry = {
        f"{source}/{industry}": {
            "priced_candidates": candidate_counts[source, industry],
            "excluded_before_arbitrage": sum(v for (s, i, _), v in exclusion_counts.items()
                                             if (s, i) == (source, industry)),
            "retained_before_arbitrage": retained_counts[source, industry],
            "source_timestamps_on_retained": retained_timestamp_counts[source, industry],
            "processed_rows": processed_counts[source, industry],
        } for source, industry in group_keys
    }
    groups = _group(frame)
    country_coverage = {}
    if "client_country_iso2" in frame.columns:
        country_coverage = {
            f"{source}/{country}": int(n) for (source, country), n in
            frame.groupby(["source_dataset", "client_country_iso2"], dropna=False).size().items()
        }
    timestamp_series = pd.to_datetime(frame.get("observation_timestamp_utc", pd.Series(index=frame.index)),
                                      errors="coerce", utc=True)
    if timestamp_series.notna().any():
        earliest, latest = str(timestamp_series.min()), str(timestamp_series.max())
    else:
        earliest = latest = None
    eligible = sum(g["proposed_oot_eligible"] for g in groups.values())
    job_eligible = sum(g["proposed_oot_eligible"] for k, g in groups.items() if k.startswith("upwork_jobs/"))
    jobs = source_summary["upwork_jobs"]
    possible_job_rows = sum(g["rows"] - g["outside_post_bounds"] for k, g in groups.items()
                            if k.startswith("upwork_jobs/"))
    estimated_after_rebuild = (possible_job_rows if processed_counts == retained_counts and
                               jobs["valid_raw_observation_dates"] == jobs["raw_rows"] else None)
    return {
        "issue": 91,
        "dataset_sha256": _hash_file(Path(parquet_path)),
        "processed_rows": len(frame),
        "sources": source_summary,
        "pre_arbitrage_policy": {
            "usd_to_kes_anchor": USD_TO_KES_RATE_ANCHOR,
            "minimum_description_length": MIN_DESCRIPTION_LENGTH,
            "minimum_kes_per_hour": MIN_ACCEPTED_HOURLY_RATE_KES,
            "maximum_kes_per_hour": MAX_ACCEPTED_HOURLY_RATE_KES,
            "arbitrage_alpha_default": BILATERAL_ALPHA,
            "order": "hourly USD candidate -> description -> USD*anchor KES bounds -> bilateral factor -> label",
        },
        "proposed_oot_policy": {
            "target_population": "posted_upwork_job_budgets_only_not_verified_mentor_rates",
            "rules": "Same pre-arbitrage rule; require source published_date with timezone, and post-arbitrage KES/hour in [500,35000]. Exclude profiles lacking observation time. Choose cutoff without peeking at held-out outcomes; hold out all equal timestamps on one side. Fit all transforms and peer indices on train only.",
            "iqr_handling": "Report IQR for training diagnostics only; no data-dependent outlier trimming or holdout-based exclusions.",
            "retained_rows_with_timestamp_and_post_bounds": eligible,
            "retained_job_budget_rows_with_timestamp_and_post_bounds": job_eligible,
            "estimated_eligible_job_rows_after_source_timestamp_preserving_rebuild": estimated_after_rebuild,
            "estimate_caveat": "Conditional on rebuilding from these same raw rows and verifying row-level date preservation; not OOT metrics or a mentor-rate sample.",
        },
        "source_industry_flow": by_source_industry,
        "exclusions_by_source_industry_reason": {
            f"{s}/{i}/{reason}": n for (s, i, reason), n in sorted(exclusion_counts.items())
        },
        "processed_source_industry_rates": groups,
        "processed_source_country_counts": country_coverage,
        "country_mapping_note": "client_country_iso2 may default to KE when source_country is missing/unrecognized; KE is not necessarily verified origin.",
        "overall_rates": {
            "usd_per_hour": _stats(usd), "pre_arbitrage_kes_per_hour": _stats(pre),
            "post_arbitrage_kes_per_hour": _stats(post),
        },
        "timestamp_coverage": {
            "processed_timestamp_column_present": "observation_timestamp_utc" in frame.columns,
            "processed_valid": int(timestamp_series.notna().sum()),
            "processed_missing": int(timestamp_series.isna().sum()),
            "earliest_utc": earliest, "latest_utc": latest,
        },
        "decision": {
            "raw_candidate_counts_match_parquet": rebuild_matches,
            "current_parquet_can_support_oot": bool(rebuild_matches and job_eligible >= 2 and
                                                    timestamp_series.nunique() >= 2),
            "mentor_rate_oot_supported": False,
            "limitations": "Published dates are job-post times, not verified mentor transaction dates; profile rates have no observation dates. A parquet without source timestamps cannot be chronologically split. Audit source reliability and dataset snapshot before #81; never use export/ingestion time as observation time.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate-only issue #91 pricing label audit")
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--parquet", default="data/processed/harmonized_marketplace_corpus.parquet")
    parser.add_argument("--output", default="reports/label_provenance_audit.json")
    args = parser.parse_args()
    report = audit_label_provenance(args.raw_dir, args.parquet)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(output), "processed_rows": report["processed_rows"],
                      "decision": report["decision"]}, indent=2))


if __name__ == "__main__":
    main()
