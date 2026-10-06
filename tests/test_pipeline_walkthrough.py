"""Lightweight checks for the local-data, research-only pipeline notebook (#137)."""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from src.inference_safe_benchmark import _split_population
from src.train_pipeline import load_harmonized_parquet


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "pipeline_walkthrough.ipynb"
PARQUET = ROOT / "data" / "processed" / "harmonized_marketplace_corpus.parquet"
MACRO = ROOT / "data" / "processed" / "macro_lookup_table.json"


class PipelineWalkthroughTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cells = {cell["id"]: cell for cell in json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]}

    def test_notebook_cells_compile_and_use_existing_oot_path(self):
        for cell in self.cells.values():
            if cell["cell_type"] == "code":
                compile("".join(cell["source"]), f"{NOTEBOOK}:{cell['id']}", "exec")

        sources = {key: "".join(cell["source"]) for key, cell in self.cells.items()}
        self.assertIn("load_harmonized_parquet(str(parquet_path))", sources["corpus"])
        self.assertIn("_split_population(frame, VALIDATION_CUTOFF, TEST_CUTOFF)", sources["metadata"])
        self.assertIn("indexer.fit(x_train, split.train.industry_partition", sources["spatial"])
        self.assertIn("'deployable_manifest': False", sources["runtime"])
        for forbidden in ("build_stratified_splits", "evaluate_and_serialize_training(",
                          "pd.DataFrame(jobs).to_csv", "TestClient("):
            self.assertNotIn(forbidden, "\n".join(sources.values()))

    def test_missing_local_parquet_fails_before_workspace_creation(self):
        original_is_file = Path.is_file

        def missing_parquet(path):
            return False if path == PARQUET else original_is_file(path)

        with patch.object(Path, "cwd", return_value=ROOT), patch.object(Path, "is_file", missing_parquet):
            with self.assertRaisesRegex(FileNotFoundError, "Missing ignored local input.*harmonized_marketplace_corpus"):
                exec("".join(self.cells["setup"]["source"]), {})

    @unittest.skipUnless(PARQUET.is_file() and MACRO.is_file(), "ignored local corpus unavailable")
    def test_local_cohort_is_dated_disjoint_and_train_derived(self):
        frame = load_harmonized_parquet(str(PARQUET))
        split, provenance = _split_population(
            frame, "2024-02-20T00:00:00+00:00", "2024-02-22T00:00:00+00:00",
        )
        self.assertIn("posted budgets", provenance["population"])
        self.assertTrue(provenance["disjoint_record_ids"])
        self.assertGreaterEqual(provenance["excluded_other_sources"], 1)
        self.assertLess(split.train.observation_timestamp_utc.max(), split.validation.observation_timestamp_utc.min())
        self.assertLess(split.validation.observation_timestamp_utc.max(), split.test.observation_timestamp_utc.min())
        self.assertEqual(set(split.train.source_dataset), {"upwork_jobs"})
        self.assertEqual(set(split.validation.source_dataset), {"upwork_jobs"})
        self.assertEqual(set(split.test.source_dataset), {"upwork_jobs"})
        for part in (split.train, split.validation, split.test):
            self.assertTrue(part.target_rate.between(500, 35000).all())
        counts = split.train.industry_partition.value_counts()
        for part in (split.train, split.validation, split.test):
            self.assertTrue((part.industry_frequency == part.industry_partition.map(counts)).all())


if __name__ == "__main__":
    unittest.main()
