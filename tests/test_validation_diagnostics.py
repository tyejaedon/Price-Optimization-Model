import os
import tempfile
import unittest

import pandas as pd

from src.validation_diagnostics import compute_confidence_interval, detect_duplicate_records


class ValidationDiagnosticsTests(unittest.TestCase):
    def test_duplicate_detection_reports_normalized_duplicate_rows(self) -> None:
        frame = pd.DataFrame(
            [
                {"raw_description": " Senior Python Mentor ", "target_rate": 2500.0},
                {"raw_description": "senior   python mentor", "target_rate": 2500.0},
                {"raw_description": "Different mentor", "target_rate": 3000.0},
            ]
        )

        result = detect_duplicate_records(frame)

        self.assertEqual(result["duplicate_rows"], 2)
        self.assertEqual(result["duplicate_groups"], 1)
        self.assertGreater(result["duplicate_rate"], 0.0)

    def test_confidence_interval_is_finite_and_deterministic(self) -> None:
        result = compute_confidence_interval([0.5, 0.6, 0.7, 0.8])

        self.assertEqual(result["samples"], 4)
        self.assertAlmostEqual(result["mean"], 0.65, places=6)
        self.assertLess(result["ci_lower"], result["mean"])
        self.assertGreater(result["ci_upper"], result["mean"])
        self.assertTrue(all(pd.notna(value) for value in result.values() if isinstance(value, (int, float))))


if __name__ == "__main__":
    unittest.main()

