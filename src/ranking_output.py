from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .utils import write_jsonl_record


RANKED_COLUMNS = ("candidate_id", "rank", "score", "reasoning")
BREAKDOWN_COLUMNS = (
    "candidate_id",
    "rank",
    "final_score",
    "risk_adjusted_score",
    "calibrated_final_score",
    "evidence_confidence_score",
    "career_depth_score",
    "jd_constraint_match_score",
    "negative_constraint_penalty",
    "calibrated_hireability_score",
    "top10_readiness_score",
    "calibration_bonus",
    "calibration_penalty",
    "honeypot_risk_score",
    "honeypot_penalty",
    "risk_level",
    "disqualified",
    "risk_flags",
    "jd_relevance_score",
    "must_have_skill_score",
    "proof_alignment_score",
    "retrieval_ranking_evidence_score",
    "evaluation_evidence_score",
    "production_evidence_score",
    "hireability_score",
    "penalty_score",
    "strict_rerank_applied",
    "reasoning",
)


def build_reasoning(item: dict[str, Any]) -> str:
    score = item["score"]
    proof = item["proof_graph"]
    strengths: list[str] = []
    supported = proof.get("supported_skills", [])
    if supported:
        strengths.append(f"supported evidence for {', '.join(supported[:4])}")
    if float(score.get("retrieval_ranking_evidence_score", 0.0)) >= 0.25:
        strengths.append("retrieval/ranking work")
    if float(score.get("evaluation_evidence_score", 0.0)) >= 0.25:
        strengths.append("evaluation practice")
    if float(score.get("production_evidence_score", 0.0)) >= 0.25:
        strengths.append("production deployment")
    if not strengths:
        strengths.append("partial JD term alignment")

    concerns: list[str] = []
    unsupported = score.get("unsupported_required_skills", [])
    if unsupported:
        concerns.append(f"limited proof for {', '.join(unsupported[:3])}")
    if score.get("neutral_hireability_used"):
        concerns.append("availability signals are incomplete")
    if float(score.get("penalty_score", 0.0)) > 0:
        concerns.append("basic profile-quality penalties apply")
    if score.get("firewall_enabled"):
        risk_level = str(score.get("risk_level", "low"))
        if risk_level == "low":
            strengths.append("low honeypot risk")
        elif score.get("risk_flags"):
            concerns.append(
                "risk flags: "
                + ", ".join(str(flag).replace("_", " ") for flag in score["risk_flags"][:2])
            )
    if score.get("calibration_enabled"):
        if float(score.get("top10_readiness_score", 0.0)) >= 0.65:
            strengths.append("strong top-10 evidence readiness")
        negatives = score.get("negative_constraints_triggered") or []
        if negatives:
            concerns.append(
                "calibration constraints: "
                + ", ".join(str(value).replace("_", " ") for value in negatives[:2])
            )

    reasoning = f"Evidence-based match: {'; '.join(strengths)}."
    if concerns:
        reasoning += f" Concern: {'; '.join(concerns)}."
    return reasoning


def write_ranking_outputs(
    ranked_candidates: list[dict[str, Any]],
    output_dir: Path | str,
) -> dict[str, Path]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    ranked_path = target / "ranked_candidates.csv"
    breakdown_path = target / "score_breakdown.csv"
    proofs_path = target / "top_candidate_proofs.jsonl"

    with ranked_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RANKED_COLUMNS)
        writer.writeheader()
        for item in ranked_candidates:
            reasoning = build_reasoning(item)
            item["reasoning"] = reasoning
            writer.writerow(
                {
                    "candidate_id": item["candidate_id"],
                    "rank": item["rank"],
                    "score": f"{float(item['score'].get('calibrated_final_score', item['score'].get('risk_adjusted_score', item['score']['final_score']))):.6f}",
                    "reasoning": reasoning,
                }
            )

    with breakdown_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BREAKDOWN_COLUMNS)
        writer.writeheader()
        for item in ranked_candidates:
            score = item["score"]
            writer.writerow(
                {
                    "candidate_id": item["candidate_id"],
                    "rank": item["rank"],
                    "final_score": f"{float(score['final_score']):.6f}",
                    "risk_adjusted_score": f"{float(score.get('risk_adjusted_score', score['final_score'])):.6f}",
                    "calibrated_final_score": f"{float(score.get('calibrated_final_score', score.get('risk_adjusted_score', score['final_score']))):.6f}",
                    "evidence_confidence_score": score.get("evidence_confidence_score", 0.0),
                    "career_depth_score": score.get("career_depth_score", 0.0),
                    "jd_constraint_match_score": score.get("jd_constraint_match_score", 0.0),
                    "negative_constraint_penalty": score.get("negative_constraint_penalty", 0.0),
                    "calibrated_hireability_score": score.get("calibrated_hireability_score", score.get("hireability_score", 0.5)),
                    "top10_readiness_score": score.get("top10_readiness_score", 0.0),
                    "calibration_bonus": score.get("calibration_bonus", 0.0),
                    "calibration_penalty": score.get("calibration_penalty", 0.0),
                    "honeypot_risk_score": score.get("honeypot_risk_score", 0.0),
                    "honeypot_penalty": score.get("honeypot_penalty", 0.0),
                    "risk_level": score.get("risk_level", "low"),
                    "disqualified": score.get("disqualified", False),
                    "risk_flags": "|".join(score.get("risk_flags") or []),
                    "jd_relevance_score": score["jd_relevance_score"],
                    "must_have_skill_score": score["must_have_skill_score"],
                    "proof_alignment_score": score["proof_alignment_score"],
                    "retrieval_ranking_evidence_score": score[
                        "retrieval_ranking_evidence_score"
                    ],
                    "evaluation_evidence_score": score["evaluation_evidence_score"],
                    "production_evidence_score": score["production_evidence_score"],
                    "hireability_score": score["hireability_score"],
                    "penalty_score": score["penalty_score"],
                    "strict_rerank_applied": score["strict_rerank_applied"],
                    "reasoning": item["reasoning"],
                }
            )

    with proofs_path.open("w", encoding="utf-8") as handle:
        for item in ranked_candidates:
            proof_graph = item["proof_graph"]
            snippets = [
                snippet
                for values in proof_graph.get("evidence_snippets", {}).values()
                for snippet in values
            ]
            write_jsonl_record(
                handle,
                {
                    "candidate_id": item["candidate_id"],
                    "rank": item["rank"],
                    "proof_graph": proof_graph,
                    "top_evidence_snippets": snippets[:5],
                },
            )

    return {
        "ranked_candidates": ranked_path,
        "score_breakdown": breakdown_path,
        "top_candidate_proofs": proofs_path,
    }
