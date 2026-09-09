import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, cast

from src.ingest_multisource import (
    build_macro_lookup,
    find_file_in_dir,
    get_macro_record,
    load_macro_lookup_table,
)


class MacroLookupBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parent.parent
        self.raw_dir = str(self.repo_root / "data" / "raw")

    def test_find_file_in_dir_resolves_expected_csvs(self) -> None:
        wdi_path = find_file_in_dir(
            os.path.join(self.raw_dir, "World_Development_Indicators"),
            name_contains="_Data",
        )
        col_path = find_file_in_dir(
            os.path.join(self.raw_dir, "Cost_Index"),
            name_contains="Cost_of_Living_Index",
        )
        mpesa_path = find_file_in_dir(
            os.path.join(self.raw_dir, "Mpesa_Tarrifs"),
            name_contains="tarrifs",
        )

        self.assertTrue(wdi_path.endswith("_Data.csv"))
        self.assertTrue(col_path.endswith("Cost_of_Living_Index_by_Country_2024.csv"))
        self.assertTrue(mpesa_path.endswith("tarrifs.csv"))

    def test_build_lookup_contains_target_economies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = os.path.join(tmp_dir, "macro_lookup_table.json")
            payload = build_macro_lookup(self.raw_dir, output_path)
            records = cast(Dict[str, Dict[str, Any]], payload["records"])

            for iso2 in ["KE", "UG", "TZ", "RW", "US", "GB", "DE", "CA", "IN"]:
                self.assertIn(iso2, records)
                self.assertGreater(float(records[iso2]["ppp_lcu_per_intl_dollar"]), 0.0)

            self.assertTrue(os.path.exists(output_path))

    def test_rwanda_cost_index_fallback_is_seeded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = os.path.join(tmp_dir, "macro_lookup_table.json")
            payload = build_macro_lookup(self.raw_dir, output_path)
            records = cast(Dict[str, Dict[str, Any]], payload["records"])
            rwanda = records["RW"]

            self.assertTrue(bool(rwanda["cost_index_fallback_used"]))
            self.assertGreater(float(rwanda["cost_of_living_index"]), 0.0)

    def test_lookup_load_and_safe_fallback_accessor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = os.path.join(tmp_dir, "macro_lookup_table.json")
            build_macro_lookup(self.raw_dir, output_path)

            records = load_macro_lookup_table(output_path)
            self.assertIn("KE", records)

            default_record = get_macro_record(records, iso2_code="XX", default_iso2_code="KE")
            self.assertEqual(default_record["country_iso2"], "KE")

            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("records", data)

    def test_mpesa_tariff_metadata_is_integrated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = os.path.join(tmp_dir, "macro_lookup_table.json")
            payload = build_macro_lookup(self.raw_dir, output_path)

            metadata = cast(Dict[str, Any], payload.get("metadata", {}))
            mpesa = cast(Dict[str, Any], metadata.get("mpesa_tariffs", {}))
            summary = cast(Dict[str, Any], mpesa.get("summary", {}))

            self.assertEqual(mpesa.get("source_file"), "tarrifs.csv")
            self.assertGreater(int(summary.get("row_count", 0)), 0)
            self.assertGreater(int(summary.get("consumer_transfer_band_count", 0)), 0)


if __name__ == "__main__":
    unittest.main()
