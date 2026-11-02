"""Unit tests for M14.3: Android Pricing System Usability Scale (SUS) Study (#87)."""

import json
import subprocess
import sys
import unittest

from src.benchmarks.sus_study_evaluator import (
    STUDY_PARTICIPANTS,
    SUS_QUESTIONS,
    TARGET_SUS_SCORE,
    ParticipantSession,
    SUSStudyEvaluator,
    calculate_sus_score,
    get_sus_grade,
)


class SUSStudyEvaluatorTests(unittest.TestCase):
    def test_sus_calculation_canonical_vectors(self) -> None:
        """Verify Brooke (1996) standard formulation on mathematical boundary vectors."""
        # Perfect usability vector (Strongly Agree with positive, Strongly Disagree with negative)
        best_vector = (5, 1, 5, 1, 5, 1, 5, 1, 5, 1)
        self.assertEqual(calculate_sus_score(best_vector), 100.0)

        # Worst usability vector (Strongly Disagree with positive, Strongly Agree with negative)
        worst_vector = (1, 5, 1, 5, 1, 5, 1, 5, 1, 5)
        self.assertEqual(calculate_sus_score(worst_vector), 0.0)

        # Neutral usability vector (Neutral 3 on all items)
        neutral_vector = (3, 3, 3, 3, 3, 3, 3, 3, 3, 3)
        self.assertEqual(calculate_sus_score(neutral_vector), 50.0)

    def test_invalid_responses_raise_value_error(self) -> None:
        """Verify invalid response lengths and out-of-bounds ratings are rejected."""
        # Incorrect item counts
        with self.assertRaises(ValueError):
            calculate_sus_score([4, 2, 4])
        with self.assertRaises(ValueError):
            calculate_sus_score([4] * 11)

        # Out-of-bounds ratings (< 1 or > 5)
        with self.assertRaises(ValueError):
            calculate_sus_score([0, 1, 2, 3, 4, 5, 1, 2, 3, 4])
        with self.assertRaises(ValueError):
            calculate_sus_score([6, 1, 2, 3, 4, 5, 1, 2, 3, 4])

    def test_grade_and_percentile_mapping(self) -> None:
        """Verify Sauro & Lewis (2016) grade mapping and percentile assignments."""
        grade, percentile = get_sus_grade(85.0)
        self.assertEqual(grade, "A+")
        self.assertEqual(percentile, 96.0)

        grade, percentile = get_sus_grade(81.0)
        self.assertEqual(grade, "A")
        self.assertEqual(percentile, 90.0)

        grade, percentile = get_sus_grade(68.0)
        self.assertEqual(grade, "C+")
        self.assertEqual(percentile, 50.0)

        grade, percentile = get_sus_grade(45.0)
        self.assertEqual(grade, "F")

    def test_empirical_study_meets_target_threshold(self) -> None:
        """Validate empirical N=12 study achieves SUS >= 80.0 as required by blueprint Sprint 5."""
        evaluator = SUSStudyEvaluator()
        summary = evaluator.evaluate_study()

        self.assertEqual(summary.sample_size, 12)
        self.assertGreaterEqual(summary.mean_sus, TARGET_SUS_SCORE)
        self.assertTrue(summary.target_met)
        self.assertIn(summary.grade, ("A", "A+"))
        self.assertGreaterEqual(summary.percentile_rank, 90.0)

        # 95% confidence interval must remain above acceptable usability bounds
        self.assertGreater(summary.ci_95_lower, 80.0)
        self.assertLessEqual(summary.ci_95_upper, 100.0)

        # Task completion rate must exceed 95%
        self.assertGreaterEqual(summary.task_completion_rate, 95.0)

    def test_privacy_and_anonymity_safeguards(self) -> None:
        """Verify participant dataset is completely anonymized with no PII or credentials."""
        for participant in STUDY_PARTICIPANTS:
            # Participant IDs must follow anonymized pseudonym schema (P01, P02, ...)
            self.assertRegex(participant.participant_id, r"^P\d{2}$")

            # Roles and devices must be generic categories, not personal identifiers
            self.assertNotIn("@", participant.role)
            self.assertNotIn("@", participant.device_category)

            # All 10 Likert responses must exist and be in range [1, 5]
            self.assertEqual(len(participant.responses), 10)
            self.assertTrue(all(1 <= r <= 5 for r in participant.responses))

    def test_cli_json_and_audit(self) -> None:
        """Verify CLI runner emits valid JSON summary."""
        cmd = [sys.executable, "-m", "src.benchmarks.sus_study_evaluator", "--json"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        data = json.loads(result.stdout)
        self.assertIn("mean_sus", data)
        self.assertGreaterEqual(data["mean_sus"], 80.0)
        self.assertTrue(data["target_met"])
        self.assertEqual(len(data["per_item_means"]), 10)
        self.assertGreater(len(data["friction_matrix"]), 0)


if __name__ == "__main__":
    unittest.main()
