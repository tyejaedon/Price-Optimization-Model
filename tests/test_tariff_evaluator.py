import unittest
from pathlib import Path

from src.tariff_evaluator import MpesaTariffEvaluator


class MpesaTariffEvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        tariff_csv = repo_root / "tests" / "fixtures" / "raw" / "Mpesa_Tarrifs" / "tarrifs_full_schedule.csv"
        cls.evaluator = MpesaTariffEvaluator.from_csv(str(tariff_csv))

    def test_domestic_4500_case_yields_expected_55_surcharge(self) -> None:
        surcharge = self.evaluator.compute_surcharge(base_rate_kes=4500.0, mentor_country="KE")

        self.assertEqual(surcharge, 55.0)

    def test_international_mentor_country_returns_zero_surcharge(self) -> None:
        surcharge = self.evaluator.compute_surcharge(base_rate_kes=4500.0, mentor_country="US")

        self.assertEqual(surcharge, 0.0)

    def test_bracket_transitions_are_deterministic(self) -> None:
        self.assertEqual(self.evaluator.compute_surcharge(2500.0, "KE"), 33.0)
        self.assertEqual(self.evaluator.compute_surcharge(2501.0, "KE"), 55.0)
        self.assertEqual(self.evaluator.compute_surcharge(5000.0, "KE"), 55.0)
        self.assertEqual(self.evaluator.compute_surcharge(5001.0, "KE"), 78.0)

    def test_quote_payload_is_api_friendly(self) -> None:
        payload = self.evaluator.evaluate_quote(base_predicted_rate=4500.0, mentor_country="KE")

        self.assertEqual(payload["base_predicted_rate"], 4500.0)
        self.assertEqual(payload["mpesa_tariff_surcharge"], 55.0)
        self.assertEqual(payload["final_quoted_rate"], 4555.0)
        self.assertEqual(payload["currency"], "KES")
        self.assertEqual(payload["mentor_country_iso2"], "KE")
        self.assertIsNotNone(payload["applied_tariff_band"])
        self.assertEqual(payload["applied_tariff_band"]["min_amount_kes"], 2501.0)
        self.assertEqual(payload["applied_tariff_band"]["max_amount_kes"], 5000.0)

    def test_repaired_schedule_preserves_15001_to_20000_band(self) -> None:
        surcharge = self.evaluator.compute_surcharge(base_rate_kes=15001.0, mentor_country="KE")

        self.assertEqual(surcharge, 105.0)

    def test_negative_base_rate_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-negative"):
            self.evaluator.compute_surcharge(base_rate_kes=-1.0, mentor_country="KE")


if __name__ == "__main__":
    unittest.main()

