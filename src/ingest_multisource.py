import argparse
import csv
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Tuple, cast

PPP_SERIES_CODE = "PA.NUS.PPP"
USD_TO_KES_RATE_ANCHOR = 130.0
MIN_DESCRIPTION_LENGTH = 40
MIN_ACCEPTED_HOURLY_RATE_KES = 500.0
MAX_ACCEPTED_HOURLY_RATE_KES = 35000.0
BILATERAL_ALPHA = 0.50

DEFAULT_MACRO_OUTPUT = os.path.join("data", "processed", "macro_lookup_table.json")
DEFAULT_HARMONIZED_OUTPUT = os.path.join("data", "processed", "harmonized_marketplace_corpus.csv")
DEFAULT_HARMONIZED_PARQUET_OUTPUT = os.path.join("data", "processed", "harmonized_marketplace_corpus.parquet")

SUPPORTED_INDUSTRY_PARTITIONS = (
    "data_ai",
    "web_backend",
    "mobile",
    "devops_cloud",
    "design_creative",
    "product_management",
    "digital_marketing",
    "general_tech",
)

INDUSTRY_KEYWORDS = {
    "data_ai": (
        "data scientist",
        "data science",
        "machine learning",
        "deep learning",
        "artificial intelligence",
        "nlp",
        "llm",
        "computer vision",
        "power bi",
        "tableau",
        "analytics",
        "data analysis",
        "data analyst",
        "statistics",
        "sql",
        "predictive",
    ),
    "web_backend": (
        "full stack",
        "fullstack",
        "backend",
        "front end",
        "frontend",
        "web development",
        "web app",
        "react",
        "angular",
        "vue",
        "node",
        "django",
        "flask",
        "wordpress",
        "shopify",
        "javascript",
        "typescript",
        "api",
    ),
    "mobile": (
        "android",
        "ios",
        "flutter",
        "react native",
        "mobile app",
        "swift",
        "kotlin",
        "xamarin",
    ),
    "devops_cloud": (
        "devops",
        "cloud",
        "aws",
        "azure",
        "gcp",
        "kubernetes",
        "docker",
        "terraform",
        "ci/cd",
        "jenkins",
        "github actions",
        "nginx",
        "linux",
        "microsoft azure",
    ),
    "design_creative": (
        "graphic design",
        "logo",
        "brand",
        "adobe",
        "photoshop",
        "illustrator",
        "video editing",
        "youtube",
        "ui",
        "ux",
        "figma",
        "motion design",
        "branding",
        "creative",
    ),
    "product_management": (
        "product manager",
        "product management",
        "project manager",
        "project management",
        "scrum",
        "agile",
        "roadmap",
        "stakeholder",
        "user story",
        "jira",
    ),
    "digital_marketing": (
        "seo",
        "google ads",
        "facebook ads",
        "social media",
        "media buyer",
        "marketing",
        "email marketing",
        "lead generation",
        "campaign",
        "instagram",
        "search engine optimization",
        "content marketing",
    ),
}

TARGET_ISO2_TO_ISO3 = {
    "KE": "KEN",
    "UG": "UGA",
    "TZ": "TZA",
    "RW": "RWA",
    "US": "USA",
    "GB": "GBR",
    "DE": "DEU",
    "CA": "CAN",
    "IN": "IND",
}

ISO2_TO_COUNTRY_NAME = {
    "KE": "Kenya",
    "UG": "Uganda",
    "TZ": "Tanzania",
    "RW": "Rwanda",
    "US": "United States",
    "GB": "United Kingdom",
    "DE": "Germany",
    "CA": "Canada",
    "IN": "India",
}

COST_INDEX_COUNTRY_TO_ISO2 = {
    "Kenya": "KE",
    "Uganda": "UG",
    "Tanzania": "TZ",
    "Rwanda": "RW",
    "United States": "US",
    "United Kingdom": "GB",
    "Germany": "DE",
    "Canada": "CA",
    "India": "IN",
}

COUNTRY_ALIASES_TO_ISO2 = {
    "us": "US",
    "usa": "US",
    "united states of america": "US",
    "uk": "GB",
    "england": "GB",
    "great britain": "GB",
    "germany": "DE",
    "deutschland": "DE",
    "india": "IN",
    "kenya": "KE",
    "uganda": "UG",
    "tanzania": "TZ",
    "rwanda": "RW",
    "canada": "CA",
}

YEAR_PATTERN = re.compile(r"(\d{4})")
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)


def _resolve_input_dir(path_value: str) -> str:
    if os.path.isabs(path_value):
        return path_value

    cwd_candidate = os.path.abspath(path_value)
    if os.path.isdir(cwd_candidate):
        return cwd_candidate

    return os.path.abspath(os.path.join(PROJECT_ROOT, path_value))


def _resolve_output_path(path_value: str) -> str:
    if os.path.isabs(path_value):
        return path_value

    parent = os.path.dirname(path_value)
    if parent and os.path.isdir(os.path.abspath(parent)):
        return os.path.abspath(path_value)

    return os.path.abspath(os.path.join(PROJECT_ROOT, path_value))


def find_file_in_dir(root_dir: str, name_contains: str, extension: str = ".csv") -> str:
    name_contains_lower = name_contains.lower()
    extension_lower = extension.lower()

    candidates: List[str] = []
    for current_root, _, files in os.walk(root_dir):
        for filename in files:
            lower_name = filename.lower()
            if name_contains_lower in lower_name and lower_name.endswith(extension_lower):
                candidates.append(os.path.join(current_root, filename))

    if not candidates:
        raise FileNotFoundError(
            f"No file found under '{root_dir}' matching token '{name_contains}' and extension '{extension}'."
        )

    candidates.sort()
    return candidates[0]


def _safe_float(value: str) -> Optional[float]:
    if value is None:
        return None
    normalized = value.strip().replace(",", "")
    if normalized in {"", "..", "NA", "N/A", "nan"}:
        return None
    try:
        return float(normalized)
    except ValueError:
        return None


def _safe_float_any(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)

    if value is None:
        return None

    text_value = str(value).strip().replace(",", "").replace("$", "")
    if text_value.endswith("%"):
        text_value = text_value[:-1]

    return _safe_float(text_value)


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    normalized = str(value or "").strip().lower()
    return normalized in {"true", "1", "yes", "y"}


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def map_country_to_iso2(country_value: Any, default_iso2_code: str = "KE") -> str:
    normalized = _normalize_text(country_value).strip()
    if not normalized:
        return default_iso2_code

    upper_code = normalized.upper()
    if len(upper_code) == 2 and upper_code in TARGET_ISO2_TO_ISO3:
        return upper_code

    lower_name = normalized.lower()
    for iso2, country_name in ISO2_TO_COUNTRY_NAME.items():
        if lower_name == country_name.lower():
            return iso2

    if lower_name in COUNTRY_ALIASES_TO_ISO2:
        return COUNTRY_ALIASES_TO_ISO2[lower_name]

    return default_iso2_code


def map_industry_partition(text: str) -> str:
    normalized = _normalize_text(text).lower()
    if not normalized:
        return "general_tech"

    for partition, keywords in INDUSTRY_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return partition

    return "general_tech"


def _extract_hourly_rate_from_upwork_jobs(row: Dict[str, Any]) -> Optional[float]:
    if not _normalize_bool(row.get("is_hourly")):
        return None

    low_rate = _safe_float_any(row.get("hourly_low"))
    high_rate = _safe_float_any(row.get("hourly_high"))

    if low_rate is not None and high_rate is not None:
        return (low_rate + high_rate) / 2.0

    if low_rate is not None:
        return low_rate

    if high_rate is not None:
        return high_rate

    return None


def parse_upwork_jobs_dataset(csv_path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hourly_rate_usd = _extract_hourly_rate_from_upwork_jobs(row)
            if hourly_rate_usd is None:
                continue

            title = _normalize_text(row.get("title"))
            description = _normalize_text(row.get("description"))
            text_blob = f"{title} {description}".strip()
            rows.append(
                {
                    "source_dataset": "upwork_jobs",
                    "job_title": title,
                    "raw_description": description,
                    "source_country": _normalize_text(row.get("country")),
                    "hourly_rate_usd": hourly_rate_usd,
                    "industry_partition": map_industry_partition(text_blob),
                }
            )

    return rows


def parse_data_scientist_upwork_dataset(csv_path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hourly_rate_usd = _safe_float_any(row.get("hourlyRate"))
            if hourly_rate_usd is None:
                continue

            title = _normalize_text(row.get("title"))
            description = _normalize_text(row.get("description"))
            skills = _normalize_text(row.get("skills"))
            text_blob = f"{title} {skills} {description}".strip()
            rows.append(
                {
                    "source_dataset": "upwork_data_scientists",
                    "job_title": title,
                    "raw_description": description,
                    "source_country": _normalize_text(row.get("country")),
                    "hourly_rate_usd": hourly_rate_usd,
                    "industry_partition": map_industry_partition(text_blob),
                }
            )

    return rows


def harmonize_marketplace_corpus(
    raw_data_dir: str,
    usd_to_kes_rate_anchor: float = USD_TO_KES_RATE_ANCHOR,
    min_description_length: int = MIN_DESCRIPTION_LENGTH,
    min_hourly_rate_kes: float = MIN_ACCEPTED_HOURLY_RATE_KES,
    max_hourly_rate_kes: float = MAX_ACCEPTED_HOURLY_RATE_KES,
) -> List[Dict[str, Any]]:
    upwork_jobs_root = os.path.join(raw_data_dir, "upwork-jobs.csv")
    upwork_profiles_root = os.path.join(raw_data_dir, "Data_Scientist_Upwork")

    upwork_jobs_csv = find_file_in_dir(upwork_jobs_root, name_contains="upwork-jobs")
    upwork_profiles_csv = find_file_in_dir(upwork_profiles_root, name_contains="upwork_data_scientists")

    staged = parse_upwork_jobs_dataset(upwork_jobs_csv)
    staged.extend(parse_data_scientist_upwork_dataset(upwork_profiles_csv))

    records: List[Dict[str, Any]] = []
    for row in staged:
        description = _normalize_text(row.get("raw_description"))
        if len(description) < min_description_length:
            continue

        industry_partition = _normalize_text(row.get("industry_partition"))
        if not industry_partition:
            continue

        hourly_rate_usd = _safe_float_any(row.get("hourly_rate_usd"))
        if hourly_rate_usd is None or hourly_rate_usd <= 0:
            continue

        hourly_rate_kes = hourly_rate_usd * float(usd_to_kes_rate_anchor)
        if hourly_rate_kes < min_hourly_rate_kes or hourly_rate_kes > max_hourly_rate_kes:
            continue

        records.append(
            {
                "source_dataset": row["source_dataset"],
                "job_title": _normalize_text(row.get("job_title")),
                "raw_description": description,
                "source_country": _normalize_text(row.get("source_country")),
                "industry_partition": industry_partition,
                "hourly_rate": round(hourly_rate_kes, 2),
                "hourly_rate_usd": round(hourly_rate_usd, 2),
                "currency": "KES",
                "usd_to_kes_rate_anchor": float(usd_to_kes_rate_anchor),
            }
        )

    return records


def preview_harmonized_records(records: List[Dict[str, Any]], limit: int = 5) -> str:
    if limit <= 0:
        limit = 5

    preview_payload = {
        "record_count": len(records),
        "preview": records[:limit],
    }
    return json.dumps(preview_payload, indent=2, ensure_ascii=False)


def export_harmonized_records(records: List[Dict[str, Any]], output_path: str) -> None:
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    _, ext = os.path.splitext(output_path)
    if ext.lower() == ".json":
        payload = {
            "metadata": {
                "currency": "KES",
                "record_count": len(records),
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            "records": records,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
        return

    fieldnames = [
        "source_dataset",
        "job_title",
        "raw_description",
        "source_country",
        "industry_partition",
        "hourly_rate",
        "hourly_rate_usd",
        "currency",
        "usd_to_kes_rate_anchor",
    ]
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in records:
            writer.writerow(row)


def _year_columns(fieldnames: Iterable[str]) -> List[Tuple[int, str]]:
    columns: List[Tuple[int, str]] = []
    for column in fieldnames:
        match = YEAR_PATTERN.search(column)
        if match:
            columns.append((int(match.group(1)), column))
    columns.sort(reverse=True)
    return columns


def extract_latest_ppp_by_iso3(wdi_csv_path: str) -> Dict[str, Dict[str, object]]:
    with open(wdi_csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Missing CSV headers in {wdi_csv_path}")

        year_cols = _year_columns(reader.fieldnames)
        if not year_cols:
            raise ValueError(f"No year columns detected in {wdi_csv_path}")

        ppp_by_iso3: Dict[str, Dict[str, object]] = {}
        for row in reader:
            if row.get("Series Code") != PPP_SERIES_CODE:
                continue

            iso3 = (row.get("Country Code") or "").strip().upper()
            if len(iso3) != 3 or not iso3.isalpha():
                continue

            latest_year = None
            latest_ppp = None
            for year, col in year_cols:
                maybe_value = _safe_float(row.get(col, ""))
                if maybe_value is not None:
                    latest_year = year
                    latest_ppp = maybe_value
                    break

            if latest_ppp is None:
                continue

            ppp_by_iso3[iso3] = {
                "country_name": (row.get("Country Name") or "").strip(),
                "year": latest_year,
                "ppp_lcu_per_intl_dollar": latest_ppp,
            }

    return ppp_by_iso3


def extract_cost_index_by_iso2(cost_csv_path: str) -> Dict[str, Dict[str, float]]:
    by_iso2: Dict[str, Dict[str, float]] = {}
    with open(cost_csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            country_name = (row.get("Country") or "").strip()
            iso2 = COST_INDEX_COUNTRY_TO_ISO2.get(country_name)
            if not iso2:
                continue

            cost_idx = _safe_float(row.get("Cost of Living Index", ""))
            rent_idx = _safe_float(row.get("Rent Index", ""))
            pp_idx = _safe_float(row.get("Local Purchasing Power Index", ""))
            if cost_idx is None:
                continue

            by_iso2[iso2] = {
                "cost_of_living_index": cost_idx,
                "rent_index": rent_idx if rent_idx is not None else 0.0,
                "local_purchasing_power_index": pp_idx if pp_idx is not None else 0.0,
            }

    return by_iso2


def _fallback_cost_index_value(cost_data: Dict[str, Dict[str, float]]) -> float:
    regional_sources = [
        cost_data.get("KE", {}).get("cost_of_living_index"),
        cost_data.get("UG", {}).get("cost_of_living_index"),
        cost_data.get("TZ", {}).get("cost_of_living_index"),
    ]
    values = [v for v in regional_sources if isinstance(v, (int, float))]
    return float(median(values)) if values else 30.0


def extract_mpesa_tariff_summary(mpesa_csv_path: str) -> Dict[str, object]:
    total_rows = 0
    unique_categories = set()
    unique_tx_types = set()
    consumer_transfer_rows = 0
    max_fee = 0.0

    with open(mpesa_csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            category = (row.get("tariff_category") or "").strip()
            tx_type = (row.get("transaction_type") or "").strip()
            if category:
                unique_categories.add(category)
            if tx_type:
                unique_tx_types.add(tx_type)

            if category == "CONSUMER_TRANSFER" and tx_type == "P2P_MPESA":
                consumer_transfer_rows += 1

            fee = _safe_float(row.get("fee_kes", ""))
            if fee is not None and fee > max_fee:
                max_fee = fee

    return {
        "row_count": total_rows,
        "category_count": len(unique_categories),
        "transaction_type_count": len(unique_tx_types),
        "consumer_transfer_band_count": consumer_transfer_rows,
        "max_fee_kes": max_fee,
    }


def build_macro_lookup(raw_data_dir: str, output_path: str) -> Dict[str, object]:
    wdi_root = os.path.join(raw_data_dir, "World_Development_Indicators")
    cost_root = os.path.join(raw_data_dir, "Cost_Index")
    mpesa_root = os.path.join(raw_data_dir, "Mpesa_Tarrifs")

    wdi_csv_path = find_file_in_dir(wdi_root, name_contains="_Data")
    cost_csv_path = find_file_in_dir(cost_root, name_contains="Cost_of_Living_Index")
    mpesa_csv_path = find_file_in_dir(mpesa_root, name_contains="tarrifs")

    ppp_by_iso3 = extract_latest_ppp_by_iso3(wdi_csv_path)
    cost_by_iso2 = extract_cost_index_by_iso2(cost_csv_path)
    mpesa_summary = extract_mpesa_tariff_summary(mpesa_csv_path)
    fallback_col = _fallback_cost_index_value(cost_by_iso2)

    records: Dict[str, Dict[str, object]] = {}
    for iso2, iso3 in TARGET_ISO2_TO_ISO3.items():
        ppp_info = ppp_by_iso3.get(iso3)
        if ppp_info is None:
            raise ValueError(f"Missing PPP record for target country {iso2}/{iso3}")
        ppp_info = cast(Dict[str, Any], ppp_info)
        ppp_value = float(cast(float, ppp_info["ppp_lcu_per_intl_dollar"]))
        ppp_year = int(cast(int, ppp_info["year"]))

        cost_info = cost_by_iso2.get(iso2)
        fallback_used = cost_info is None

        records[iso2] = {
            "country_iso2": iso2,
            "country_iso3": iso3,
            "country_name": ISO2_TO_COUNTRY_NAME[iso2],
            "ppp_lcu_per_intl_dollar": ppp_value,
            "ppp_reference_year": ppp_year,
            "cost_of_living_index": float(cost_info["cost_of_living_index"]) if cost_info else fallback_col,
            "rent_index": float(cost_info["rent_index"]) if cost_info else 0.0,
            "local_purchasing_power_index": float(cost_info["local_purchasing_power_index"]) if cost_info else 0.0,
            "cost_index_fallback_used": fallback_used,
            "sources": {
                "ppp": os.path.basename(wdi_csv_path),
                "cost_of_living": os.path.basename(cost_csv_path) if not fallback_used else "fallback_seed",
            },
        }

    payload: Dict[str, object] = {
        "metadata": {
            "indicator_series_code": PPP_SERIES_CODE,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "raw_data_dir": os.path.abspath(raw_data_dir),
            "target_economies": list(TARGET_ISO2_TO_ISO3.keys()),
            "mpesa_tariffs": {
                "source_file": os.path.basename(mpesa_csv_path),
                "summary": mpesa_summary,
            },
        },
        "records": records,
    }

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)

    return payload


def load_macro_lookup_table(lookup_json_path: str) -> Dict[str, Dict[str, object]]:
    with open(lookup_json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    records = payload.get("records")
    if not isinstance(records, dict):
        raise ValueError("Invalid macro lookup payload: 'records' must be a dictionary.")

    return records


def get_macro_record(
    records: Dict[str, Dict[str, object]],
    iso2_code: str,
    default_iso2_code: str = "KE",
) -> Dict[str, object]:
    normalized = (iso2_code or "").strip().upper()
    if normalized in records:
        return records[normalized]

    if default_iso2_code in records:
        return records[default_iso2_code]

    raise KeyError(f"Neither '{normalized}' nor fallback '{default_iso2_code}' exist in lookup records.")


def compute_bilateral_arbitrage_factor(
    mentor_iso2_code: str,
    client_iso2_code: str,
    macro_records: Dict[str, Dict[str, object]],
    alpha: float = BILATERAL_ALPHA,
) -> float:
    mentor_iso2 = map_country_to_iso2(mentor_iso2_code)
    client_iso2 = map_country_to_iso2(client_iso2_code)

    if mentor_iso2 == client_iso2:
        return 1.0

    mentor_record = get_macro_record(macro_records, mentor_iso2, default_iso2_code="KE")
    client_record = get_macro_record(macro_records, client_iso2, default_iso2_code="KE")

    mentor_ppp = _safe_float_any(mentor_record.get("ppp_lcu_per_intl_dollar")) or 1.0
    client_ppp = _safe_float_any(client_record.get("ppp_lcu_per_intl_dollar")) or 1.0
    mentor_col = _safe_float_any(mentor_record.get("cost_of_living_index")) or 1.0
    client_col = _safe_float_any(client_record.get("cost_of_living_index")) or 1.0

    if mentor_ppp <= 0 or client_ppp <= 0 or mentor_col <= 0 or client_col <= 0:
        return 1.0

    ppp_ratio = mentor_ppp / client_ppp
    cost_ratio = client_col / mentor_col
    return float((ppp_ratio ** alpha) * (cost_ratio ** (1.0 - alpha)))


def build_harmonized_marketplace_records(
    raw_data_dir: str,
    macro_lookup_path: str,
    mentor_country_iso2: str = "KE",
    alpha: float = BILATERAL_ALPHA,
    usd_to_kes_rate_anchor: float = USD_TO_KES_RATE_ANCHOR,
    min_description_length: int = MIN_DESCRIPTION_LENGTH,
    min_hourly_rate_kes: float = MIN_ACCEPTED_HOURLY_RATE_KES,
    max_hourly_rate_kes: float = MAX_ACCEPTED_HOURLY_RATE_KES,
) -> List[Dict[str, Any]]:
    macro_records = load_macro_lookup_table(macro_lookup_path)
    marketplace_rows = harmonize_marketplace_corpus(
        raw_data_dir=raw_data_dir,
        usd_to_kes_rate_anchor=usd_to_kes_rate_anchor,
        min_description_length=min_description_length,
        min_hourly_rate_kes=min_hourly_rate_kes,
        max_hourly_rate_kes=max_hourly_rate_kes,
    )

    partition_counts = Counter(_normalize_text(r.get("industry_partition")) for r in marketplace_rows)
    total_rows = len(marketplace_rows)
    max_partition_count = max(partition_counts.values()) if partition_counts else 1

    output_rows: List[Dict[str, Any]] = []
    for row in marketplace_rows:
        industry_partition = _normalize_text(row.get("industry_partition"))
        client_country_iso2 = map_country_to_iso2(row.get("source_country"))
        bilateral_factor = compute_bilateral_arbitrage_factor(
            mentor_iso2_code=mentor_country_iso2,
            client_iso2_code=client_country_iso2,
            macro_records=macro_records,
            alpha=alpha,
        )

        frequency = partition_counts[industry_partition]
        output_rows.append(
            {
                **row,
                "mentor_country_iso2": map_country_to_iso2(mentor_country_iso2),
                "client_country_iso2": client_country_iso2,
                "bilateral_arbitrage_factor": round(bilateral_factor, 6),
                "harmonized_hourly_rate": round(float(row["hourly_rate"]) * bilateral_factor, 2),
                "industry_frequency": frequency,
                "market_saturation_score": round(frequency / total_rows, 6) if total_rows else 0.0,
                "industry_relative_density": round(frequency / max_partition_count, 6) if max_partition_count else 0.0,
                "arbitrage_alpha": float(alpha),
            }
        )

    return output_rows


def export_harmonized_records_parquet(records: List[Dict[str, Any]], output_path: str) -> None:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise RuntimeError("pyarrow is required to export parquet. Install dependencies from requirements.txt") from exc

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    table = pa.Table.from_pylist(records)
    pq.write_table(table, output_path, compression="snappy")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build project ingestion artifacts from raw data files.")
    parser.add_argument(
        "--mode",
        choices=("macro_lookup", "harmonize_corpus", "harmonize_parquet"),
        default="macro_lookup",
        help="Execution mode: macro lookup (M1.1), harmonize corpus (M1.2), or export parquet (M1.3).",
    )
    parser.add_argument(
        "--raw-dir",
        default=os.path.join("data", "raw"),
        help="Root directory containing raw CSV datasets.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_MACRO_OUTPUT,
        help="Output path for generated artifact.",
    )
    parser.add_argument(
        "--preview-limit",
        type=int,
        default=0,
        help="When harmonizing, print a preview of up to N records.",
    )
    parser.add_argument(
        "--usd-to-kes-rate",
        type=float,
        default=USD_TO_KES_RATE_ANCHOR,
        help="USD to KES conversion anchor used for harmonization.",
    )
    parser.add_argument(
        "--min-description-length",
        type=int,
        default=MIN_DESCRIPTION_LENGTH,
        help="Minimum description length for retained harmonized rows.",
    )
    parser.add_argument(
        "--min-hourly-kes",
        type=float,
        default=MIN_ACCEPTED_HOURLY_RATE_KES,
        help="Minimum accepted hourly rate in KES.",
    )
    parser.add_argument(
        "--max-hourly-kes",
        type=float,
        default=MAX_ACCEPTED_HOURLY_RATE_KES,
        help="Maximum accepted hourly rate in KES.",
    )
    parser.add_argument(
        "--macro-lookup",
        default=DEFAULT_MACRO_OUTPUT,
        help="Macro lookup JSON path for M1.3 macro joins.",
    )
    parser.add_argument(
        "--mentor-country",
        default="KE",
        help="Mentor ISO-2 anchor used for bilateral arbitrage factors in M1.3.",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=BILATERAL_ALPHA,
        help="Bilateral arbitrage alpha weight.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    resolved_raw_dir = _resolve_input_dir(args.raw_dir)

    if args.mode == "harmonize_corpus":
        output_arg = args.output if args.output != DEFAULT_MACRO_OUTPUT else DEFAULT_HARMONIZED_OUTPUT
        resolved_output_path = _resolve_output_path(output_arg)

        records = harmonize_marketplace_corpus(
            raw_data_dir=resolved_raw_dir,
            usd_to_kes_rate_anchor=args.usd_to_kes_rate,
            min_description_length=args.min_description_length,
            min_hourly_rate_kes=args.min_hourly_kes,
            max_hourly_rate_kes=args.max_hourly_kes,
        )
        export_harmonized_records(records, resolved_output_path)

        if args.preview_limit > 0:
            print(preview_harmonized_records(records, args.preview_limit))

        print(f"Wrote {len(records)} harmonized marketplace records to {resolved_output_path}")
        return

    if args.mode == "harmonize_parquet":
        output_arg = args.output if args.output != DEFAULT_MACRO_OUTPUT else DEFAULT_HARMONIZED_PARQUET_OUTPUT
        resolved_output_path = _resolve_output_path(output_arg)
        resolved_macro_lookup = _resolve_output_path(args.macro_lookup)

        records = build_harmonized_marketplace_records(
            raw_data_dir=resolved_raw_dir,
            macro_lookup_path=resolved_macro_lookup,
            mentor_country_iso2=args.mentor_country,
            alpha=args.alpha,
            usd_to_kes_rate_anchor=args.usd_to_kes_rate,
            min_description_length=args.min_description_length,
            min_hourly_rate_kes=args.min_hourly_kes,
            max_hourly_rate_kes=args.max_hourly_kes,
        )
        export_harmonized_records_parquet(records, resolved_output_path)

        if args.preview_limit > 0:
            print(preview_harmonized_records(records, args.preview_limit))

        print(f"Wrote {len(records)} harmonized parquet rows to {resolved_output_path}")
        return

    resolved_output_path = _resolve_output_path(args.output)
    payload = build_macro_lookup(raw_data_dir=resolved_raw_dir, output_path=resolved_output_path)
    records = cast(Dict[str, Dict[str, Any]], payload.get("records", {}))
    print(f"Wrote {len(records)} macro records to {resolved_output_path}")


if __name__ == "__main__":
    main()
