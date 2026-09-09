import os
import tempfile
import unittest
from pathlib import Path

from src.ingest_multisource import (
    build_harmonized_marketplace_records,
    build_macro_lookup,
    compute_bilateral_arbitrage_factor,
    export_harmonized_records_parquet,
    load_macro_lookup_table,
)


class HarmonizedParquetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parent.parent
        self.raw_dir = str(self.repo_root / "tests" / "fixtures" / "raw")

    def test_bilateral_arbitrage_factor_invariants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            macro_lookup_path = os.path.join(tmp_dir, "macro_lookup_table.json")
            build_macro_lookup(self.raw_dir, macro_lookup_path)
            macro_records = load_macro_lookup_table(macro_lookup_path)

            self.assertEqual(compute_bilateral_arbitrage_factor("KE", "KE", macro_records), 1.0)
            self.assertGreater(compute_bilateral_arbitrage_factor("KE", "US", macro_records), 1.0)

    def test_export_harmonized_parquet_is_readable(self) -> None:
        import pandas as pd

        with tempfile.TemporaryDirectory() as tmp_dir:
            macro_lookup_path = os.path.join(tmp_dir, "macro_lookup_table.json")
            parquet_path = os.path.join(tmp_dir, "harmonized_marketplace_corpus.parquet")

            build_macro_lookup(self.raw_dir, macro_lookup_path)
            records = build_harmonized_marketplace_records(self.raw_dir, macro_lookup_path)
            export_harmonized_records_parquet(records, parquet_path)

            df = pd.read_parquet(parquet_path)
            self.assertFalse(df.empty)
            self.assertIn("raw_description", df.columns)
            self.assertIn("industry_partition", df.columns)
            self.assertIn("hourly_rate", df.columns)
            self.assertIn("bilateral_arbitrage_factor", df.columns)
            self.assertIn("market_saturation_score", df.columns)

            self.assertTrue((df["hourly_rate"] >= 500.0).all())
            self.assertTrue((df["hourly_rate"] <= 35000.0).all())
            self.assertTrue((df["industry_partition"].astype(str).str.len() > 0).all())


if __name__ == "__main__":
    unittest.main()

