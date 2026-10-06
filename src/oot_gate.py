"""Fail-closed software gate for chronological OOT report structure and R2.

Passing confirms only that a report has timezone-aware strictly ordered splits
and a finite test R2 at the fixed 0.75 threshold. It does not authenticate
label provenance, establish mentor-pricing accuracy, or pass the deferred
empirical #81/#91 gate. The current reports may be based on KES/hour proxy
labels; see ``../docs/Label_Provenance_Audit_91.md``.
"""

import argparse
import json
import math
from datetime import datetime
from pathlib import Path


def validate_oot_report(report: dict) -> float:
    """Validate chronological timestamps and finite test R2 >= 0.75.

    Raises ``ValueError`` when required evidence is incomplete, non-chronological,
    timezone-naive, or below threshold; returns the unrounded test R2 otherwise.
    """
    if report.get("evaluation_protocol") != "chronological_out_of_time":
        raise ValueError("chronological out-of-time evaluation required")
    try:
        train_end = datetime.fromisoformat(report["train_end"])
        test_start = datetime.fromisoformat(report["test_start"])
        r2 = report["test"]["r2"]
        if train_end.tzinfo is None or test_start.tzinfo is None or train_end >= test_start:
            raise ValueError("test timestamps must follow training with explicit time zones")
        if "time_cutoff" in report:
            cutoff = datetime.fromisoformat(report["time_cutoff"])
            if cutoff.tzinfo is None or not train_end <= cutoff < test_start:
                raise ValueError("OOT cutoff must separate training from strictly later test records")
        if isinstance(r2, bool) or not isinstance(r2, (float, int)) or not math.isfinite(r2):
            raise ValueError("test R2 must be finite")
        if r2 < 0.75:
            raise ValueError(f"OOT test R2 {r2} is below 0.75")
    except (KeyError, TypeError) as exc:
        raise ValueError("incomplete chronological OOT evidence") from exc
    return float(r2)


def main() -> None:
    """Validate a JSON OOT report supplied on the command line."""
    parser = argparse.ArgumentParser(description="Gate chronological OOT test R2 >= 0.75")
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    r2 = validate_oot_report(json.loads(args.report.read_text(encoding="utf-8")))
    print(f"Chronological OOT test R2: {r2:.4f}")


if __name__ == "__main__":
    main()
