from __future__ import annotations

import csv
import json
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .artifact_hasher import build_artifact_hashes, sha256_file
from .utils import write_json


BUNDLE_FILES = (
    "ranked_candidates.csv",
    "score_breakdown.csv",
    "EvidenceRank_Approach_Deck.pptx",
    "EvidenceRank_Approach_Deck.pdf",
    "final_submission_safety_report.json",
    "reproducibility_manifest.json",
    "runtime_profile_report.json",
    "approach_summary.md",
    "judge_demo_packet.md",
    "top10_explanation_cards.md",
    "final_reproduction_command.txt",
    "final_submission_manifest.json",
    "final_artifact_hashes.json",
    "EvidenceRank_One_Page_Summary.md",
    "EvidenceRank_Final_Submission_Guide.md",
)


def _git(project_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ("git", *args),
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def write_final_guides(output_dir: Path | str) -> dict[str, Path]:
    output = Path(output_dir)
    runtime = _json(output / "runtime_profile_report.json")
    reproduction = _json(output / "reproducibility_manifest.json")
    command = reproduction.get(
        "run_command_recommended",
        "python run.py --jd data/input/job_description.txt --rank --top-k 100 "
        "--enable-honeypot-firewall --enable-evidence-calibration",
    )
    summary_path = output / "EvidenceRank_One_Page_Summary.md"
    summary_path.write_text(
        f"""# EvidenceRank — Candidate Proof Engine

**One-line pitch:** An offline, proof-based candidate ranking system that verifies
skill claims against career evidence before protecting and calibrating the top ranks.

## Problem

Traditional résumé matching trusts keyword overlap, rewards stuffing, and can miss
strong candidates who describe real work without fashionable vocabulary.

## Solution

EvidenceRank streams candidate profiles into fingerprints, parses the JD, builds a
Candidate Proof Graph, applies deterministic ranking, protects the shortlist with a
Honeypot Firewall, and calibrates confidence using production and evaluation depth.

## Key differentiators

- Supported, weakly supported, and unsupported skill evidence
- Risk-aware top-10 protection without accusing candidates
- Bounded hireability and evidence calibration
- Transparent score breakdowns and proof snippets
- CPU-only, offline, deterministic, and reproducible

## System pipeline

Dataset → Streaming Profiler → Fingerprints → JD Parser → Proof Graph → Baseline
Ranker → Honeypot Firewall → Evidence Calibration → Final CSV + Audits

## Scoring summary

JD relevance, must-have skills, proof alignment, retrieval/evaluation depth,
production readiness, and hireability form the base score. Bounded risk penalties
and evidence calibration refine the final shortlist.

## Safety and validation

Final CSV validation, submission safety, benchmarks, ablation, sensitivity tests,
judge demo checks, reproducibility metadata, and SHA-256 artifact hashes are included.

## Performance

- Measured candidates: {runtime.get('candidate_count', 'not available')}
- Ranking runtime: {runtime.get('ranking_runtime_seconds', 'not available')} seconds
- 100,000-candidate projection: {runtime.get('estimated_100000_candidate_ranking_seconds', 'not available')} seconds
- Peak RSS: {runtime.get('peak_rss_memory_mb', 'not available')} MB

## Final outputs

`ranked_candidates.csv`, `score_breakdown.csv`, approach deck, proof/risk audits,
reproducibility manifest, demo packet, and final submission bundle.

## Reproduction command

```powershell
{command}
```
""",
        encoding="utf-8",
    )
    guide_path = output / "EvidenceRank_Final_Submission_Guide.md"
    guide_path.write_text(
        f"""# EvidenceRank Final Submission Guide

## Mandatory uploads

1. GitHub repository link
2. `data/output/ranked_candidates.csv`
3. `data/output/EvidenceRank_Approach_Deck.pdf` or `.pptx`

## Optional backup

- `data/output/final_submission_bundle.zip`

## Regenerate the final CSV

```powershell
{command}
```

## Regenerate the deck

```powershell
python run.py --export-deck --format pptx
python run.py --export-deck --format pdf
```

## Freeze the submission

```powershell
python run.py --freeze-submission --top-k 100
```

## Common mistakes to avoid

- Uploading or committing the raw candidate dataset
- Submitting an older ranked CSV
- Forgetting the deck PDF/PPTX
- Committing generated `data/output` artifacts
- Skipping `python run.py --judge-demo-check`
- Failing to verify exactly the expected top-100 rows
- Modifying files after the freeze without rebuilding hashes
""",
        encoding="utf-8",
    )
    return {"one_page_summary": summary_path, "final_submission_guide": guide_path}


def build_final_submission_bundle(
    output_dir: Path | str,
    config: dict[str, Any],
    *,
    top_k: int = 100,
) -> tuple[dict[str, Any], dict[str, Path]]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    guides = write_final_guides(output)
    if not (output / "final_artifact_hashes.json").exists():
        build_artifact_hashes(output)
    freeze_config = config.get("submission_freeze", {})
    bundle_name = str(freeze_config.get("final_bundle_name", "final_submission_bundle.zip"))
    included = [output / filename for filename in BUNDLE_FILES if (output / filename).exists()]
    missing = [filename for filename in BUNDLE_FILES if not (output / filename).exists()]
    bundle_path = output / bundle_name
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in included:
            archive.write(path, arcname=path.name)
    hash_report = _json(output / "final_artifact_hashes.json")
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "top_k": top_k,
        "included_files": [path.name for path in included],
        "missing_optional_files": missing,
        "bundle_sha256": sha256_file(bundle_path),
        "bundle_size_bytes": bundle_path.stat().st_size,
        "artifact_hashes": hash_report.get("artifacts", []),
        "raw_data_included": False,
        "candidate_fingerprints_included": False,
    }
    manifest_path = output / "submission_freeze_manifest.json"
    write_json(manifest_path, manifest)
    return manifest, {
        **guides,
        "submission_freeze_manifest": manifest_path,
        "final_submission_bundle": bundle_path,
    }


def build_freeze_report(
    project_root: Path | str,
    output_dir: Path | str,
    config: dict[str, Any],
    *,
    validation: dict[str, Any],
    safety: dict[str, Any],
    judge_check: dict[str, Any],
    bundle_manifest: dict[str, Any],
) -> dict[str, Any]:
    root = Path(project_root)
    output = Path(output_dir)
    freeze_config = config.get("submission_freeze", {})
    requirements = {
        "ranked_candidates.csv": bool(freeze_config.get("require_ranked_candidates", True)),
        "score_breakdown.csv": bool(freeze_config.get("require_score_breakdown", True)),
        "EvidenceRank_Approach_Deck.pptx": bool(freeze_config.get("require_deck", True)),
        "final_submission_safety_report.json": bool(freeze_config.get("require_safety_report", True)),
        "reproducibility_manifest.json": bool(
            freeze_config.get("require_reproducibility_manifest", True)
        ),
        "runtime_profile_report.json": bool(freeze_config.get("require_runtime_profile", False)),
    }
    missing = [
        filename for filename, required in requirements.items()
        if required and not (output / filename).exists()
    ]
    warnings = [
        f"Optional artifact is missing: {filename}"
        for filename, required in requirements.items()
        if not required and not (output / filename).exists()
    ]
    blocking = [
        *validation.get("errors", []),
        *safety.get("blocking_errors", []),
        *judge_check.get("blocking_errors", []),
        *(f"Required artifact is missing: {filename}" for filename in missing),
    ]
    branch = _git(root, "branch", "--show-current")
    commit = _git(root, "rev-parse", "HEAD")
    dirty_text = _git(root, "status", "--porcelain")
    if dirty_text:
        blocking.append(
            "Git working tree is dirty. Commit or remove source changes, then freeze again."
        )
    report = {
        "passed": not blocking,
        "blocking_errors": blocking,
        "warnings": warnings,
        "git_branch": branch,
        "git_commit": commit,
        "git_dirty_status": bool(dirty_text) if dirty_text is not None else None,
        "tests_last_known": "Run `python -m pytest -q` immediately before freeze.",
        "required_artifacts": [name for name, required in requirements.items() if required],
        "missing_artifacts": missing,
        "artifact_hashes_path": str(output / "final_artifact_hashes.json"),
        "final_bundle_path": str(output / "final_submission_bundle.zip"),
        "recommended_uploads": freeze_config.get(
            "recommended_uploads",
            [
                "GitHub repository link",
                "ranked_candidates.csv",
                "EvidenceRank_Approach_Deck.pdf or EvidenceRank_Approach_Deck.pptx",
            ],
        ),
        "final_commands": [
            "python run.py --jd data/input/job_description.txt --rank --top-k 100 "
            "--enable-honeypot-firewall --enable-evidence-calibration",
            "python run.py --freeze-submission --top-k 100",
        ],
        "bundle_manifest": bundle_manifest,
        "notes": (
            "The freeze is a deterministic readiness snapshot. Rebuild it after any "
            "ranked CSV, deck, configuration, or documentation change."
        ),
    }
    write_json(output / "final_submission_freeze_report.json", report)
    return report
