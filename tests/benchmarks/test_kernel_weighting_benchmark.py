"""Synthetic-only tests for the M16.3 kernel weighting benchmark runner."""

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.benchmarks.kernel_weighting_benchmark import (
    DEFAULT_KERNEL_SPECS,
    compute_weight_distribution_stats,
    run_benchmark,
    run_edge_stability_probes,
)
from tests.training.test_train_pipeline import TrainPipelineTests


class KernelWeightingBenchmarkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.macro, parquet = TrainPipelineTests()._write_input_artifacts(self.temp.name)
        self.parquet = Path(parquet)
        frame = pd.read_parquet(self.parquet)
        frame["source_dataset"] = "upwork_jobs"
        frame["mentor_country_iso2"] = "KE"
        frame["client_country_iso2"] = "KE"
        frame["bilateral_arbitrage_factor"] = 1.0
        frame["observation_timestamp_utc"] = [
            ("2025-01-01T00:00:00+00:00", "2025-02-01T00:00:00+00:00", "2025-03-01T00:00:00+00:00")[i % 3]
            for i in range(len(frame))
        ]
        frame.to_parquet(self.parquet, index=False)

    def test_edge_stability_probes_pass_all_kernels(self) -> None:
        probes = run_edge_stability_probes(DEFAULT_KERNEL_SPECS)
        self.assertEqual(len(probes), len(DEFAULT_KERNEL_SPECS) * 4)
        self.assertTrue(all(p["finite"] and p["non_negative"] for p in probes))

    def test_weight_distribution_stats_bounds(self) -> None:
        uniform = compute_weight_distribution_stats([0.25, 0.25, 0.25, 0.25])
        self.assertAlmostEqual(uniform["normalized_entropy"], 1.0, places=6)
        self.assertAlmostEqual(uniform["effective_neighbors"], 4.0, places=6)

        spiky = compute_weight_distribution_stats([0.97, 0.01, 0.01, 0.01])
        self.assertLess(spiky["normalized_entropy"], 0.3)
        self.assertLess(spiky["effective_neighbors"], 1.2)

    def test_run_benchmark_evaluates_all_kernels_on_validation_only(self) -> None:
        out_dir = self.root / "kernel_run"
        report = run_benchmark(
            str(self.parquet),
            self.macro,
            "2025-01-15T00:00:00+00:00",
            "2025-02-15T00:00:00+00:00",
            "synthetic-only",
            output_dir=str(out_dir),
        )
        self.assertEqual(len(report["results"]), len(DEFAULT_KERNEL_SPECS))
        self.assertTrue((out_dir / "benchmark.json").exists())
        self.assertTrue((out_dir / "protocol_frozen.json").exists())
        self.assertNotIn("test", json.dumps(report["results"]))
        for entry in report["results"]:
            self.assertTrue(entry["corridor_invariants_preserved"])
            self.assertTrue(np.isfinite(entry["validation"]["mae"]))
            self.assertTrue(np.isfinite(entry["validation"]["rmse"]))
            self.assertIn("delta_vs_baseline", entry)
            self.assertGreater(entry["overall_dynamics"]["mean_corridor_width"], 0.0)


if __name__ == "__main__":
    unittest.main()
