from __future__ import annotations

from functools import lru_cache
from typing import Any

from .jd_parser import SKILL_DICTIONARY
from .text_normalizer import clean_text
from .utils import clamp, safe_float


DEFAULT_SCORE_WEIGHTS = {
    "jd_relevance": 0.25,
    "must_have_skill": 0.20,
    "proof_alignment": 0.25,
    "retrieval_evaluation_depth": 0.10,
    "production_readiness": 0.10,
    "hireability": 0.10,
}

DEFAULT_PENALTIES = {
    "empty_profile_text": 0.15,
    "extremely_high_keyword_density": 0.10,
    "missing_skills": 0.05,
    "missing_experience": 0.05,
}

STOPWORDS = {
    "and",
    "the",
    "with",
    "for",
    "from",
    "that",
    "this",
    "you",
    "your",
    "our",
    "are",
    "will",
    "have",
    "has",
    "into",
    "role",
    "work",
    "experience",
    "years",
}

NORMALIZED_SKILL_ALIASES = {
    skill: tuple(clean_text(alias) for alias in aliases)
    for skill, aliases in SKILL_DICTIONARY.items()
}


def _canonical_skill_matches_normalized(normalized_text: str) -> set[str]:
    padded = f" {normalized_text} "
    matches: set[str] = set()
    for skill, aliases in NORMALIZED_SKILL_ALIASES.items():
        if any(f" {alias} " in padded for alias in aliases):
            matches.add(skill)
    return matches


@lru_cache(maxsize=16)
def _jd_tokens(normalized_jd_text: str) -> frozenset[str]:
    return frozenset(
        token
        for token in normalized_jd_text.split()
        if len(token) > 2 and token not in STOPWORDS
    )


def _jd_relevance_score(
    jd_profile: dict[str, Any],
    candidate_normalized: str,
    candidate_skills: set[str],
) -> float:
    jd_tokens = {
        token for token in _jd_tokens(str(jd_profile.get("normalized_jd_text", "")))
    }
    candidate_tokens = set(candidate_normalized.split())
    if not jd_tokens:
        return 0.5
    overlap = len(jd_tokens & candidate_tokens) / len(jd_tokens)
    jd_skills = set(jd_profile.get("required_skills", [])) | set(
        jd_profile.get("preferred_skills", [])
    )
    skill_overlap = (
        len(jd_skills & candidate_skills) / len(jd_skills)
        if jd_skills
        else overlap
    )
    return clamp(0.55 * overlap + 0.45 * skill_overlap)


def _must_have_score(
    jd_profile: dict[str, Any],
    proof_graph: dict[str, Any],
    present: set[str],
) -> tuple[float, list[str], list[str]]:
    required = list(jd_profile.get("required_skills", []))
    if not required:
        return 0.5, [], []
    supported = set(proof_graph.get("supported_skills", []))
    weak = set(proof_graph.get("weakly_supported_skills", []))
    matched: list[str] = []
    unsupported_required: list[str] = []
    total_credit = 0.0
    for skill in required:
        if skill in supported:
            total_credit += 1.0
            matched.append(skill)
        elif skill in weak or skill in present:
            total_credit += 0.55
            matched.append(skill)
            unsupported_required.append(skill)
        else:
            unsupported_required.append(skill)
    return clamp(total_credit / len(required)), matched, unsupported_required


def _hireability_score(fingerprint: dict[str, Any]) -> tuple[float, bool]:
    behavior = fingerprint.get("behavioral_signal_summary") or {}
    availability = fingerprint.get("availability_signal_summary") or {}
    if not behavior and not availability:
        return 0.5, True

    components: list[float] = []
    response_rate = safe_float(
        behavior.get("recruiter_response_rate", behavior.get("response_rate"))
        if isinstance(behavior, dict)
        else None
    )
    if response_rate is not None:
        components.append(clamp(response_rate))

    interview_rate = safe_float(
        behavior.get("interview_completion_rate") if isinstance(behavior, dict) else None
    )
    if interview_rate is not None:
        components.append(clamp(interview_rate))

    notice = safe_float(
        availability.get("notice_period_days", availability.get("notice_period"))
        if isinstance(availability, dict)
        else None
    )
    if notice is not None:
        components.append(clamp(1.0 - notice / 180.0))

    if isinstance(availability, dict):
        open_to_work = availability.get(
            "open_to_work_flag",
            availability.get("open_to_work"),
        )
        if isinstance(open_to_work, bool):
            components.append(1.0 if open_to_work else 0.35)
        relocation = availability.get("willing_to_relocate", availability.get("relocation"))
        if isinstance(relocation, bool):
            components.append(0.8 if relocation else 0.5)

    return (sum(components) / len(components), False) if components else (0.5, True)


def score_candidate(
    jd_profile: dict[str, Any],
    fingerprint: dict[str, Any],
    proof_graph: dict[str, Any],
    score_weights: dict[str, float] | None = None,
    penalties: dict[str, float] | None = None,
) -> dict[str, Any]:
    weights = {**DEFAULT_SCORE_WEIGHTS, **(score_weights or {})}
    penalty_config = {**DEFAULT_PENALTIES, **(penalties or {})}

    candidate_text = " ".join(
        (
            str(fingerprint.get("current_title") or ""),
            str(fingerprint.get("raw_text_compact") or ""),
            " ".join(str(value) for value in fingerprint.get("technical_terms", [])),
        )
    )
    candidate_normalized = clean_text(candidate_text)
    present_skills = _canonical_skill_matches_normalized(candidate_normalized)
    jd_relevance = _jd_relevance_score(
        jd_profile,
        candidate_normalized,
        present_skills,
    )
    must_have, matched_required, unsupported_required = _must_have_score(
        jd_profile,
        proof_graph,
        present_skills,
    )
    proof_alignment = float(proof_graph.get("proof_alignment_score", 0.0))
    retrieval = float(proof_graph.get("retrieval_ranking_evidence_score", 0.0))
    evaluation = float(proof_graph.get("evaluation_evidence_score", 0.0))
    retrieval_evaluation_depth = clamp(0.65 * retrieval + 0.35 * evaluation)
    production = float(proof_graph.get("production_evidence_score", 0.0))
    hireability, neutral_hireability = _hireability_score(fingerprint)

    anomaly_flags = set(fingerprint.get("anomaly_flags", []))
    penalty_score = sum(
        amount for flag, amount in penalty_config.items() if flag in anomaly_flags
    )
    weighted_score = (
        weights["jd_relevance"] * jd_relevance
        + weights["must_have_skill"] * must_have
        + weights["proof_alignment"] * proof_alignment
        + weights["retrieval_evaluation_depth"] * retrieval_evaluation_depth
        + weights["production_readiness"] * production
        + weights["hireability"] * hireability
    )
    final_score = clamp(weighted_score - penalty_score)

    return {
        "candidate_id": str(fingerprint.get("candidate_id") or ""),
        "final_score": round(final_score, 6),
        "jd_relevance_score": round(jd_relevance, 4),
        "must_have_skill_score": round(must_have, 4),
        "proof_alignment_score": round(proof_alignment, 4),
        "retrieval_ranking_evidence_score": round(retrieval, 4),
        "evaluation_evidence_score": round(evaluation, 4),
        "retrieval_evaluation_depth_score": round(retrieval_evaluation_depth, 4),
        "production_evidence_score": round(production, 4),
        "hireability_score": round(hireability, 4),
        "penalty_score": round(penalty_score, 4),
        "matched_required_skills": matched_required,
        "unsupported_required_skills": unsupported_required,
        "neutral_hireability_used": neutral_hireability,
        "strict_rerank_applied": False,
    }


def apply_strict_rerank(score: dict[str, Any], fingerprint: dict[str, Any]) -> dict[str, Any]:
    adjusted = dict(score)
    unsupported_count = len(score.get("unsupported_required_skills", []))
    strict_adjustment = (
        0.05 * float(score.get("proof_alignment_score", 0.0))
        + 0.035 * float(score.get("retrieval_ranking_evidence_score", 0.0))
        + 0.025 * float(score.get("evaluation_evidence_score", 0.0))
        + 0.03 * float(score.get("production_evidence_score", 0.0))
        - min(0.12, 0.025 * unsupported_count)
        - 0.08 * float(fingerprint.get("keyword_density_score", 0.0))
    )
    adjusted["final_score"] = round(
        clamp(float(score["final_score"]) + strict_adjustment),
        6,
    )
    adjusted["strict_rerank_applied"] = True
    adjusted["strict_adjustment"] = round(strict_adjustment, 6)
    return adjusted
