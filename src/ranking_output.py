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
                    "score": f"{float(item['score']['final_score']):.6f}",
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
