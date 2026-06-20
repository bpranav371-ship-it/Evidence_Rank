from __future__ import annotations

import csv
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .utils import write_json


REQUIRED_PACKAGE_FILES = (
    "ranked_candidates.csv",
    "score_breakdown.csv",
    "final_submission_safety_report.json",
    "reproducibility_manifest.json",
)
OPTIONAL_PACKAGE_FILES = (
    "top_candidate_proofs.jsonl",
    "runtime_profile_report.json",
    "ablation_report.json",
    "weight_sensitivity_report.json",
    "benchmark_report.json",
)


def _row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _expected_rows(output: Path, top_k: int) -> int:
    summary_path = output / "profiler_summary.json"
    if not summary_path.exists():
        return top_k
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        return min(top_k, max(0, int(summary.get("total_candidates_processed", top_k))))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return top_k


def _approach_summary() -> str:
    return """# EvidenceRank — Submission Approach

## What we built

EvidenceRank is a CPU-only, offline candidate proof engine that profiles candidates
incrementally and ranks them against a job description.

## Why keyword matching is weak

Keyword lists can reward copied buzzwords. EvidenceRank connects claimed skills to
career text, production work, retrieval/ranking evaluation, and profile consistency.

## Architecture and differentiators

- Candidate Proof Graph verifies skill claims against profile evidence.
- Honeypot Firewall assigns explainable risk signals without making accusations.
- Evidence Calibration rewards production depth and JD-specific proof.
- Hireability Calibration treats missing behavior data neutrally.
- Ablation, benchmark, safety, and sensitivity reports provide submission checks.

## Scoring

The deterministic baseline combines JD relevance, must-have skills, proof alignment,
retrieval/evaluation depth, production readiness, and hireability. Risk penalties and
bounded evidence calibration refine only a limited top pool.

## Reproduce

Run the commands in `final_reproduction_command.txt`.

## Outputs

The package contains the final ranked CSV, score breakdown, safety and reproducibility
reports, and available optional evaluation reports.

## Limitations and fairness

Proxy benchmarks are not official labels. Risk and hireability signals are ranking
confidence aids, not hiring decisions. Human review remains required.
"""


def build_submission_package(
    project_root: Path | str,
    output_dir: Path | str,
    config: dict[str, Any],
    *,
    top_k: int = 100,
) -> tuple[dict[str, Any], dict[str, Path]]:
    del project_root  # Kept in the API for future package metadata expansion.
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    package_config = config.get("submission_package", {})
    package_name = str(package_config.get("package_name", "submission_package.zip"))
    command = config.get("reproducibility", {}).get(
        "recommended_final_command",
        "python run.py --jd data/input/job_description.txt --rank --top-k 100 "
        "--enable-honeypot-firewall --enable-evidence-calibration",
    )
    profile_command = (
        "python run.py --input data/input/candidates.jsonl "
        "--jd data/input/job_description.txt --profile-and-rank "
        f"--top-k {top_k} --enable-honeypot-firewall --enable-evidence-calibration"
    )
    reproduction_path = output / "final_reproduction_command.txt"
    reproduction_path.write_text(
        f"{command}\n\n# If fingerprints do not exist:\n{profile_command}\n",
        encoding="utf-8",
    )
    summary_path = output / "approach_summary.md"
    summary_path.write_text(_approach_summary(), encoding="utf-8")

    missing_required = [
        filename for filename in REQUIRED_PACKAGE_FILES if not (output / filename).exists()
    ]
    missing_optional = [
        filename for filename in OPTIONAL_PACKAGE_FILES if not (output / filename).exists()
    ]
    safety_path = output / "final_submission_safety_report.json"
    safety = {}
    if safety_path.exists():
        try:
            safety = json.loads(safety_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            safety = {}
    reproducibility_path = output / "reproducibility_manifest.json"
    reproducibility = {}
    if reproducibility_path.exists():
        try:
            reproducibility = json.loads(reproducibility_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            reproducibility = {}
    manifest = {
        "package_created_at": datetime.now(timezone.utc).isoformat(),
        "included_files": [],
        "missing_required_files": missing_required,
        "missing_optional_files": missing_optional,
        "ranked_csv_rows": _row_count(output / "ranked_candidates.csv"),
        "top_k": top_k,
        "validation_passed": not missing_required,
        "safety_passed": bool(safety.get("passed", False)),
        "git_commit": reproducibility.get("current_git_commit_hash"),
        "command_to_reproduce": command,
        "warnings": [
            *(f"Missing required file: {name}" for name in missing_required),
            *(f"Optional report not included: {name}" for name in missing_optional),
        ],
    }
    manifest_path = output / "final_submission_manifest.json"
    package_path = output / package_name
    include_optional = bool(package_config.get("include_optional_reports", True))
    ranked_rows = _row_count(output / "ranked_candidates.csv")
    expected_rows = _expected_rows(output, top_k)
    manifest["ranked_csv_rows"] = ranked_rows
    manifest["validation_passed"] = not missing_required and ranked_rows == expected_rows
    candidate_files = [
        *(output / filename for filename in REQUIRED_PACKAGE_FILES),
        *(output / filename for filename in OPTIONAL_PACKAGE_FILES if include_optional),
        summary_path,
        reproduction_path,
        manifest_path,
    ]
    included = [path for path in candidate_files if path.exists() or path == manifest_path]
    manifest["included_files"] = [path.name for path in included]
    write_json(manifest_path, manifest)
    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in included:
            if path.exists():
                archive.write(path, arcname=path.name)
    return manifest, {
        "submission_package": package_path,
        "final_submission_manifest": manifest_path,
        "approach_summary": summary_path,
        "final_reproduction_command": reproduction_path,
    }
