from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any


REQUIRED_COLUMNS = ("candidate_id", "rank", "score", "reasoning")


def validate_ranked_candidates(
    csv_path: Path | str,
    expected_rows: int | None = None,
    score_breakdown_path: Path | str | None = None,
    firewall_enabled: bool = False,
) -> dict[str, Any]:
    path = Path(csv_path)
    errors: list[str] = []
    if not path.exists():
        return {"valid": False, "errors": [f"File does not exist: {path}"], "row_count": 0}

    rows: list[dict[str, str]] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                errors.append("CSV header is missing.")
            else:
                missing_columns = [
                    column for column in REQUIRED_COLUMNS if column not in reader.fieldnames
                ]
                if missing_columns:
                    errors.append(
                        f"Missing required columns: {', '.join(missing_columns)}"
                    )
            rows = list(reader)
    except (OSError, csv.Error, UnicodeDecodeError) as exc:
        return {"valid": False, "errors": [f"CSV is not readable: {exc}"], "row_count": 0}

    if expected_rows is not None and len(rows) != expected_rows:
        errors.append(f"Expected {expected_rows} rows, found {len(rows)}.")

    seen_ids: set[str] = set()
    ranks: list[int] = []
    for row_number, row in enumerate(rows, start=2):
        candidate_id = str(row.get("candidate_id") or "").strip()
        if not candidate_id:
            errors.append(f"Row {row_number}: candidate_id is empty.")
        elif candidate_id in seen_ids:
            errors.append(f"Row {row_number}: duplicate candidate_id '{candidate_id}'.")
        seen_ids.add(candidate_id)

        try:
            rank = int(str(row.get("rank") or ""))
            ranks.append(rank)
        except ValueError:
            errors.append(f"Row {row_number}: rank is not an integer.")

        try:
            score = float(str(row.get("score") or ""))
            if not math.isfinite(score) or not 0.0 <= score <= 1.0:
                errors.append(f"Row {row_number}: score must be between 0 and 1.")
        except ValueError:
            errors.append(f"Row {row_number}: score is not numeric.")

        if not str(row.get("reasoning") or "").strip():
            errors.append(f"Row {row_number}: reasoning is empty.")

    if ranks:
        expected_ranks = list(range(1, len(rows) + 1))
        if ranks != expected_ranks:
            errors.append("Ranks must start at 1 and be continuous in row order.")

    if firewall_enabled and score_breakdown_path is not None:
        breakdown = Path(score_breakdown_path)
        if not breakdown.exists():
            errors.append(f"Risk-aware score breakdown does not exist: {breakdown}")
        else:
            try:
                with breakdown.open("r", encoding="utf-8-sig", newline="") as handle:
                    risk_rows = list(csv.DictReader(handle))
                for row_number, row in enumerate(risk_rows, start=2):
                    try:
                        risk_score = float(str(row.get("risk_adjusted_score") or ""))
                        if not math.isfinite(risk_score) or not 0.0 <= risk_score <= 1.0:
                            errors.append(
                                f"Breakdown row {row_number}: risk_adjusted_score must be between 0 and 1."
                            )
                    except ValueError:
                        errors.append(
                            f"Breakdown row {row_number}: risk_adjusted_score is not numeric."
                        )
                    disqualified = str(row.get("disqualified") or "").lower() == "true"
                    if disqualified:
                        errors.append(
                            f"Breakdown row {row_number}: disqualified candidate appears in ranked output."
                        )
                    flags = str(row.get("risk_flags") or "")
                    if "\n" in flags or "\r" in flags:
                        errors.append(
                            f"Breakdown row {row_number}: risk_flags is not parseable."
                        )
                    try:
                        rank = int(str(row.get("rank") or "0"))
                    except ValueError:
                        rank = 0
                    if rank <= 10 and str(row.get("risk_level") or "").lower() == "severe":
                        errors.append(
                            f"Breakdown row {row_number}: severe-risk candidate appears in top 10."
                        )
            except (OSError, csv.Error, UnicodeDecodeError) as exc:
                errors.append(f"Risk-aware score breakdown is not readable: {exc}")

    return {"valid": not errors, "errors": errors, "row_count": len(rows)}
