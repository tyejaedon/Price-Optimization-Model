"""Score anonymized System Usability Scale responses without retaining row-level results."""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from pathlib import Path
from typing import Sequence

SUS_ITEM_COUNT = 10
SUS_THRESHOLD = 80.0
PARTICIPANT_ID_PATTERN = re.compile(r"P[0-9]{3,}\Z")
EXPECTED_FIELDS = ["participant_id", *(f"item_{number}" for number in range(1, SUS_ITEM_COUNT + 1))]


def score_sus(responses: Sequence[int]) -> float:
    """Score the standard 10-item SUS response vector on its 0-100 scale."""
    if len(responses) != SUS_ITEM_COUNT:
        raise ValueError(f"Exactly {SUS_ITEM_COUNT} item responses are required.")
    if any(not isinstance(response, int) or response not in range(1, 6) for response in responses):
        raise ValueError("Every SUS response must be an integer from 1 through 5.")

    adjusted = sum(
        response - 1 if item_index % 2 == 0 else 5 - response
        for item_index, response in enumerate(responses)
    )
    return adjusted * 2.5


def analyze_responses(csv_path: Path) -> dict[str, float | int | bool | None]:
    scores: list[float] = []
    participant_ids: set[str] = set()
    with csv_path.open(newline="", encoding="utf-8-sig") as response_file:
        reader = csv.DictReader(response_file)
        if reader.fieldnames != EXPECTED_FIELDS:
            raise ValueError(f"CSV columns must be exactly: {', '.join(EXPECTED_FIELDS)}.")
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(f"Row {row_number}: unexpected extra CSV values.")
            participant_id = (row.get("participant_id") or "").strip()
            if PARTICIPANT_ID_PATTERN.fullmatch(participant_id) is None:
                raise ValueError(f"Row {row_number}: participant_id must be an anonymous code such as P001.")
            if participant_id in participant_ids:
                raise ValueError(f"Row {row_number}: duplicate anonymous participant_id.")
            participant_ids.add(participant_id)

            responses: list[int] = []
            for item_name in EXPECTED_FIELDS[1:]:
                value = (row.get(item_name) or "").strip()
                try:
                    response = int(value)
                except ValueError as exc:
                    raise ValueError(f"Row {row_number}: {item_name} must be an integer from 1 through 5.") from exc
                if response not in range(1, 6):
                    raise ValueError(f"Row {row_number}: {item_name} must be an integer from 1 through 5.")
                responses.append(response)
            scores.append(score_sus(responses))

    if not scores:
        raise ValueError("The CSV must contain at least one complete response.")

    mean_score = statistics.mean(scores)
    return {
        "sample_size": len(scores),
        "mean_sus": mean_score,
        "median_sus": statistics.median(scores),
        "standard_deviation_sus": statistics.stdev(scores) if len(scores) > 1 else None,
        "minimum_sus": min(scores),
        "maximum_sus": max(scores),
        "threshold": SUS_THRESHOLD,
        "threshold_met": mean_score >= SUS_THRESHOLD,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("responses_csv", type=Path, help="Local CSV; do not commit participant responses.")
    args = parser.parse_args()
    try:
        summary = analyze_responses(args.responses_csv)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
