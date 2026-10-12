from __future__ import annotations

import argparse
import importlib
import shutil
from pathlib import Path

DATASET_HANDLE = "ahmedmyalo/upwork-freelance-jobs-60k"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TARGET = PROJECT_ROOT / "data" / "raw" / "upwork-jobs.csv" / "upwork-jobs.csv"


def load_kagglehub():
    try:
        return importlib.import_module("kagglehub")
    except ImportError as exc:  # pragma: no cover - exercised via unit test
        raise RuntimeError(
            "kagglehub is required for the Upwork jobs downloader. "
            "Install dependencies from requirements.txt and configure Kaggle credentials first."
        ) from exc


def choose_jobs_csv(download_root: Path) -> Path:
    candidates = sorted(path for path in download_root.rglob("*.csv") if path.is_file())
    if not candidates:
        raise FileNotFoundError(f"No CSV files found under downloaded dataset directory: {download_root}")

    def rank(path: Path) -> tuple[int, int, str]:
        name = path.name.lower()
        score = 100
        if "upwork-jobs" in name:
            score -= 90
        if "upwork" in name and "job" in name:
            score -= 60
        if "freelance" in name:
            score -= 15
        return score, len(path.parts), name

    return min(candidates, key=rank)


def download_upwork_jobs_dataset(
    target_path: Path = DEFAULT_TARGET,
    *,
    dataset_handle: str = DATASET_HANDLE,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, str]:
    kagglehub = load_kagglehub()
    download_root = Path(kagglehub.dataset_download(dataset_handle)).resolve()
    source_csv = choose_jobs_csv(download_root)
    target_path = target_path.resolve()

    if target_path.exists() and not force:
        raise FileExistsError(
            f"Target already exists: {target_path}. Use --force to overwrite the local raw dataset copy."
        )

    if not dry_run:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_csv, target_path)

    return {
        "datasetHandle": dataset_handle,
        "downloadRoot": download_root.as_posix(),
        "sourceCsv": source_csv.as_posix(),
        "targetCsv": target_path.as_posix(),
        "mode": "dry-run" if dry_run else "copied",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download the Kaggle Upwork jobs dataset into the ignored raw-data path "
            "expected by src.ingest_multisource."
        )
    )
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--dataset-handle", default=DATASET_HANDLE)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = download_upwork_jobs_dataset(
        target_path=args.target,
        dataset_handle=args.dataset_handle,
        force=args.force,
        dry_run=args.dry_run,
    )
    print(f"Dataset download root: {result['downloadRoot']}")
    print(f"Selected source CSV: {result['sourceCsv']}")
    print(f"Target CSV path: {result['targetCsv']}")
    print(f"Result: {result['mode']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

