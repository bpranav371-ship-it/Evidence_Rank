from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .deck_materials import build_deck_materials
from .explanation_cards import build_explanation_cards
from .judge_packet import build_judge_packet
from .utils import write_json


def build_demo_pack(
    project_root: Path | str,
    output_dir: Path | str,
    config: dict[str, Any],
    *,
    top_n: int = 10,
) -> tuple[dict[str, Any], dict[str, Path]]:
    root = Path(project_root)
    output = Path(output_dir)
    if not (output / "ranked_candidates.csv").exists():
        raise FileNotFoundError("Run the final ranking command first.")
    docs_paths = build_deck_materials(root / "docs", config.get("demo_materials", {}))
    _, card_paths = build_explanation_cards(output, top_n=top_n)
    packet_manifest, packet_paths = build_judge_packet(
        root / "docs",
        output,
        config,
    )
    paths = {**docs_paths, **card_paths, **packet_paths}
    manifest = {
        "generated_files": {name: str(path) for name, path in paths.items()},
        "top_n_explanations": top_n,
        "packet": packet_manifest,
    }
    return manifest, paths


def _staged_raw_inputs(project_root: Path) -> list[str]:
    try:
        completed = subprocess.run(
            ("git", "diff", "--cached", "--name-only"),
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip().replace("\\", "/").startswith("data/input/")
        and not line.strip().endswith(".gitkeep")
    ]


def judge_demo_check(
    project_root: Path | str,
    output_dir: Path | str,
) -> dict[str, Any]:
    root = Path(project_root)
    output = Path(output_dir)
    required = {
        "README.md": root / "README.md",
        "docs/approach_deck.md": root / "docs" / "approach_deck.md",
        "docs/demo_script.md": root / "docs" / "demo_script.md",
        "docs/judge_walkthrough.md": root / "docs" / "judge_walkthrough.md",
        "docs/submission_checklist.md": root / "docs" / "submission_checklist.md",
        "docs/faq_for_judges.md": root / "docs" / "faq_for_judges.md",
        "docs/architecture_diagram.mmd": root / "docs" / "architecture_diagram.mmd",
        "docs/scoring_pipeline_diagram.mmd": root / "docs" / "scoring_pipeline_diagram.mmd",
        "docs/evidence_flow_diagram.mmd": root / "docs" / "evidence_flow_diagram.mmd",
        "data/output/top10_explanation_cards.md": output / "top10_explanation_cards.md",
        "data/output/judge_demo_packet.md": output / "judge_demo_packet.md",
        "data/output/demo_packet.zip": output / "demo_packet.zip",
        "data/output/ranked_candidates.csv": output / "ranked_candidates.csv",
        "data/output/score_breakdown.csv": output / "score_breakdown.csv",
        "data/output/final_submission_safety_report.json": output
        / "final_submission_safety_report.json",
        "data/output/reproducibility_manifest.json": output
        / "reproducibility_manifest.json",
    }
    file_checks = {name: path.exists() for name, path in required.items()}
    readme = (root / "README.md").read_text(encoding="utf-8") if (root / "README.md").exists() else ""
    feature_sections = {
        f"Feature {number}": f"Feature {number}" in readme for number in range(1, 7)
    }
    staged_raw = _staged_raw_inputs(root)
    blocking = [
        f"Missing required judge artifact: {name}"
        for name, exists in file_checks.items()
        if not exists
    ]
    if not all(feature_sections.values()):
        blocking.append("README.md does not mention all Feature 1–6 sections.")
    if staged_raw:
        blocking.append("Raw input data is staged in Git: " + ", ".join(staged_raw))
    report = {
        "passed": not blocking,
        "blocking_errors": blocking,
        "file_checks": file_checks,
        "readme_feature_sections": feature_sections,
        "staged_raw_input_files": staged_raw,
    }
    write_json(output / "judge_demo_check_report.json", report)
    return report
