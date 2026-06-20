from __future__ import annotations

from typing import Any

from .utils import clamp


DEFAULT_NEGATIVE_PENALTIES = {
    "research_only_without_production": 0.05,
    "service_only_without_ai_depth": 0.05,
    "keyword_only_without_evidence": 0.10,
    "no_retrieval_or_ranking_evidence": 0.08,
    "no_evaluation_evidence": 0.06,
    "no_production_evidence": 0.06,
    "missing_must_have_skill": 0.10,
}


def calibrate_evidence(
    fingerprint: dict[str, Any],
    proof_graph: dict[str, Any],
    career: dict[str, Any],
    constraints: dict[str, Any],
    hireability: dict[str, Any],
    risk_report: dict[str, Any] | None,
    component_scores: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or {}
    weights = {
        "evidence_confidence": 0.30,
        "career_depth": 0.15,
        "jd_constraint_match": 0.25,
        "hireability": 0.10,
        "top10_readiness": 0.20,
        **(config.get("weights") or {}),
    }
    max_bonus = float(config.get("max_calibration_bonus", 0.08))
    max_penalty = float(config.get("max_calibration_penalty", 0.15))
    negative_weights = {
        **DEFAULT_NEGATIVE_PENALTIES,
        **(config.get("negative_constraint_penalties") or {}),
    }

    proof_alignment = float(proof_graph.get("proof_alignment_score", 0.0))
    production = float(career.get("production_depth_score", 0.0))
    retrieval = float(career.get("retrieval_depth_score", 0.0))
    evaluation = float(career.get("evaluation_depth_score", 0.0))
    consistency = float(career.get("career_consistency_score", 0.5))
    career_depth = float(career.get("career_depth_score", 0.0))
    required = constraints.get("required_positive_skills") or []
    supported = set(proof_graph.get("supported_skills") or [])
    weak = set(proof_graph.get("weakly_supported_skills") or [])
    unsupported = [skill for skill in required if skill not in supported and skill not in weak]
    constraint_match = clamp(1.0 - len(unsupported) / max(1, len(required))) if required else 0.5

    negatives: list[str] = []
    text = str(fingerprint.get("career_evidence_text") or "").lower()
    if constraints.get("production_heavy") and production == 0:
        negatives.append("no_production_evidence")
    if constraints.get("retrieval_heavy") and retrieval == 0:
        negatives.append("no_retrieval_or_ranking_evidence")
    if constraints.get("evaluation_heavy") and evaluation == 0:
        negatives.append("no_evaluation_evidence")
    if unsupported:
        negatives.append("missing_must_have_skill")
    if float(fingerprint.get("keyword_density_score", 0.0)) >= 0.12 and proof_alignment < 0.20:
        negatives.append("keyword_only_without_evidence")
    if "research" in text and production == 0:
        negatives.append("research_only_without_production")
    if "service_only_profile" in (risk_report or {}).get("risk_flags", []):
        negatives.append("service_only_without_ai_depth")

    negative_penalty = min(max_penalty, sum(negative_weights.get(flag, 0.0) for flag in set(negatives)))
    evidence_depth = clamp(0.35 * career_depth + 0.25 * production + 0.20 * retrieval + 0.20 * evaluation)
    evidence_confidence = clamp(0.55 * proof_alignment + 0.25 * consistency + 0.20 * evidence_depth)
    risk_score = float((risk_report or {}).get("risk_score", 0.0))
    technical_readiness = clamp(
        0.30 * proof_alignment
        + 0.20 * constraint_match
        + 0.20 * production
        + 0.18 * retrieval
        + 0.12 * evaluation
    )
    top10_readiness = clamp(technical_readiness * (1.0 - 0.65 * risk_score))
    hireability_score = float(hireability.get("hireability_score", 0.5))
    combined = clamp(
        weights["evidence_confidence"] * evidence_confidence
        + weights["career_depth"] * career_depth
        + weights["jd_constraint_match"] * constraint_match
        + weights["hireability"] * hireability_score
        + weights["top10_readiness"] * top10_readiness
    )
    # Hireability can influence only a small share; technical weakness caps the bonus.
    technical_cap = clamp(0.5 * proof_alignment + 0.5 * constraint_match)
    calibration_bonus = min(max_bonus, max(0.0, combined - 0.50) * 0.16 * technical_cap)
    calibration_penalty = min(max_penalty, negative_penalty + max(0.0, 0.25 - evidence_confidence) * 0.20)
    notes = []
    if calibration_bonus:
        notes.append("Supported career evidence adds a modest calibration bonus.")
    if negatives:
        notes.append(f"Negative constraints: {', '.join(sorted(set(negatives)))}.")
    if top10_readiness < float(config.get("top10_strictness", 0.75)):
        notes.append("Profile does not meet strict top-10 readiness.")

    return {
        "candidate_id": str(fingerprint.get("candidate_id") or ""),
        "evidence_confidence_score": round(evidence_confidence, 4),
        "evidence_depth_score": round(evidence_depth, 4),
        "evidence_consistency_score": round(consistency, 4),
        "jd_constraint_match_score": round(constraint_match, 4),
        "negative_constraint_penalty": round(negative_penalty, 4),
        "negative_constraints_triggered": sorted(set(negatives)),
        "calibrated_hireability_score": round(hireability_score, 4),
        "top10_readiness_score": round(top10_readiness, 4),
        "calibration_bonus": round(calibration_bonus, 4),
        "calibration_penalty": round(calibration_penalty, 4),
        "calibration_notes": notes,
    }
