import argparse
import csv
import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Sequence

from src.ingest_multisource import PROJECT_ROOT, map_country_to_iso2


def _resolve_default_tariff_csv() -> str:
    candidates = [
        os.path.join(PROJECT_ROOT, "data", "raw", "Mpesa_Tarrifs", "tarrifs.csv"),
        os.path.join(PROJECT_ROOT, "tests", "fixtures", "raw", "Mpesa_Tarrifs", "tarrifs_full_schedule.csv"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return candidates[0]


DEFAULT_MPESA_TARIFF_CSV = _resolve_default_tariff_csv()
DEFAULT_DOMESTIC_MENTOR_ISO2 = "KE"
DEFAULT_CURRENCY = "KES"


@dataclass(frozen=True)
class MpesaTariffBand:
    min_amount_kes: float
    max_amount_kes: float
    fee_kes: float

    def includes(self, amount_kes: float) -> bool:
        return self.min_amount_kes <= amount_kes <= self.max_amount_kes


def _safe_float(value: Any) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric tariff value: {value!r}") from exc


def load_consumer_transfer_tariff_bands(csv_path: str = DEFAULT_MPESA_TARIFF_CSV) -> List[MpesaTariffBand]:
    bands: List[MpesaTariffBand] = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            category = (row.get("tariff_category") or "").strip()
            transaction_type = (row.get("transaction_type") or "").strip()
            if category != "CONSUMER_TRANSFER" or transaction_type != "P2P_MPESA":
                continue

            bands.append(
                MpesaTariffBand(
                    min_amount_kes=_safe_float(row.get("min_amount_kes")),
                    max_amount_kes=_safe_float(row.get("max_amount_kes")),
                    fee_kes=_safe_float(row.get("fee_kes")),
                )
            )

    if not bands:
        raise ValueError(f"No CONSUMER_TRANSFER/P2P_MPESA tariff bands found in '{csv_path}'.")

    return _repair_overlapping_bands(bands)


def _repair_overlapping_bands(raw_bands: Sequence[MpesaTariffBand]) -> List[MpesaTariffBand]:
    repaired: List[MpesaTariffBand] = []
    for band in raw_bands:
        if not repaired:
            repaired.append(band)
            continue

        previous = repaired[-1]
        if band.min_amount_kes <= previous.max_amount_kes and band.max_amount_kes > previous.max_amount_kes:
            repaired.append(
                MpesaTariffBand(
                    min_amount_kes=previous.max_amount_kes + 1.0,
                    max_amount_kes=band.max_amount_kes,
                    fee_kes=band.fee_kes,
                )
            )
            continue

        if band.max_amount_kes <= previous.max_amount_kes:
            continue

        repaired.append(band)

    return repaired


def derive_quote_protection_bands(raw_bands: Sequence[MpesaTariffBand]) -> List[MpesaTariffBand]:
    if not raw_bands:
        raise ValueError("At least one raw M-Pesa tariff band is required.")

    normalized: List[MpesaTariffBand] = []
    current = raw_bands[0]

    for next_band in raw_bands[1:]:
        contiguous = next_band.min_amount_kes <= current.max_amount_kes + 1.0
        same_fee = next_band.fee_kes == current.fee_kes
        near_fee = (
            current.fee_kes > 0.0
            and next_band.fee_kes > 0.0
            and abs(next_band.fee_kes - current.fee_kes) <= 4.0
            and next_band.max_amount_kes <= 5000.0
        )

        if contiguous and (same_fee or near_fee):
            merged_fee = current.fee_kes if same_fee else round((current.fee_kes + next_band.fee_kes) / 2.0, 2)
            current = MpesaTariffBand(
                min_amount_kes=current.min_amount_kes,
                max_amount_kes=next_band.max_amount_kes,
                fee_kes=merged_fee,
            )
            continue

        normalized.append(current)
        current = next_band

    normalized.append(current)
    return normalized


class MpesaTariffEvaluator:
    """Apply domestic M-Pesa surcharge protection to Kenyan rate recommendations."""

    def __init__(self, quote_bands: Sequence[MpesaTariffBand], currency: str = DEFAULT_CURRENCY) -> None:
        if not quote_bands:
            raise ValueError("quote_bands cannot be empty.")
        self.quote_bands = list(sorted(quote_bands, key=lambda band: (band.min_amount_kes, band.max_amount_kes)))
        self.currency = currency

    @classmethod
    def from_csv(cls, csv_path: str = DEFAULT_MPESA_TARIFF_CSV) -> "MpesaTariffEvaluator":
        raw_bands = load_consumer_transfer_tariff_bands(csv_path)
        return cls(quote_bands=derive_quote_protection_bands(raw_bands))

    def find_band(self, amount_kes: float) -> MpesaTariffBand:
        if amount_kes < 0.0:
            raise ValueError("amount_kes must be non-negative.")

        for band in self.quote_bands:
            if band.includes(amount_kes):
                return band

        if amount_kes > self.quote_bands[-1].max_amount_kes:
            return self.quote_bands[-1]

        raise ValueError(f"No tariff band covers amount {amount_kes} KES.")

    def compute_surcharge(self, base_rate_kes: float, mentor_country: str) -> float:
        amount = float(base_rate_kes)
        if amount < 0.0:
            raise ValueError("base_rate_kes must be non-negative.")

        mentor_iso2 = map_country_to_iso2(mentor_country, default_iso2_code="ZZ")
        if mentor_iso2 != DEFAULT_DOMESTIC_MENTOR_ISO2:
            return 0.0

        band = self.find_band(amount)
        return float(band.fee_kes)

    def evaluate_quote(self, base_predicted_rate: float, mentor_country: str) -> Dict[str, Any]:
        surcharge = self.compute_surcharge(base_predicted_rate, mentor_country)
        final_quoted_rate = float(base_predicted_rate) + surcharge
        mentor_iso2 = map_country_to_iso2(mentor_country, default_iso2_code="ZZ")
        applied_band = self.find_band(float(base_predicted_rate)) if mentor_iso2 == DEFAULT_DOMESTIC_MENTOR_ISO2 else None

        return {
            "base_predicted_rate": round(float(base_predicted_rate), 2),
            "mpesa_tariff_surcharge": round(float(surcharge), 2),
            "final_quoted_rate": round(float(final_quoted_rate), 2),
            "currency": self.currency,
            "mentor_country_iso2": mentor_iso2,
            "applied_tariff_band": asdict(applied_band) if applied_band else None,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate domestic M-Pesa tariff protection for a predicted rate.")
    parser.add_argument("--base-rate", type=float, default=4500.0, help="Base predicted rate in KES")
    parser.add_argument("--mentor-country", default="KE", help="Mentor country used to decide domestic surcharge")
    parser.add_argument("--tariff-csv", default=DEFAULT_MPESA_TARIFF_CSV, help="Path to the raw M-Pesa tariff CSV")
    parser.add_argument("--show-bands", action="store_true", help="Include the derived quote bands in the output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    evaluator = MpesaTariffEvaluator.from_csv(args.tariff_csv)
    payload = evaluator.evaluate_quote(base_predicted_rate=args.base_rate, mentor_country=args.mentor_country)
    if args.show_bands:
        payload["quote_bands"] = [asdict(band) for band in evaluator.quote_bands]
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

