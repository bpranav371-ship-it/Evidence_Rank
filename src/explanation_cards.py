from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .utils import write_json


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _proofs_for_ids(path: Path, candidate_ids: set[str]) -> dict[str, dict[str, Any]]:
    proofs: dict[str, dict[str, Any]] = {}
    if not path.exists() or not candidate_ids:
        return proofs
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            candidate_id = str(payload.get("candidate_id") or "")
            if candidate_id in candidate_ids:
                proofs[candidate_id] = payload
                if len(proofs) == len(candidate_ids):
                    break
    return proofs


def _strengths(row: dict[str, str], proof: dict[str, Any]) -> list[str]:
    graph = proof.get("proof_graph") or {}
    strengths: list[str] = []
    supported = list(graph.get("supported_skills") or [])
    if supported:
        strengths.append("Career evidence supports " + ", ".join(map(str, supported[:5])) + ".")
    if _float(row.get("retrieval_ranking_evidence_score")) >= 0.5:
        strengths.append("Strong retrieval or ranking evidence is present.")
    if _float(row.get("evaluation_evidence_score")) >= 0.5:
        strengths.append("Evaluation metrics or experimentation are supported.")
    if _float(row.get("production_evidence_score")) >= 0.5:
        strengths.append("Production deployment evidence is present.")
    if _float(row.get("evidence_confidence_score")) >= 0.5:
        strengths.append("Evidence confidence is above the calibrated midpoint.")
    return strengths or ["The score reflects partial JD alignment; explicit proof is limited."]


def _risk_notes(row: dict[str, str]) -> list[str]:
    risk_level = str(row.get("risk_level") or "low").lower()
    flags = [flag for flag in str(row.get("risk_flags") or "").split("|") if flag]
    notes = [f"Honeypot risk level: {risk_level}."]
    if flags:
        notes.append("Observed flags: " + ", ".join(flag.replace("_", " ") for flag in flags[:4]) + ".")
    if _float(row.get("penalty_score")) > 0:
        notes.append(f"Basic profile penalty: {_float(row.get('penalty_score')):.3f}.")
    if _float(row.get("calibration_penalty")) > 0:
        notes.append(f"Evidence calibration penalty: {_float(row.get('calibration_penalty')):.3f}.")
    return notes


def _hireability_notes(row: dict[str, str]) -> list[str]:
    score = _float(
        row.get("calibrated_hireability_score"),
        _float(row.get("hireability_score"), 0.5),
    )
    if score >= 0.65:
        message = "Positive behavioral or availability evidence supports interview readiness."
    elif score <= 0.35:
        message = "Behavioral or availability evidence is weak or negative."
    else:
        message = "Hireability evidence is neutral or incomplete and does not dominate ranking."
    return [message, f"Calibrated hireability score: {score:.3f}."]


def build_explanation_cards(
    output_dir: Path | str,
    top_n: int = 10,
) -> tuple[list[dict[str, Any]], dict[str, Path]]:
    output = Path(output_dir)
    ranked_path = output / "ranked_candidates.csv"
    breakdown_path = output / "score_breakdown.csv"
    proof_path = output / "top_candidate_proofs.jsonl"
    if not ranked_path.exists() or not breakdown_path.exists():
        raise FileNotFoundError("Run the final ranking command first.")

    ranked = _read_csv(ranked_path)[: max(1, top_n)]
    breakdown_by_id = {
        str(row.get("candidate_id") or ""): row for row in _read_csv(breakdown_path)
    }
    candidate_ids = {str(row.get("candidate_id") or "") for row in ranked}
    proofs = _proofs_for_ids(proof_path, candidate_ids)
    cards: list[dict[str, Any]] = []
    for ranked_row in ranked:
        candidate_id = str(ranked_row.get("candidate_id") or "")
        score_row = breakdown_by_id.get(candidate_id, {})
        proof = proofs.get(candidate_id, {})
        graph = proof.get("proof_graph") or {}
        snippets = [
            str(snippet).strip()
            for snippet in (proof.get("top_evidence_snippets") or [])
            if str(snippet).strip()
        ][:5]
        strengths = _strengths(score_row, proof)
        risk_notes = _risk_notes(score_row)
        hireability = _hireability_notes(score_row)
        reasoning = str(ranked_row.get("reasoning") or "").strip()
        card = {
            "rank": int(ranked_row.get("rank") or len(cards) + 1),
            "candidate_id": candidate_id,
            "final_score": _float(score_row.get("final_score"), _float(ranked_row.get("score"))),
            "risk_adjusted_score": _float(score_row.get("risk_adjusted_score")),
            "calibrated_final_score": _float(
                score_row.get("calibrated_final_score"), _float(ranked_row.get("score"))
            ),
            "headline_summary": reasoning or "Evidence-based candidate ranking summary.",
            "why_ranked_high": "; ".join(item.rstrip(".") for item in strengths[:3]) + ".",
            "evidence_strengths": strengths,
            "risk_or_penalty_notes": risk_notes,
            "hireability_notes": hireability,
            "top_evidence_snippets": snippets or ["No explicit snippet available"],
            "score_breakdown_table": {
                "JD relevance": _float(score_row.get("jd_relevance_score")),
                "Must-have skills": _float(score_row.get("must_have_skill_score")),
                "Proof alignment": _float(score_row.get("proof_alignment_score")),
                "Retrieval/ranking": _float(score_row.get("retrieval_ranking_evidence_score")),
                "Evaluation": _float(score_row.get("evaluation_evidence_score")),
                "Production": _float(score_row.get("production_evidence_score")),
                "Evidence confidence": _float(score_row.get("evidence_confidence_score")),
                "Honeypot risk": _float(score_row.get("honeypot_risk_score")),
            },
            "judge_takeaway": (
                "This rank is based on traceable profile evidence, component scores, and "
                f"a {str(score_row.get('risk_level') or 'low').lower()} risk assessment."
            ),
            "proof_summary": str(graph.get("proof_summary") or ""),
        }
        cards.append(card)

    json_path = output / "top10_explanation_cards.json"
    markdown_path = output / "top10_explanation_cards.md"
    write_json(json_path, {"top_n": len(cards), "cards": cards})
    lines = [
        "# EvidenceRank Top Candidate Explanation Cards",
        "",
        "These cards summarize existing deterministic scores and proof snippets. "
        "They do not introduce new evidence.",
        "",
    ]
    for card in cards:
        lines.extend(
            [
                f"## Rank {card['rank']} — {card['candidate_id']}",
                "",
                f"**Final score:** {card['final_score']:.3f}  ",
                f"**Risk-adjusted score:** {card['risk_adjusted_score']:.3f}  ",
                f"**Calibrated final score:** {card['calibrated_final_score']:.3f}",
                "",
                f"**Why ranked high:** {card['why_ranked_high']}",
                "",
                "**Evidence strengths:**",
                "",
                *[f"- {item}" for item in card["evidence_strengths"]],
                "",
                "**Risk or penalty notes:**",
                "",
                *[f"- {item}" for item in card["risk_or_penalty_notes"]],
                "",
                "**Hireability notes:**",
                "",
                *[f"- {item}" for item in card["hireability_notes"]],
                "",
                "**Top evidence snippets:**",
                "",
                *[f"- {item}" for item in card["top_evidence_snippets"]],
                "",
                "**Score breakdown:**",
                "",
                "| Component | Score |",
                "|---|---:|",
                *[
                    f"| {name} | {value:.3f} |"
                    for name, value in card["score_breakdown_table"].items()
                ],
                "",
                f"**Judge takeaway:** {card['judge_takeaway']}",
                "",
            ]
        )
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return cards, {
        "top10_explanation_cards_markdown": markdown_path,
        "top10_explanation_cards_json": json_path,
    }
