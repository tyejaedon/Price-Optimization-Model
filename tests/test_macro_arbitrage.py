import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.ingest_multisource import (
    build_harmonized_marketplace_records,
    build_macro_lookup,
    export_harmonized_records_parquet,
)
from src.macro_arbitrage import ContinuousMetadataNormalizer


class ContinuousMetadataNormalizerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parent.parent
        self.raw_dir = str(self.repo_root / "tests" / "fixtures" / "raw")

    def _build_fixture_paths(self, tmp_dir: str) -> tuple[str, str]:
        macro_lookup_path = os.path.join(tmp_dir, "macro_lookup_table.json")
        parquet_path = os.path.join(tmp_dir, "harmonized_marketplace_corpus.parquet")
        build_macro_lookup(self.raw_dir, macro_lookup_path)
        records = build_harmonized_marketplace_records(self.raw_dir, macro_lookup_path)
        export_harmonized_records_parquet(records, parquet_path)
        return macro_lookup_path, parquet_path

    def test_fit_from_parquet_scales_values_to_zero_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            macro_lookup_path, parquet_path = self._build_fixture_paths(tmp_dir)
            normalizer = ContinuousMetadataNormalizer(macro_lookup_path=macro_lookup_path)

            transformed = normalizer.fit_from_parquet(parquet_path)

            self.assertEqual(transformed.shape[1], 3)
            self.assertTrue(np.all(np.isfinite(transformed)))
            self.assertGreaterEqual(float(transformed.min()), 0.0)
            self.assertLessEqual(float(transformed.max()), 1.0)

    def test_unknown_country_codes_fallback_safely(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            macro_lookup_path, parquet_path = self._build_fixture_paths(tmp_dir)
            normalizer = ContinuousMetadataNormalizer(macro_lookup_path=macro_lookup_path)
            normalizer.fit_from_parquet(parquet_path)

            raw = normalizer.build_live_metadata_vector("ZZ", "XX", 0.2, 0.5)
            scaled = normalizer.transform_live_metadata("ZZ", "XX", 0.2, 0.5)

            self.assertEqual(round(float(raw[0][0]), 6), 1.0)
            self.assertEqual(scaled.shape, (1, 3))
            self.assertTrue(np.all(np.isfinite(scaled)))

    def test_serialization_preserves_transform_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            macro_lookup_path, parquet_path = self._build_fixture_paths(tmp_dir)
            normalizer = ContinuousMetadataNormalizer(macro_lookup_path=macro_lookup_path)
            normalizer.fit_from_parquet(parquet_path)

            baseline = normalizer.transform_live_metadata("KE", "US", 0.3, 0.7)
            normalizer.save_artifacts(tmp_dir)
            restored = ContinuousMetadataNormalizer.load_artifacts(tmp_dir)
            reloaded = restored.transform_live_metadata("KE", "US", 0.3, 0.7)

            np.testing.assert_allclose(baseline, reloaded, atol=1e-9)

    def test_export_corridor_bilateral_factor_exceeds_domestic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            macro_lookup_path, parquet_path = self._build_fixture_paths(tmp_dir)
            normalizer = ContinuousMetadataNormalizer(macro_lookup_path=macro_lookup_path)
            normalizer.fit_from_parquet(parquet_path)

            domestic = normalizer.build_live_metadata_vector("KE", "KE", 0.1, 0.1)
            export = normalizer.build_live_metadata_vector("KE", "US", 0.1, 0.1)

            self.assertEqual(round(float(domestic[0][0]), 6), 1.0)
            self.assertGreater(float(export[0][0]), 1.0)


if __name__ == "__main__":
    unittest.main()

