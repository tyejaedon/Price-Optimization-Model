import json
import unittest
from pathlib import Path


class PortableReferenceAssetsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parent.parent
        self.portable_root = self.repo_root / "tests" / "fixtures" / "portable"
        self.manifest_path = self.portable_root / "manifest.json"
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self.max_size_bytes = int(self.manifest["selectionPolicy"]["maxFileSizeMB"] * 1024 * 1024)

    def test_manifest_entries_exist_and_stay_small(self) -> None:
        files = self.manifest["files"]
        self.assertGreater(len(files), 0)
        for entry in files:
            target = self.repo_root / Path(entry["destination"])
            self.assertTrue(target.exists(), f"Missing mirrored file: {target}")
            self.assertGreater(entry["sizeBytes"], 0)
            self.assertLessEqual(entry["sizeBytes"], self.max_size_bytes)
            self.assertLessEqual(target.stat().st_size, self.max_size_bytes, target.as_posix())

    def test_mirror_excludes_large_raw_and_binary_artifacts(self) -> None:
        destinations = {entry["destination"] for entry in self.manifest["files"]}
        self.assertNotIn("tests/fixtures/portable/raw/upwork-jobs.csv/upwork-jobs.csv", destinations)
        for entry in self.manifest["files"]:
            suffix = Path(entry["destination"]).suffix.lower()
            self.assertNotIn(suffix, {".joblib", ".parquet", ".pyc"})

    def test_manifest_includes_useful_cross_machine_examples(self) -> None:
        destinations = {entry["destination"] for entry in self.manifest["files"]}
        self.assertIn(
            "tests/fixtures/portable/raw/World_Development_Indicators/World_Data.csv",
            destinations,
        )
        self.assertIn(
            "tests/fixtures/portable/raw/freelancer_earnings/freelancer_earnings_bd.csv",
            destinations,
        )
        self.assertIn(
            "tests/fixtures/portable/reports/label_provenance_audit.json",
            destinations,
        )
        self.assertIn(
            "tests/fixtures/portable/reports/m10_protected_pricing/latency.json",
            destinations,
        )


if __name__ == "__main__":
    unittest.main()

