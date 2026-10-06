"""Dated Kenyan M-Pesa P2P fee illustration for KES/hour point quotes.

The pricing pipeline computes its fee-free base and floor/corridor first, then
adds exactly one configured transfer-to-M-PESA-user fee to the base. The final
quote may lie outside that corridor. A one-hour transfer is an illustration,
not an executed payment or a guarantee of the fee on a future transaction.

The protected gateway, not this evaluator, verifies mentor identity and country.
Only KE mentors receive this fee; non-KE mentors bypass the schedule. The loader
accepts the exact 15 ordered P2P bands spanning 1..250000 KES, without blending or
extrapolation. Production approval requires an independent live-source review
and trusted file digest; hashing a file is not evidence its tariffs are current.

Other-network transfers, withdrawals, Pochi, Buy Goods and till tariffs remain
reference-only catalog data. Visa/bank and other payment rails are unsupported,
not implicitly free alternatives selected here.

See ../docs/README.md (glossary) and ../docs/M11.3_Mpesa_Tariff.md
(dated schedule, payer/rail scope and production release gate).
"""

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Sequence

from src.ingest_multisource import PROJECT_ROOT, map_country_to_iso2


DEFAULT_MPESA_TARIFF_CSV = os.path.join(PROJECT_ROOT, "config", "tariffs", "mpesa_p2p_users_2026-08-04.csv")
DEFAULT_DOMESTIC_MENTOR_ISO2 = "KE"
DEFAULT_CURRENCY = "KES"
EXPECTED_TARIFF_RANGES = (
    (1, 49), (50, 100), (101, 500), (501, 1000), (1001, 1500),
    (1501, 2500), (2501, 3500), (3501, 5000), (5001, 7500),
    (7501, 10000), (10001, 15000), (15001, 20000),
    (20001, 35000), (35001, 50000), (50001, 250000),
)


class TariffUnavailableError(ValueError):
    """The quoted KE amount is outside the configured tariff schedule."""


@dataclass(frozen=True)
class MpesaTariffBand:
    """Immutable inclusive published whole-KES endpoints and flat KES fee."""

    min_amount_kes: float
    max_amount_kes: float
    fee_kes: float

    def includes(self, amount_kes: float) -> bool:
        """Check literal endpoints; cent-valued quote lookup instead uses find_band."""
        return self.min_amount_kes <= amount_kes <= self.max_amount_kes


def _safe_float(value: Any) -> float:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric tariff value: {value!r}") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError("Invalid tariff schedule: amounts and fees must be finite and non-negative")
    return number


def load_consumer_transfer_tariff_bands(csv_path: str = DEFAULT_MPESA_TARIFF_CSV) -> List[MpesaTariffBand]:
    """Load/validate P2P rows only; this helper does not enforce a trusted digest."""
    with open(csv_path, "rb") as handle:
        return _parse_consumer_transfer_tariff_bands(handle.read())


def _parse_consumer_transfer_tariff_bands(contents: bytes) -> List[MpesaTariffBand]:
    bands: List[MpesaTariffBand] = []
    reader = csv.DictReader(io.StringIO(contents.decode("utf-8-sig"), newline=""))
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

    return derive_quote_protection_bands(bands)


def derive_quote_protection_bands(raw_bands: Sequence[MpesaTariffBand]) -> List[MpesaTariffBand]:
    """Preserve configured fees in exactly 15 expected ordered P2P ranges.

    Reject missing/extra/reordered tiers and non-finite, negative or fractional-
    cent fees. This validates structure, not the source's current effective fees.
    """
    if len(raw_bands) != len(EXPECTED_TARIFF_RANGES) or any(
        (band.min_amount_kes, band.max_amount_kes) != expected
        or not math.isfinite(band.fee_kes) or band.fee_kes < 0
        or not math.isclose(band.fee_kes * 100, round(band.fee_kes * 100), rel_tol=0, abs_tol=1e-8)
        for band, expected in zip(raw_bands, EXPECTED_TARIFF_RANGES)
    ):
        raise ValueError("Invalid tariff schedule: expected 15 ordered Kenyan P2P tiers (1-250000 KES)")
    return list(raw_bands)


class MpesaTariffEvaluator:
    """Add one P2P fee to a base quote; callers own identity/country verification.

    This class does not compute a corridor, enforce a reservation floor, select
    other payment rails, or execute/verify payments.
    """

    def __init__(self, quote_bands: Sequence[MpesaTariffBand], currency: str = DEFAULT_CURRENCY,
                 schedule_sha256: str | None = None) -> None:
        self.quote_bands = derive_quote_protection_bands(quote_bands)
        self.currency = currency
        self.schedule_sha256 = schedule_sha256

    @classmethod
    def from_csv(cls, csv_path: str = DEFAULT_MPESA_TARIFF_CSV,
                 trusted_sha256: str | None = None) -> "MpesaTariffEvaluator":
        """Load the exact bytes, record SHA-256 and reject a supplied pin mismatch.

        The pin is optional for library/local use; protected runtime startup
        requires an independently approved pin. File/validation errors propagate.
        """
        if trusted_sha256 is not None and re.fullmatch(r"[0-9a-f]{64}", trusted_sha256) is None:
            raise ValueError("Invalid tariff schedule SHA-256 pin")
        with open(csv_path, "rb") as handle:
            contents = handle.read()
        digest = hashlib.sha256(contents).hexdigest()
        if trusted_sha256 is not None and digest != trusted_sha256:
            raise ValueError("Untrusted tariff schedule: SHA-256 mismatch")
        return cls(quote_bands=_parse_consumer_transfer_tariff_bands(contents), schedule_sha256=digest)

    def find_band(self, amount_kes: float) -> MpesaTariffBand:
        """Find a finite non-negative amount's P2P tier, or raise if out of range.

        The first cent above a whole-KES maximum uses the next tier via ceil;
        values below 1 or above 250000 are never clamped into the schedule.
        """
        amount = _safe_float(amount_kes)
        if amount < self.quote_bands[0].min_amount_kes or amount > self.quote_bands[-1].max_amount_kes:
            raise TariffUnavailableError("No configured M-Pesa tariff covers the predicted rate")

        # Quotes are in cents, while published tier endpoints are whole KES.
        # The first cent above a tier's maximum belongs to the next tier.
        for band in self.quote_bands:
            if math.ceil(amount) <= band.max_amount_kes:
                return band

        raise TariffUnavailableError("No configured M-Pesa tariff covers the predicted rate")

    def compute_surcharge(self, base_rate_kes: float, mentor_country: str) -> float:
        """Return the exact configured KE fee, or zero for a non-KE/unknown country.

        All amounts are validated; only KE amounts require a supported tariff.
        Country normalization is not proof of mentor identity or ownership.
        """
        amount = _safe_float(base_rate_kes)

        mentor_iso2 = map_country_to_iso2(mentor_country, default_iso2_code="ZZ")
        if mentor_iso2 != DEFAULT_DOMESTIC_MENTOR_ISO2:
            return 0.0

        band = self.find_band(amount)
        return float(band.fee_kes)

    def evaluate_quote(self, base_predicted_rate: float, mentor_country: str) -> Dict[str, Any]:
        """Round the base to cents, add one fee and return quote/band metadata.

        Check KE range support before rounding so an unsupported raw amount
        cannot round into range; lookup then uses the rounded base. Return the
        final sum rounded to cents, without floor/corridor clamping.
        """
        amount = _safe_float(base_predicted_rate)
        mentor_iso2 = map_country_to_iso2(mentor_country, default_iso2_code="ZZ")
        if mentor_iso2 == DEFAULT_DOMESTIC_MENTOR_ISO2:
            self.find_band(amount)  # Do not let rounding move an unsupported amount into range.
        base = round(amount, 2)
        surcharge = self.compute_surcharge(base, mentor_country)
        final_quoted_rate = base + surcharge
        applied_band = self.find_band(base) if mentor_iso2 == DEFAULT_DOMESTIC_MENTOR_ISO2 else None

        return {
            "base_predicted_rate": base,
            "mpesa_tariff_surcharge": round(float(surcharge), 2),
            "final_quoted_rate": round(float(final_quoted_rate), 2),
            "currency": self.currency,
            "mentor_country_iso2": mentor_iso2,
            "applied_tariff_band": asdict(applied_band) if applied_band else None,
        }


def parse_args() -> argparse.Namespace:
    """Parse local fee-illustration CLI arguments, without gateway authentication."""
    parser = argparse.ArgumentParser(description="Evaluate domestic M-Pesa tariff protection for a predicted rate.")
    parser.add_argument("--base-rate", type=float, default=4500.0, help="Base predicted rate in KES")
    parser.add_argument("--mentor-country", default="KE", help="Mentor country used to decide domestic surcharge")
    parser.add_argument("--tariff-csv", default=DEFAULT_MPESA_TARIFF_CSV, help="Path to the raw M-Pesa tariff CSV")
    parser.add_argument("--show-bands", action="store_true", help="Include the derived quote bands in the output")
    return parser.parse_args()


def main() -> None:
    """Print a local quote illustration, optionally including the configured bands."""
    args = parse_args()
    evaluator = MpesaTariffEvaluator.from_csv(args.tariff_csv)
    payload = evaluator.evaluate_quote(base_predicted_rate=args.base_rate, mentor_country=args.mentor_country)
    if args.show_bands:
        payload["quote_bands"] = [asdict(band) for band in evaluator.quote_bands]
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
