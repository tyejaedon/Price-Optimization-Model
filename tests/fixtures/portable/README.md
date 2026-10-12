# Portable reference assets

This directory contains **tracked, small-footprint copies** of selected files from the ignored `data/raw/` and `reports/` trees.

Why this exists:

- `data/raw/` and `reports/` stay out of Git by repository policy.
- teammates still need a few useful reference inputs and report outputs on a fresh machine;
- copies here stay lightweight, inspectable, and safe for normal GitHub workflows.

Selection rules:

- source files come only from `data/raw/` and `reports/`;
- each file must be at or below **1 MB** by default;
- binary model artifacts such as `.joblib` and `.parquet` are excluded;
- curated copies are mirrored under `tests/fixtures/portable/` with a generated `manifest.json`.

Refresh the mirror from the current local workspace with:

```powershell
python .\scripts\sync_portable_reference_assets.py
```

Preview what would be selected without changing files:

```powershell
python .\scripts\sync_portable_reference_assets.py --dry-run
```

These files are for cross-machine development, fixture inspection, and reproducible documentation/tests. They are **not** the authoritative raw datasets or official released reports.

