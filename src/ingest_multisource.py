import argparse
import csv
import json
import os
import re
from datetime import datetime, timezone
from statistics import median
from typing import Dict, Iterable, List, Optional, Tuple

PPP_SERIES_CODE = "PA.NUS.PPP"

# Target set from M1.1 acceptance criteria.
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

YEAR_PATTERN = re.compile(r"(\d{4})")


def find_file_in_dir(root_dir: str, name_contains: str, extension: str = ".csv") -> str:
    """Recursively find the first file matching a token and extension."""
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


def _year_columns(fieldnames: Iterable[str]) -> List[Tuple[int, str]]:
    columns: List[Tuple[int, str]] = []
    for column in fieldnames:
        match = YEAR_PATTERN.search(column)
        if match:
            columns.append((int(match.group(1)), column))
    columns.sort(reverse=True)
    return columns


def extract_latest_ppp_by_iso3(wdi_csv_path: str) -> Dict[str, Dict[str, object]]:
    """Extract latest available PPP value per ISO-3 code for PA.NUS.PPP."""
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
    """Extract cost-of-living metrics by ISO-2 code for mapped countries."""
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


def build_macro_lookup(raw_data_dir: str, output_path: str) -> Dict[str, object]:
    wdi_root = os.path.join(raw_data_dir, "World_Development_Indicators")
    cost_root = os.path.join(raw_data_dir, "Cost_Index")

    wdi_csv_path = find_file_in_dir(wdi_root, name_contains="_Data")
    cost_csv_path = find_file_in_dir(cost_root, name_contains="Cost_of_Living_Index")

    ppp_by_iso3 = extract_latest_ppp_by_iso3(wdi_csv_path)
    cost_by_iso2 = extract_cost_index_by_iso2(cost_csv_path)
    fallback_col = _fallback_cost_index_value(cost_by_iso2)

    records: Dict[str, Dict[str, object]] = {}

    for iso2, iso3 in TARGET_ISO2_TO_ISO3.items():
        ppp_info = ppp_by_iso3.get(iso3)
        if ppp_info is None:
            raise ValueError(f"Missing PPP record for target country {iso2}/{iso3}")

        cost_info = cost_by_iso2.get(iso2)
        fallback_used = cost_info is None

        records[iso2] = {
            "country_iso2": iso2,
            "country_iso3": iso3,
            "country_name": ISO2_TO_COUNTRY_NAME[iso2],
            "ppp_lcu_per_intl_dollar": float(ppp_info["ppp_lcu_per_intl_dollar"]),
            "ppp_reference_year": int(ppp_info["year"]),
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
    """Load the generated lookup table from local disk."""
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
    """Return a country record with a safe fallback."""
    normalized = (iso2_code or "").strip().upper()
    if normalized in records:
        return records[normalized]

    if default_iso2_code in records:
        return records[default_iso2_code]

    raise KeyError(f"Neither '{normalized}' nor fallback '{default_iso2_code}' exist in lookup records.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build macroeconomic lookup table from raw data files.")
    parser.add_argument(
        "--raw-dir",
        default=os.path.join("data", "raw"),
        help="Root directory containing raw CSV datasets.",
    )
    parser.add_argument(
        "--output",
        default=os.path.join("data", "processed", "macro_lookup_table.json"),
        help="Output path for the generated macro lookup JSON.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_macro_lookup(raw_data_dir=args.raw_dir, output_path=args.output)
    print(
        f"Wrote {len(payload['records'])} macro records to {os.path.abspath(args.output)}"
    )


if __name__ == "__main__":
    main()

