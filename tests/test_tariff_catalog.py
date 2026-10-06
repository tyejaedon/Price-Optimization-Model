"""Other Safaricom rails are recorded for future work, never priced as P2P."""

import csv
import unittest
from collections import Counter
from decimal import Decimal
from pathlib import Path

from src.tariff_evaluator import DEFAULT_MPESA_TARIFF_CSV, MpesaTariffEvaluator


ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "config" / "tariffs" / "mpesa_other_services_2026-08-04.csv"


class OtherTariffCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with CATALOG.open(encoding="utf-8", newline="") as handle:
            cls.rows = list(csv.DictReader(handle))

    def test_catalog_is_complete_and_kept_out_of_p2p_quote_path(self) -> None:
        expected = {
            "TRANSFER_OTHER_NETWORK": 15, "WITHDRAW_AGENT": 15,
            "TRANSFER_POCHI": 8, "WITHDRAW_ATM": 4,
            "FREE_DEPOSIT": 1, "FREE_REGISTRATION": 1, "FREE_AIRTIME": 1,
            "FREE_BALANCE_ENQUIRY": 1, "FREE_PIN_CHANGE": 1,
            "RECEIVE_BUY_GOODS": 4, "TILL_PAY_MOBILE": 18, "TILL_PAY_PAYBILL": 18,
        }
        self.assertEqual(Counter(row["service"] for row in self.rows), expected)
        self.assertEqual(len(self.rows), 87)
        with self.assertRaisesRegex(ValueError, "15 ordered Kenyan P2P tiers"):
            MpesaTariffEvaluator.from_csv(str(CATALOG))

        # Only the versioned transfer-to-M-PESA-user CSV is a default quote input.
        p2p = MpesaTariffEvaluator.from_csv(DEFAULT_MPESA_TARIFF_CSV)
        self.assertEqual(p2p.compute_surcharge(2500, "KE"), 33)
        self.assertEqual(p2p.compute_surcharge(2500, "US"), 0)
        other_network = [row for row in self.rows if row["service"] == "TRANSFER_OTHER_NETWORK"]
        self.assertEqual([(float(row["min_amount_kes"]), float(row["max_amount_kes"]),
                           float(row["fee_kes"])) for row in other_network],
                         [(band.min_amount_kes, band.max_amount_kes, band.fee_kes) for band in p2p.quote_bands])
        self.assertFalse(any("VISA" in row["service"] or "BANK" in row["service"] for row in self.rows))

    def test_flat_percent_free_and_unspecified_are_distinct(self) -> None:
        for row in self.rows:
            with self.subTest(service=row["service"], band=(row["min_amount_kes"], row["max_amount_kes"])):
                self.assertIn(row["payer"], {"CUSTOMER", "MERCHANT", "BUSINESS_TILL"})
                self.assertNotIn(None, row)
                fee, percent = row["fee_kes"], row["fee_percent"]
                self.assertFalse(fee and percent)
                if row["status"] in ("unspecified", "not_available"):
                    self.assertFalse(fee or percent)
                else:
                    self.assertTrue(fee or percent)
                for value in (fee, percent):
                    if value:
                        self.assertGreaterEqual(Decimal(value), 0)
                if row["min_amount_kes"]:
                    self.assertGreaterEqual(Decimal(row["min_amount_kes"]), 0)
                if row["max_amount_kes"]:
                    self.assertGreaterEqual(Decimal(row["max_amount_kes"]), Decimal(row["min_amount_kes"]))

        def entry(service, minimum, maximum):
            return next(r for r in self.rows if r["service"] == service
                        and r["min_amount_kes"] == str(minimum) and r["max_amount_kes"] == str(maximum))

        self.assertEqual(entry("WITHDRAW_AGENT", 1, 49)["status"], "not_available")
        self.assertEqual(entry("WITHDRAW_ATM", 10001, 35000)["fee_kes"], "203.00")
        self.assertEqual(entry("TRANSFER_OTHER_NETWORK", 1501, 2500)["fee_kes"], "33.00")
        self.assertEqual(entry("TRANSFER_POCHI", 2500, 250000)["validity"], "3_months_from_2026-08-01")
        self.assertEqual(entry("RECEIVE_BUY_GOODS", 501, 36363)["fee_percent"], "0.55")
        self.assertEqual(entry("RECEIVE_BUY_GOODS", 36363.01, "")["fee_kes"], "200.00")
        self.assertEqual(entry("TILL_PAY_MOBILE", 1501, 2500)["fee_kes"], "17.00")
        self.assertEqual(entry("TILL_PAY_PAYBILL", 1501, 2500)["fee_kes"], "10.00")
        self.assertEqual(entry("TILL_PAY_PAYBILL", 0, 50)["status"], "unspecified")
