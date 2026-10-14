import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.download_upwork_jobs_dataset import choose_jobs_csv, download_upwork_jobs_dataset


class DownloadUpworkJobsDatasetTests(unittest.TestCase):
    def test_choose_jobs_csv_prefers_expected_upwork_jobs_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            other = root / "nested" / "freelance_jobs.csv"
            best = root / "exports" / "upwork-jobs-60k.csv"
            other.parent.mkdir(parents=True, exist_ok=True)
            best.parent.mkdir(parents=True, exist_ok=True)
            other.write_text("id\n1\n", encoding="utf-8")
            best.write_text("id\n2\n", encoding="utf-8")

            self.assertEqual(choose_jobs_csv(root), best)

    def test_download_copies_selected_csv_to_ingestion_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            download_dir = root / "downloaded"
            source = download_dir / "upwork-jobs.csv"
            target = root / "data" / "raw" / "upwork-jobs.csv" / "upwork-jobs.csv"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("title,description\nexample,test\n", encoding="utf-8")

            fake_kagglehub = type("FakeKaggleHub", (), {"dataset_download": staticmethod(lambda _: str(download_dir))})
            with patch("scripts.download_upwork_jobs_dataset.load_kagglehub", return_value=fake_kagglehub):
                result = download_upwork_jobs_dataset(target_path=target)

            self.assertEqual(result["mode"], "copied")
            self.assertTrue(target.exists())
            self.assertEqual(target.read_text(encoding="utf-8"), source.read_text(encoding="utf-8"))

    def test_download_dry_run_and_force_behaviour(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            download_dir = root / "downloaded"
            source = download_dir / "folder" / "upwork-jobs-export.csv"
            target = root / "data" / "raw" / "upwork-jobs.csv" / "upwork-jobs.csv"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("title\njob\n", encoding="utf-8")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("old\n", encoding="utf-8")

            fake_kagglehub = type("FakeKaggleHub", (), {"dataset_download": staticmethod(lambda _: str(download_dir))})
            with patch("scripts.download_upwork_jobs_dataset.load_kagglehub", return_value=fake_kagglehub):
                with self.assertRaises(FileExistsError):
                    download_upwork_jobs_dataset(target_path=target)
                dry_run = download_upwork_jobs_dataset(target_path=target, force=True, dry_run=True)
                self.assertEqual(dry_run["mode"], "dry-run")
                self.assertEqual(target.read_text(encoding="utf-8"), "old\n")
                copied = download_upwork_jobs_dataset(target_path=target, force=True)

            self.assertEqual(copied["mode"], "copied")
            self.assertEqual(target.read_text(encoding="utf-8"), source.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

