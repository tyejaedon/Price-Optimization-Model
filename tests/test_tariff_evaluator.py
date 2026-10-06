import hashlib
import tempfile
import unittest
from pathlib import Path

from src.tariff_evaluator import DEFAULT_MPESA_TARIFF_CSV, MpesaTariffEvaluator, TariffUnavailableError


class MpesaTariffEvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        tariff_csv = repo_root / "tests" / "fixtures" / "raw" / "Mpesa_Tarrifs" / "tarrifs_full_schedule.csv"
        cls.tariff_csv = tariff_csv
        cls.evaluator = MpesaTariffEvaluator.from_csv(str(tariff_csv))

    def test_versioned_release_schedule_matches_the_regression_fixture(self) -> None:
        self.assertEqual(MpesaTariffEvaluator.from_csv(DEFAULT_MPESA_TARIFF_CSV).quote_bands,
                         self.evaluator.quote_bands)

    def test_domestic_4500_case_preserves_seventh_tier_fee(self) -> None:
        surcharge = self.evaluator.compute_surcharge(base_rate_kes=4500.0, mentor_country="KE")

        self.assertEqual(surcharge, 57.0)

    def test_international_mentor_country_returns_zero_surcharge(self) -> None:
        surcharge = self.evaluator.compute_surcharge(base_rate_kes=4500.0, mentor_country="US")

        self.assertEqual(surcharge, 0.0)

    def test_bracket_transitions_are_deterministic(self) -> None:
        self.assertEqual(self.evaluator.compute_surcharge(2500.0, "KE"), 33.0)
        self.assertEqual(self.evaluator.compute_surcharge(2501.0, "KE"), 53.0)
        self.assertEqual(self.evaluator.compute_surcharge(5000.0, "KE"), 57.0)
        self.assertEqual(self.evaluator.compute_surcharge(5001.0, "KE"), 78.0)

    def test_all_fifteen_safaricom_p2p_tiers_and_fractional_transitions(self) -> None:
        tiers = (
            (1, 49, 0), (50, 100, 0), (101, 500, 7), (501, 1000, 13),
            (1001, 1500, 23), (1501, 2500, 33), (2501, 3500, 53),
            (3501, 5000, 57), (5001, 7500, 78), (7501, 10000, 90),
            (10001, 15000, 100), (15001, 20000, 105),
            (20001, 35000, 108), (35001, 50000, 108), (50001, 250000, 108),
        )
        self.assertEqual(len(self.evaluator.quote_bands), len(tiers))
        for index, (minimum, maximum, fee) in enumerate(tiers):
            with self.subTest(tier=index + 1):
                self.assertEqual((self.evaluator.quote_bands[index].min_amount_kes,
                                  self.evaluator.quote_bands[index].max_amount_kes,
                                  self.evaluator.quote_bands[index].fee_kes), (minimum, maximum, fee))
                self.assertEqual(self.evaluator.compute_surcharge(minimum, "KE"), fee)
                self.assertEqual(self.evaluator.compute_surcharge(maximum, "KE"), fee)
                if index + 1 < len(tiers):
                    self.assertEqual(self.evaluator.compute_surcharge(maximum + 0.01, "KE"), tiers[index + 1][2])

    def test_uncovered_kenyan_rates_fail_instead_of_clamping(self) -> None:
        for amount in (0, 0.99, 250000.01):
            with self.subTest(amount=amount), self.assertRaises(TariffUnavailableError):
                self.evaluator.compute_surcharge(amount, "KE")
        self.assertEqual(self.evaluator.compute_surcharge(250000.01, "US"), 0)

    def test_quote_payload_is_api_friendly(self) -> None:
        payload = self.evaluator.evaluate_quote(base_predicted_rate=4500.0, mentor_country="KE")

        self.assertEqual(payload["base_predicted_rate"], 4500.0)
        self.assertEqual(payload["mpesa_tariff_surcharge"], 57.0)
        self.assertEqual(payload["final_quoted_rate"], 4557.0)
        self.assertEqual(payload["currency"], "KES")
        self.assertEqual(payload["mentor_country_iso2"], "KE")
        self.assertIsNotNone(payload["applied_tariff_band"])
        self.assertEqual(payload["applied_tariff_band"]["min_amount_kes"], 3501.0)
        self.assertEqual(payload["applied_tariff_band"]["max_amount_kes"], 5000.0)

    def test_published_quote_and_fee_use_the_same_rounded_base(self) -> None:
        quote = self.evaluator.evaluate_quote(base_predicted_rate=3500.006, mentor_country="KE")
        self.assertEqual(quote["base_predicted_rate"], 3500.01)
        self.assertEqual(quote["mpesa_tariff_surcharge"], 57)
        self.assertEqual(quote["final_quoted_rate"], 3557.01)
        with self.assertRaises(TariffUnavailableError):
            self.evaluator.evaluate_quote(base_predicted_rate=250000.001, mentor_country="KE")

    def test_unmerged_schedule_preserves_15001_to_20000_band(self) -> None:
        surcharge = self.evaluator.compute_surcharge(base_rate_kes=15001.0, mentor_country="KE")

        self.assertEqual(surcharge, 105.0)

    def test_negative_base_rate_is_rejected(self) -> None:
        for amount in (-1.0, float("nan"), float("inf")):
            with self.subTest(amount=amount), self.assertRaisesRegex(ValueError, "finite and non-negative"):
                self.evaluator.compute_surcharge(base_rate_kes=amount, mentor_country="KE")

    def test_untrusted_and_invalid_schedules_are_rejected(self) -> None:
        contents = self.tariff_csv.read_bytes()
        digest = hashlib.sha256(contents).hexdigest()
        self.assertEqual(MpesaTariffEvaluator.from_csv(str(self.tariff_csv), digest).schedule_sha256, digest)
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            MpesaTariffEvaluator.from_csv(str(self.tariff_csv), "0" * 64)
        for original, replacement in (
            (b"15001,20000,105.00", b"15001,20000,nan"),
            (b"3501,5000,57.00", b"3501,5000,57.001"),
            (b"3501,5000,57.00", b"1501,5000,57.00"),
            (b"50001,250000,108.00", b"50001,249999,108.00"),
        ):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as tmp:
                # Break a real tier boundary or fee: never repair/average a corrupt source.
                damaged = contents.replace(original, replacement, 1)
                path = Path(tmp) / "schedule.csv"
                path.write_bytes(damaged)
                with self.assertRaisesRegex(ValueError, "tariff"):
                    MpesaTariffEvaluator.from_csv(str(path))

    def test_withdrawal_and_other_payment_types_are_not_used_for_p2p_fees(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "schedule.csv"
            path.write_bytes(self.tariff_csv.read_bytes() +
                             b"CUSTOMER_WITHDRAWAL,AGENT_WITHDRAWAL,1501,2500,29.00\n" +
                             b"BUSINESS_PAYMENT,TILL_PAYMENT,1501,2500,17.00\n")
            evaluator = MpesaTariffEvaluator.from_csv(str(path))
            self.assertEqual(evaluator.compute_surcharge(2500, "KE"), 33.0)


if __name__ == "__main__":
    unittest.main()

