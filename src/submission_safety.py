from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .submission_validator import validate_ranked_candidates
from .utils import write_json


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def validate_final_submission(
    output_dir: Path | str,
    top_k: int = 100,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or {}
    output = Path(output_dir)
    ranked_path = output / "ranked_candidates.csv"
    breakdown_path = output / "score_breakdown.csv"
    proof_path = output / "top_candidate_proofs.jsonl"
    report_path = output / "final_submission_safety_report.json"
    reproduction_path = output / "final_reproduction_command.txt"
    blocking: list[str] = []
    warnings: list[str] = []
    actions: list[str] = []
    expected_rows = top_k
    summary_path = output / "profiler_summary.json"
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            processed = int(summary.get("total_candidates_processed", top_k))
            if processed >= 0:
                expected_rows = min(top_k, processed)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            warnings.append("profiler_summary.json could not be used for row-count validation.")
    base = validate_ranked_candidates(
        ranked_path,
        expected_rows=expected_rows,
        score_breakdown_path=breakdown_path,
    )
    blocking.extend(base["errors"])
    rows: list[dict[str, str]] = []
    breakdown: list[dict[str, str]] = []
    if ranked_path.exists():
        with ranked_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    if breakdown_path.exists():
        with breakdown_path.open("r", encoding="utf-8-sig", newline="") as handle:
            breakdown = list(csv.DictReader(handle))
    else:
        blocking.append("score_breakdown.csv is missing.")
    if rows and tuple(rows[0].keys()) != ("candidate_id", "rank", "score", "reasoning"):
        blocking.append(
            "ranked_candidates.csv must contain exactly: candidate_id, rank, score, reasoning."
        )
    if breakdown:
        final_score_columns = {
            "final_score", "risk_adjusted_score", "calibrated_final_score"
        }
        if not final_score_columns.intersection(breakdown[0]):
            warnings.append("score_breakdown.csv has no recognized final score column.")
    scores = [_number(row["score"]) for row in rows if row.get("score")]
    if scores and scores != sorted(scores, reverse=True):
        blocking.append("Scores are not monotonically descending.")
    if len(set(scores)) <= 1 and scores:
        blocking.append("All scores are identical.")
    if len(scores) >= 10 and max(scores[:10]) - min(scores[:10]) <= float(
        config.get("warn_if_all_scores_within", 0.02)
    ):
        warnings.append("Top-10 scores are unusually flat.")
    min_reasoning = int(config.get("min_reasoning_chars", 40))
    lengths = [len((row.get("reasoning") or "").strip()) for row in rows]
    if any(length < min_reasoning for length in lengths):
        blocking.append(f"At least one reasoning entry is shorter than {min_reasoning} characters.")
    if any(length < min_reasoning for length in lengths[:10]):
        blocking.append("Top-10 reasoning is not detailed enough.")
    severe_top10 = [
        row for row in breakdown[:10] if (row.get("risk_level") or "").lower() == "severe"
    ]
    if len(severe_top10) > int(config.get("max_top10_severe_risk", 0)):
        blocking.append("A severe-risk candidate appears in the top 10.")
    if any((row.get("disqualified") or "").lower() == "true" for row in breakdown):
        blocking.append("A disqualified candidate appears in ranked output.")
    if any("empty_profile_text" in (row.get("risk_flags") or "") for row in breakdown[:10]):
        blocking.append("An empty-profile candidate appears in the top 10.")
    if not proof_path.exists():
        warnings.append("top_candidate_proofs.jsonl is missing.")
    firewall_files = ("honeypot_audit.json", "honeypot_flags.csv", "rerank_audit_top100.csv")
    calibration_files = (
        "evidence_calibration_report.json",
        "jd_constraints_report.json",
        "hireability_audit.csv",
    )
    risk_enabled = any(
        (row.get("risk_flags") or "").strip()
        or _number(row.get("honeypot_risk_score")) > 0
        for row in breakdown
    )
    if risk_enabled:
        for filename in firewall_files:
            if not (output / filename).exists():
                warnings.append(f"{filename} is missing despite risk-aware output.")
    calibration_enabled = any(
        _number(row.get("evidence_confidence_score")) > 0
        or _number(row.get("calibration_bonus")) > 0
        or _number(row.get("calibration_penalty")) > 0
        for row in breakdown
    )
    if calibration_enabled:
        for filename in calibration_files:
            if not (output / filename).exists():
                warnings.append(f"{filename} is missing despite calibrated output.")
    if not reproduction_path.exists():
        warnings.append(
            "final_reproduction_command.txt is not present yet; packaging will create it."
        )
    if warnings:
        actions.append("Review warnings before final upload.")
    if blocking:
        actions.append("Fix all blocking errors and rerun validation.")
    report = {
        "passed": not blocking,
        "blocking_errors": blocking,
        "warnings": warnings,
        "recommended_actions": actions,
        "file_checks": {
            "ranked_candidates_exists": ranked_path.exists(),
            "score_breakdown_exists": breakdown_path.exists(),
            "top_candidate_proofs_exists": proof_path.exists(),
            "final_reproduction_command_exists": reproduction_path.exists(),
            "row_count": len(rows),
            "expected_row_count": expected_rows,
        },
        "ranking_quality_checks": {
            "scores_descending": scores == sorted(scores, reverse=True) if scores else False,
            "scores_not_identical": len(set(scores)) > 1 if scores else False,
            "average_reasoning_length": round(sum(lengths) / max(1, len(lengths)), 2),
            "severe_risk_in_top10": len(severe_top10),
            "top10_score_range": round(max(scores[:10]) - min(scores[:10]), 6)
            if len(scores) >= 10
            else None,
        },
    }
    write_json(report_path, report)
    return report
