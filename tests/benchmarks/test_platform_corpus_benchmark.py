"""Tests for M15.1: Benchmark pricing quotes against 52 in-scope platform mentors."""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Optional

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
from src.core.artifact_contract import MANIFEST_NAME, file_sha256, write_manifest
from src.data.ingest_multisource import SUPPORTED_INDUSTRY_PARTITIONS, build_macro_lookup
from src.data.ingest_platform import build_platform_records
from src.engine.macro_arbitrage import ContinuousMetadataNormalizer, HYBRID_VECTOR_DIMENSIONS
from src.engine.spatial_engine import DomainPartitionedKDTreeIndexer
from src.nlp.nlp_pipeline import TextFeatureReducer


class PlatformCorpusBenchmarkTests(unittest.TestCase):
    _temp_dir: Optional[tempfile.TemporaryDirectory] = None
    artifact_dir: str = ""
    tariff_csv: str = ""

    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[2]
        prod_manifest = cls.repo_root / "artifacts" / "artifact_manifest.json"
        prod_tariff = cls.repo_root / "config" / "tariffs" / "mpesa_p2p_users_2026-08-04.csv"

        if prod_manifest.is_file() and prod_tariff.is_file():
            cls.artifact_dir = str(cls.repo_root / "artifacts")
            cls.tariff_csv = str(prod_tariff)
        else:
            # CI environment without checked-in production model artifacts: build multi-partition synthetic fixture
            cls._temp_dir = tempfile.TemporaryDirectory()
            tmp_path = cls._temp_dir.name
            cls.artifact_dir = os.path.join(tmp_path, "artifacts")
            os.makedirs(cls.artifact_dir, exist_ok=True)

            raw_fixture_dir = str(cls.repo_root / "tests" / "fixtures" / "raw")
            cls.tariff_csv = str(
                cls.repo_root
                / "tests"
                / "fixtures"
                / "raw"
                / "Mpesa_Tarrifs"
                / "tarrifs_full_schedule.csv"
            )
            macro_lookup_path = os.path.join(tmp_path, "macro_lookup_table.json")
            build_macro_lookup(raw_fixture_dir, macro_lookup_path)

            texts = [f"mentor profile engineering python backend cloud devops {i}" for i in range(90)]
            reducer = TextFeatureReducer(n_components=50, max_features=8000)
            reducer.fit_transform(texts)
            reducer.save_artifacts(cls.artifact_dir)

            normalizer = ContinuousMetadataNormalizer(macro_lookup_path=macro_lookup_path)
            normalizer.fit([
                {
                    "bilateral_arbitrage_factor": 1.0,
                    "market_saturation_score": 0.2,
                    "industry_relative_density": 0.3,
                }
            ])
            normalizer.save_artifacts(cls.artifact_dir)

            partitions = []
            verified_rates = []
            # Provide varied rates matching the empirical mentor distribution (2500 - 6500 KES)
            base_rates_sample = [2600.0, 3400.0, 4500.0, 5400.0, 6400.0]
            for p in SUPPORTED_INDUSTRY_PARTITIONS:
                partitions.extend([p] * 5)
                verified_rates.extend(base_rates_sample)
            n = len(partitions)
            vectors = np.zeros((n, HYBRID_VECTOR_DIMENSIONS), dtype=float)
            indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=1)
            indexer.fit(
                vectors,
                partitions,
                record_indices=list(range(n)),
                verified_rates=verified_rates,
            )
            indexer.save_artifacts(cls.artifact_dir)
            shutil.copyfile(macro_lookup_path, os.path.join(cls.artifact_dir, "macro_lookup_table.json"))

            config = {
                "version": 1,
                "text_dimensions": 50,
                "metadata_features": [
                    "bilateral_arbitrage_factor",
                    "market_saturation_score",
                    "industry_relative_density",
                ],
                "k_neighbors": 5,
                "idw_epsilon": 1e-6,
                "text_weight": 1.0,
                "metadata_weight": 1.0,
                "minimum_partition_size": 1,
                "fallback_partition": "general_tech",
                "allow_fallback": True,
                "partition_density": {p: 0.5 for p in SUPPORTED_INDUSTRY_PARTITIONS},
            }
            with open(os.path.join(cls.artifact_dir, "inference_config.json"), "w", encoding="utf-8") as handle:
                json.dump(config, handle)
            write_manifest(
                cls.artifact_dir,
                config,
                dataset_version="synthetic-fixture-v1",
                source_type="synthetic proxy fixture",
                split_policy="synthetic fixed fixture",
            )

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._temp_dir is not None:
            cls._temp_dir.cleanup()

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
