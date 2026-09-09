import unittest
from pathlib import Path

from src.ingest_multisource import (
    MAX_ACCEPTED_HOURLY_RATE_KES,
    MIN_ACCEPTED_HOURLY_RATE_KES,
    MIN_DESCRIPTION_LENGTH,
    SUPPORTED_INDUSTRY_PARTITIONS,
    harmonize_marketplace_corpus,
    map_industry_partition,
)


class MarketplaceHarmonizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parent.parent
        self.raw_dir = str(self.repo_root / "tests" / "fixtures" / "raw")

    def test_map_industry_partition_covers_supported_domains(self) -> None:
        samples = {
            "Build machine learning and NLP pipeline": "data_ai",
            "React and Django backend API modernization": "web_backend",
            "Flutter mobile app for Android and iOS": "mobile",
            "Kubernetes, Docker, and AWS deployment": "devops_cloud",
            "Figma UX redesign for a dashboard": "design_creative",
            "Scrum product manager for roadmap execution": "product_management",
            "Facebook Ads growth with SEO tuning": "digital_marketing",
            "General technical support": "general_tech",
        }

        for text, expected in samples.items():
            partition = map_industry_partition(text)
            self.assertEqual(partition, expected)
            self.assertIn(partition, SUPPORTED_INDUSTRY_PARTITIONS)

    def test_harmonize_marketplace_corpus_filters_and_converts(self) -> None:
        records = harmonize_marketplace_corpus(self.raw_dir)

        self.assertEqual(len(records), 3)

        for row in records:
            self.assertTrue(row["raw_description"])
            self.assertTrue(row["industry_partition"])
            self.assertGreaterEqual(len(row["raw_description"]), MIN_DESCRIPTION_LENGTH)
            self.assertGreaterEqual(float(row["hourly_rate"]), MIN_ACCEPTED_HOURLY_RATE_KES)
            self.assertLessEqual(float(row["hourly_rate"]), MAX_ACCEPTED_HOURLY_RATE_KES)
            self.assertEqual(row["currency"], "KES")

        partitions = {row["industry_partition"] for row in records}
        self.assertIn("data_ai", partitions)
        self.assertIn("web_backend", partitions)
        self.assertIn("digital_marketing", partitions)


if __name__ == "__main__":
    unittest.main()

