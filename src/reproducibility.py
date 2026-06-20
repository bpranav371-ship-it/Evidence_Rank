from __future__ import annotations

import hashlib
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .utils import write_json


EXPECTED_OUTPUTS = (
    "ranked_candidates.csv",
    "score_breakdown.csv",
    "top_candidate_proofs.jsonl",
    "final_submission_safety_report.json",
    "reproducibility_manifest.json",
)


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_value(project_root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ("git", *args),
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return completed.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def build_reproducibility_manifest(
    project_root: Path | str,
    output_dir: Path | str,
    config: dict[str, Any],
    *,
    top_k: int = 100,
    firewall_enabled: bool = True,
    calibration_enabled: bool = True,
) -> dict[str, Any]:
    root = Path(project_root)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    reproducibility = config.get("reproducibility", {})
    commit = _git_value(root, "rev-parse", "HEAD")
    branch = _git_value(root, "branch", "--show-current")
    status = _git_value(root, "status", "--porcelain")
    manifest = {
        "project_name": "EvidenceRank — Candidate Proof Engine",
        "repository_url": reproducibility.get(
            "repository_url",
            "https://github.com/bpranav371-ship-it/Evidence_Rank.git",
        ),
        "current_git_commit_hash": commit,
        "current_git_branch": branch,
        "git_dirty_status": bool(status) if status is not None else None,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "requirements_hash": _sha256(root / "requirements.txt"),
        "config_hash": _sha256(root / "config.yaml"),
        "run_command_recommended": reproducibility.get(
            "recommended_final_command",
            "python run.py --jd data/input/job_description.txt --rank --top-k 100 "
            "--enable-honeypot-firewall --enable-evidence-calibration",
        ),
        "input_files_expected": [
            "data/input/candidates.jsonl",
            "data/input/job_description.txt",
        ],
        "output_files_expected": list(EXPECTED_OUTPUTS),
        "random_seed": int(reproducibility.get("random_seed", 42)),
        "ranking_mode_used": "risk_aware_evidence_calibrated",
        "firewall_enabled": firewall_enabled,
        "calibration_enabled": calibration_enabled,
        "top_k": top_k,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notes": (
            "The manifest contains hashes and filenames only. It does not include raw "
            "candidate records or private dataset contents."
        ),
    }
    path = output / "reproducibility_manifest.json"
    write_json(path, manifest)
    manifest["output_path"] = str(path)
    return manifest
