import csv
import tempfile
import unittest
from pathlib import Path

from scripts.analyze_sus_responses import analyze_responses, score_sus


class SusAnalysisTests(unittest.TestCase):
    def test_standard_scoring_for_all_midpoint_and_opposite_responses(self):
        self.assertEqual(score_sus([3] * 10), 50.0)
        self.assertEqual(score_sus([5, 1] * 5), 100.0)
        self.assertEqual(score_sus([1, 5] * 5), 0.0)

    def test_score_requires_ten_complete_likert_responses(self):
        for responses in ([1] * 9, [1] * 9 + [6]):
            with self.subTest(responses=responses), self.assertRaises(ValueError):
                score_sus(responses)

    def test_csv_summary_contains_aggregate_metrics_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "responses.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as response_file:
                writer = csv.writer(response_file)
                writer.writerow(["participant_id", *(f"item_{number}" for number in range(1, 11))])
                writer.writerow(["P001", *([5, 1] * 5)])
                writer.writerow(["P002", *([3] * 10)])

            summary = analyze_responses(csv_path)

        self.assertEqual(summary["sample_size"], 2)
        self.assertEqual(summary["mean_sus"], 75.0)
        self.assertEqual(summary["median_sus"], 75.0)
        self.assertFalse(summary["threshold_met"])
        self.assertNotIn("participant_ids", summary)

    def test_csv_rejects_identifying_columns_and_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "responses.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as response_file:
                writer = csv.writer(response_file)
                writer.writerow(["participant_id", "email", *(f"item_{number}" for number in range(1, 11))])
            with self.assertRaisesRegex(ValueError, "columns must be exactly"):
                analyze_responses(csv_path)

            with csv_path.open("w", newline="", encoding="utf-8") as response_file:
                writer = csv.writer(response_file)
                writer.writerow(["participant_id", *(f"item_{number}" for number in range(1, 11))])
                writer.writerow(["P001", *([4] * 10), "unexpected"])
            with self.assertRaisesRegex(ValueError, "unexpected extra"):
                analyze_responses(csv_path)

            with csv_path.open("w", newline="", encoding="utf-8") as response_file:
                writer = csv.writer(response_file)
                writer.writerow(["participant_id", *(f"item_{number}" for number in range(1, 11))])
                writer.writerow(["P001", *([4] * 10)])
                writer.writerow(["P001", *([4] * 10)])
            with self.assertRaisesRegex(ValueError, "duplicate"):
                analyze_responses(csv_path)


if __name__ == "__main__":
    unittest.main()
