from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .utils import write_json


DEFAULT_ARTIFACTS = (
    "ranked_candidates.csv",
    "score_breakdown.csv",
    "EvidenceRank_Approach_Deck.pptx",
    "EvidenceRank_Approach_Deck.pdf",
    "submission_package.zip",
    "demo_packet.zip",
    "final_submission_safety_report.json",
    "reproducibility_manifest.json",
    "runtime_profile_report.json",
    "final_reproduction_command.txt",
    "final_submission_manifest.json",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_artifact_hashes(
    output_dir: Path | str,
    filenames: Iterable[str] = DEFAULT_ARTIFACTS,
) -> dict[str, Any]:
    output = Path(output_dir)
    artifacts: list[dict[str, Any]] = []
    missing: list[str] = []
    for filename in filenames:
        normalized = str(filename).replace("\\", "/")
        if normalized.startswith("data/input/") or "candidate_fingerprints" in normalized:
            continue
        path = output / filename
        if not path.exists():
            missing.append(filename)
            continue
        artifacts.append(
            {
                "file_path": filename,
                "sha256": sha256_file(path),
                "file_size_bytes": path.stat().st_size,
            }
        )
    report = {
        "algorithm": "sha256",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "artifacts": artifacts,
        "missing_files": missing,
        "raw_data_hashed": False,
        "candidate_fingerprints_hashed": False,
    }
    path = output / "final_artifact_hashes.json"
    write_json(path, report)
    report["output_path"] = str(path)
    return report
