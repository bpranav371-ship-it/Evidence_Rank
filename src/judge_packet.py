from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .utils import write_json


DOC_FILES = (
    "approach_deck.md",
    "demo_script.md",
    "judge_walkthrough.md",
    "submission_checklist.md",
    "faq_for_judges.md",
    "architecture_diagram.mmd",
    "scoring_pipeline_diagram.mmd",
    "evidence_flow_diagram.mmd",
)
OUTPUT_FILES = (
    "top10_explanation_cards.md",
    "judge_demo_packet.md",
    "final_reproduction_command.txt",
    "reproducibility_manifest.json",
    "runtime_profile_report.json",
    "final_submission_safety_report.json",
)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def build_judge_packet(
    docs_dir: Path | str,
    output_dir: Path | str,
    config: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Path]]:
    docs = Path(docs_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    settings = (config or {}).get("demo_materials", config or {})
    packet_name = str(settings.get("demo_packet_name", "demo_packet.zip"))
    cards = _load_json(output / "top10_explanation_cards.json").get("cards", [])
    runtime = _load_json(output / "runtime_profile_report.json")
    reproducibility = _load_json(output / "reproducibility_manifest.json")
    card_lines = [
        f"- Rank {card.get('rank')}: `{card.get('candidate_id')}` — "
        f"{card.get('judge_takeaway')}"
        for card in cards[:10]
    ] or ["- Top candidate cards are not available yet."]
    packet_path = output / "judge_demo_packet.md"
    packet_path.write_text(
        "\n".join(
            [
                "# EvidenceRank Judge Demo Packet",
                "",
                "## Project overview",
                "",
                "EvidenceRank is an offline candidate proof engine that ranks profiles by "
                "JD relevance, evidence support, production depth, risk, and bounded calibration.",
                "",
                "## Architecture summary",
                "",
                "Candidate records are streamed into fingerprints. A JD parser and Candidate "
                "Proof Graph feed baseline scoring, Honeypot Firewall checks, evidence "
                "calibration, and final CSV/audit generation.",
                "",
                "## Scoring summary",
                "",
                "The baseline combines JD relevance, required skills, proof alignment, "
                "retrieval/evaluation depth, production readiness, and modest hireability. "
                "Risk penalties and bounded evidence calibration refine the top pool.",
                "",
                "## Top candidate summary",
                "",
                *card_lines,
                "",
                "## Runtime summary",
                "",
                f"- Candidates measured: {runtime.get('candidate_count', 'not available')}",
                f"- Ranking runtime: {runtime.get('ranking_runtime_seconds', 'not available')} seconds",
                f"- Peak RSS: {runtime.get('peak_rss_memory_mb', 'not available')} MB",
                f"- 100,000-candidate projection: "
                f"{runtime.get('estimated_100000_candidate_ranking_seconds', 'not available')} seconds",
                "",
                "## Reproduce",
                "",
                "```powershell",
                str(
                    reproducibility.get(
                        "run_command_recommended",
                        "python run.py --jd data/input/job_description.txt --rank --top-k 100 "
                        "--enable-honeypot-firewall --enable-evidence-calibration",
                    )
                ),
                "```",
                "",
                "## File guide",
                "",
                "- `docs/approach_deck.md`: 12-slide deck content",
                "- `data/output/top10_explanation_cards.md`: evidence-grounded top candidates",
                "- `data/output/score_breakdown.csv`: transparent scoring",
                "- `data/output/final_submission_safety_report.json`: upload safety",
                "",
                "## Limitations",
                "",
                "Evidence matching is deterministic and lexical, proxy tests are not official "
                "labels, and risk/hireability signals require human review.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    candidates = [docs / name for name in DOC_FILES] + [output / name for name in OUTPUT_FILES]
    included = [path for path in candidates if path.exists()]
    missing = [str(path.name) for path in candidates if not path.exists()]
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "included_files": [
            str(path.relative_to(docs.parent)).replace("\\", "/")
            if path.is_relative_to(docs.parent)
            else path.name
            for path in included
        ],
        "missing_optional_files": missing,
        "raw_data_included": False,
        "candidate_fingerprints_included": False,
    }
    manifest_path = output / "demo_packet_manifest.json"
    write_json(manifest_path, manifest)
    included.append(manifest_path)
    zip_path = output / packet_name
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in included:
            if path.parent == docs:
                arcname = f"docs/{path.name}"
            else:
                arcname = f"data/output/{path.name}"
            archive.write(path, arcname=arcname)
    return manifest, {
        "judge_demo_packet": packet_path,
        "demo_packet_manifest": manifest_path,
        "demo_packet_zip": zip_path,
    }
