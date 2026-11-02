"""Tests for M15.1: Benchmark pricing quotes against 52 in-scope platform mentors."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict

import numpy as np

from src.benchmarks.platform_corpus_benchmark import (
    IN_SCOPE_TARGET_COUNT,
    OUT_OF_SCOPE_VOCATIONAL_COUNT,
    TOTAL_PLATFORM_MENTORS,
    compute_metrics,
    evaluate_platform_mentor_corpus,
    format_markdown_report,
    generate_synthetic_platform_mentor_cache,
    load_or_ingest_platform_corpus,
    main,
    run_benchmark,
)
from src.data.ingest_platform import build_platform_records


class PlatformCorpusBenchmarkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]
        self.artifact_dir = str(self.repo_root / "artifacts")
        self.tariff_csv = str(self.repo_root / "config" / "tariffs" / "mpesa_p2p_users_2026-08-04.csv")

    def test_compute_metrics_analytical_precision(self) -> None:
        y_true = np.array([4000.0, 5000.0, 6000.0])
        y_pred = np.array([4200.0, 4800.0, 6000.0])

        metrics = compute_metrics(y_true, y_pred)
        self.assertEqual(metrics.n_samples, 3)
        self.assertAlmostEqual(metrics.mae, 400.0 / 3.0, places=2)
        self.assertEqual(metrics.medae, 200.0)
        self.assertAlmostEqual(metrics.rmse, np.sqrt((200**2 + 200**2) / 3.0), places=2)
        self.assertEqual(metrics.over_pricing_count, 1)
        self.assertEqual(metrics.under_pricing_count, 1)
        self.assertAlmostEqual(metrics.over_pricing_pct, 33.33, places=1)
        self.assertAlmostEqual(metrics.under_pricing_pct, 33.33, places=1)
        self.assertAlmostEqual(metrics.mean_bias, 0.0, places=2)

    def test_synthetic_cache_preserves_222_mentor_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = generate_synthetic_platform_mentor_cache(tmpdir)
            self.assertTrue(os.path.isfile(paths["mentors"]))
            self.assertTrue(os.path.isfile(paths["mentor_skills"]))
            self.assertTrue(os.path.isfile(paths["bookings"]))
            self.assertTrue(os.path.isfile(paths["reviews"]))

            res = build_platform_records(tmpdir)
            self.assertEqual(res.mentors_seen, TOTAL_PLATFORM_MENTORS)
            self.assertEqual(res.excluded["out_of_scope_category"], OUT_OF_SCOPE_VOCATIONAL_COUNT)
            self.assertEqual(len(res.records), IN_SCOPE_TARGET_COUNT)

            # Ensure all retained records have valid listed rates and raw_description
            for r in res.records:
                self.assertGreaterEqual(r["listed_hourly_rate_kes"], 1000.0)
                self.assertGreaterEqual(len(r["raw_description"]), 40)
                self.assertEqual(r["source_country"], "Kenya")

    def test_evaluate_platform_mentor_corpus_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            records, _ = load_or_ingest_platform_corpus(cache_dir=tmpdir)
            self.assertEqual(len(records), IN_SCOPE_TARGET_COUNT)

            report = evaluate_platform_mentor_corpus(
                records=records,
                artifact_dir=self.artifact_dir,
                tariff_csv=self.tariff_csv,
            )

            self.assertEqual(report["n_mentors_evaluated"], IN_SCOPE_TARGET_COUNT)
            self.assertEqual(report["target_count_expected"], 52)

            # Benchmark A assertions
            ba = report["benchmark_a_listed"]
            self.assertEqual(ba["n_samples"], 52)
            self.assertGreater(ba["mae"], 0.0)
            self.assertGreater(ba["rmse"], 0.0)
            self.assertGreater(ba["smape_pct"], 0.0)
            self.assertLess(ba["smape_pct"], 100.0)

            # Benchmark B assertions
            bb = report["benchmark_b_realised"]
            self.assertGreater(bb["n_samples"], 0)
            self.assertLessEqual(bb["n_samples"], 52)
            self.assertGreater(bb["mae"], 0.0)
            self.assertGreater(bb["rmse"], 0.0)

            # Corridor containment
            cc = report["corridor_containment"]
            self.assertGreaterEqual(cc["containment_pct"], 80.0)
            self.assertEqual(cc["total_mentors"], 52)

            # Subgroup coverage
            subgroups = report["subgroup_metrics"]
            self.assertIn("data_ai", subgroups)
            self.assertIn("mobile", subgroups)
            self.assertIn("web_backend", subgroups)
            self.assertIn("digital_marketing", subgroups)
            self.assertIn("product_management", subgroups)

            # Asymmetric risk sums
            ar = report["asymmetric_risk_analysis"]
            total_pct = ar["over_pricing"]["pct"] + ar["under_pricing"]["pct"] + ar["exact_pricing"]["pct"]
            self.assertAlmostEqual(total_pct, 100.0, places=1)

    def test_format_markdown_report_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            records, _ = load_or_ingest_platform_corpus(cache_dir=tmpdir)
            report = evaluate_platform_mentor_corpus(
                records=records,
                artifact_dir=self.artifact_dir,
                tariff_csv=self.tariff_csv,
            )
            md = format_markdown_report(report)
            self.assertIn("Academic Evaluation Report", md)
            self.assertIn("Benchmark A: Listed Rates", md)
            self.assertIn("Benchmark B: Realised Rates", md)
            self.assertIn("Domain Subgroup Performance Breakdown", md)
            self.assertIn("Asymmetric Risk & Residual Analysis", md)
            self.assertIn("Academic Defense Synthesis", md)

    def test_cli_execution_with_custom_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = os.path.join(tmpdir, "cache")
            json_path = os.path.join(tmpdir, "output.json")
            report_path = os.path.join(tmpdir, "output.md")

            code = main([
                "--cache-dir", cache_path,
                "--artifacts", self.artifact_dir,
                "--tariff-csv", self.tariff_csv,
                "--output-json", json_path,
                "--output-report", report_path,
            ])
            self.assertEqual(code, 0)
            self.assertTrue(os.path.isfile(json_path))
            self.assertTrue(os.path.isfile(report_path))

            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["n_mentors_evaluated"], IN_SCOPE_TARGET_COUNT)


if __name__ == "__main__":
    unittest.main()
