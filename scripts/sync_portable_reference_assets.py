from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

DEFAULT_MAX_SIZE_MB = 1.0
TRACKING_ISSUE = 148
RAW_ALLOWED_EXTENSIONS = {".csv", ".json", ".md", ".txt"}
REPORT_ALLOWED_EXTENSIONS = {".csv", ".json", ".log", ".md", ".png", ".txt"}
EXCLUDED_EXTENSIONS = {".joblib", ".parquet", ".pyc"}
BINARY_EXTENSIONS = {".png"}


@dataclass(frozen=True)
class SyncCandidate:
    category: str
    source_root: Path
    source_path: Path
    destination_root: Path

    @property
    def relative_source(self) -> Path:
        return self.source_path.relative_to(self.source_root)

    @property
    def destination_path(self) -> Path:
        return self.destination_root / self.relative_source


def sha256_for_bytes(payload: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(payload)
    return digest.hexdigest()


def materialize_candidate_bytes(candidate: SyncCandidate) -> bytes:
    payload = candidate.source_path.read_bytes()
    if candidate.source_path.suffix.lower() not in BINARY_EXTENSIONS:
        payload = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return payload


def collect_candidates(
    source_root: Path,
    destination_root: Path,
    category: str,
    max_size_bytes: int,
    allowed_extensions: set[str],
) -> list[SyncCandidate]:
    candidates: list[SyncCandidate] = []
    for source_path in sorted(path for path in source_root.rglob("*") if path.is_file()):
        suffix = source_path.suffix.lower()
        if suffix in EXCLUDED_EXTENSIONS:
            continue
        if suffix not in allowed_extensions:
            continue
        if source_path.stat().st_size > max_size_bytes:
            continue
        candidates.append(
            SyncCandidate(
                category=category,
                source_root=source_root,
                source_path=source_path,
                destination_root=destination_root,
            )
        )
    return candidates


def reset_destination(root: Path, dry_run: bool) -> None:
    if dry_run:
        return
    if root.exists():
        for path in sorted((p for p in root.rglob("*") if p.is_file()), reverse=True):
            path.unlink()
        for path in sorted((p for p in root.rglob("*") if p.is_dir()), reverse=True):
            path.rmdir()
    root.mkdir(parents=True, exist_ok=True)


def copy_candidates(
    candidates: Iterable[SyncCandidate],
    repo_root: Path,
    dry_run: bool,
) -> list[dict[str, object]]:
    manifest_files: list[dict[str, object]] = []
    for candidate in candidates:
        destination_path = candidate.destination_path
        payload = materialize_candidate_bytes(candidate)
        if not dry_run:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            destination_path.write_bytes(payload)
        size_bytes = len(payload)
        sha256 = sha256_for_bytes(payload)
        manifest_files.append(
            {
                "category": candidate.category,
                "source": candidate.source_path.relative_to(repo_root).as_posix(),
                "sourceRelative": candidate.relative_source.as_posix(),
                "destination": destination_path.relative_to(repo_root).as_posix(),
                "sizeBytes": size_bytes,
                "sha256": sha256,
            }
        )
    return manifest_files


def build_manifest(repo_root: Path, max_size_mb: float, files: list[dict[str, object]]) -> dict[str, object]:
    return {
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "issue": TRACKING_ISSUE,
        "purpose": "Portable tracked mirrors of useful small raw/report reference files for cross-machine development.",
        "selectionPolicy": {
            "sourceDirectories": ["data/raw", "reports"],
            "trackedDestination": "tests/fixtures/portable",
            "maxFileSizeMB": max_size_mb,
            "excludeExtensions": sorted(EXCLUDED_EXTENSIONS),
            "rawAllowedExtensions": sorted(RAW_ALLOWED_EXTENSIONS),
            "reportAllowedExtensions": sorted(REPORT_ALLOWED_EXTENSIONS),
            "notes": [
                "Source directories remain git-ignored; only curated copies under tests/fixtures/portable are tracked.",
                "Large raw datasets and binary model artifacts are intentionally excluded.",
                "Use this mirror for cross-machine onboarding, fixture inspection, and reproducible docs/tests only.",
            ],
        },
        "summary": {
            "repository": repo_root.name,
            "fileCount": len(files),
            "totalBytes": sum(int(item["sizeBytes"]) for item in files),
            "rawFileCount": sum(1 for item in files if item["category"] == "raw"),
            "reportFileCount": sum(1 for item in files if item["category"] == "reports"),
        },
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__ or "Sync portable reference assets.")
    parser.add_argument("--max-size-mb", type=float, default=DEFAULT_MAX_SIZE_MB)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    raw_source = repo_root / "data" / "raw"
    reports_source = repo_root / "reports"
    portable_root = repo_root / "tests" / "fixtures" / "portable"
    raw_destination = portable_root / "raw"
    reports_destination = portable_root / "reports"
    manifest_path = portable_root / "manifest.json"

    max_size_bytes = int(args.max_size_mb * 1024 * 1024)

    raw_candidates = collect_candidates(
        source_root=raw_source,
        destination_root=raw_destination,
        category="raw",
        max_size_bytes=max_size_bytes,
        allowed_extensions=RAW_ALLOWED_EXTENSIONS,
    )
    report_candidates = collect_candidates(
        source_root=reports_source,
        destination_root=reports_destination,
        category="reports",
        max_size_bytes=max_size_bytes,
        allowed_extensions=REPORT_ALLOWED_EXTENSIONS,
    )

    all_candidates = [*raw_candidates, *report_candidates]

    reset_destination(raw_destination, dry_run=args.dry_run)
    reset_destination(reports_destination, dry_run=args.dry_run)

    files = copy_candidates(all_candidates, repo_root=repo_root, dry_run=args.dry_run)
    manifest = build_manifest(repo_root=repo_root, max_size_mb=args.max_size_mb, files=files)

    if args.dry_run:
        print(json.dumps(manifest, indent=2))
        return 0

    portable_root.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        f"Synced {manifest['summary']['fileCount']} files "
        f"({manifest['summary']['totalBytes']} bytes) to {portable_root.as_posix()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



