import unittest

from src.oot_gate import validate_oot_report


class OotGateTests(unittest.TestCase):
    def test_valid_synthetic_report(self):
        self.assertEqual(validate_oot_report({
            "evaluation_protocol": "chronological_out_of_time",
            "train_end": "2025-01-01T00:00:00+00:00",
            "test_start": "2025-02-01T00:00:00+00:00",
            "test": {"r2": 0.75},
        }), 0.75)

    def test_rejects_fabricated_or_insufficient_evidence(self):
        valid = {
            "evaluation_protocol": "chronological_out_of_time",
            "train_end": "2025-01-01T00:00:00+00:00",
            "test_start": "2025-02-01T00:00:00+00:00",
            "test": {"r2": 0.8},
        }
        for invalid in (
            {},
            {**valid, "evaluation_protocol": "stratified"},
            {**valid, "train_end": "2025-03-01T00:00:00+00:00"},
            {**valid, "time_cutoff": "2025-01-02T00:00:00+00:00", "test_start": "2025-01-02T00:00:00+00:00"},
            {**valid, "time_cutoff": "2024-12-01T00:00:00+00:00"},
            {**valid, "test": {"r2": 0.749}},
            {**valid, "test": {"r2": float("nan")}},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_oot_report(invalid)


if __name__ == "__main__":
    unittest.main()
