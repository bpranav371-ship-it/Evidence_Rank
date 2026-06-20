from __future__ import annotations

import re
from typing import Any, Iterable

from .jd_parser import (
    EVALUATION_SKILLS,
    PRODUCTION_SKILLS,
    RETRIEVAL_RANKING_SKILLS,
    SKILL_DICTIONARY,
)
from .text_normalizer import clean_text
from .utils import clamp


EVIDENCE_GROUPS: dict[str, tuple[str, ...]] = {
    **SKILL_DICTIONARY,
    "Deployment": ("deployed", "shipped", "production", "launched", "served"),
    "Scale": ("scale", "scaled", "users", "latency", "throughput"),
    "Metrics": ("metrics", "precision", "recall", "accuracy", "benchmark"),
}

NORMALIZED_EVIDENCE_ALIASES = {
    canonical: tuple(clean_text(alias) for alias in aliases)
    for canonical, aliases in EVIDENCE_GROUPS.items()
}
NORMALIZED_SKILL_LOOKUP = {
    clean_text(canonical): aliases
    for canonical, aliases in NORMALIZED_EVIDENCE_ALIASES.items()
}

AI_ML_DEPTH_TERMS = {
    "Machine Learning",
    "Deep Learning",
    "NLP",
    "LLM",
    "RAG",
    "Embeddings",
    "Fine-tuning",
    "Transformers",
    "PyTorch",
    "TensorFlow",
    "Scikit-learn",
    "MLOps",
    "Production ML",
}


def _aliases_for(skill: str) -> tuple[str, ...]:
    normalized = clean_text(skill)
    return NORMALIZED_SKILL_LOOKUP.get(normalized, (normalized,))


def _contains_normalized(padded_text: str, terms: Iterable[str]) -> bool:
    return any(f" {term} " in padded_text for term in terms if term)


def _sentences(text: str) -> list[str]:
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    if not compact:
        return []
    return [
        sentence.strip(" -;,.")
        for sentence in re.split(r"(?<=[.!?;])\s+|\s+\|\s+", compact)
        if sentence.strip()
    ]


def _sentence_pairs(texts: Iterable[str]) -> list[tuple[str, str]]:
    return [
        (sentence, f" {clean_text(sentence)} ")
        for text in texts
        for sentence in _sentences(text)
    ]


def _matching_snippets(
    sentence_pairs: Iterable[tuple[str, str]],
    aliases: Iterable[str],
    limit: int,
) -> list[str]:
    normalized_aliases = tuple(alias for alias in aliases if alias)
    snippets: list[str] = []
    seen: set[str] = set()
    for sentence, normalized in sentence_pairs:
        if not any(f" {alias} " in normalized for alias in normalized_aliases):
            continue
        snippet = sentence[:240].strip()
        key = normalized.strip()
        if snippet and key not in seen:
            snippets.append(snippet)
            seen.add(key)
            if len(snippets) >= limit:
                return snippets
    return snippets


def _contextual_raw_snippets(
    normalized: str,
    aliases: Iterable[str],
    limit: int,
) -> list[str]:
    action_terms = (
        "built",
        "developed",
        "deployed",
        "implemented",
        "designed",
        "created",
        "evaluated",
        "improved",
        "scaled",
        "owned",
        "worked",
        "experience",
    )
    snippets: list[str] = []
    for alias in aliases:
        if not alias:
            continue
        for match in re.finditer(rf"(?<!\w){re.escape(alias)}(?!\w)", normalized):
            window = normalized[max(0, match.start() - 110) : match.end() + 110].strip()
            if any(action in window for action in action_terms) and window not in snippets:
                snippets.append(window[:240])
                if len(snippets) >= limit:
                    return snippets
    return snippets


def _group_score(normalized_text: str, skills: set[str], group: set[str]) -> float:
    group_terms = set(group)
    mentioned_skills = len(skills & group_terms)
    padded_text = f" {normalized_text} "
    evidence_hits = sum(
        1
        for name in group_terms
        if _contains_normalized(
            padded_text,
            NORMALIZED_EVIDENCE_ALIASES.get(name, (clean_text(name),)),
        )
    )
    denominator = max(1, min(4, len(group_terms)))
    return clamp(max(mentioned_skills, evidence_hits) / denominator)


def build_proof_graph(
    fingerprint: dict[str, Any],
    max_evidence_snippets: int = 5,
) -> dict[str, Any]:
    claimed_skills = [str(skill) for skill in fingerprint.get("claimed_skills", []) if skill]
    technical_terms = {
        str(term) for term in fingerprint.get("technical_terms", []) if term
    }
    career_text = str(fingerprint.get("career_evidence_text") or "")
    title_text = str(fingerprint.get("current_title") or "")
    education_text = str(fingerprint.get("education_text") or "")
    raw_text = str(fingerprint.get("raw_text_compact") or "")

    career_normalized = clean_text(career_text)
    title_normalized = clean_text(title_text)
    education_normalized = clean_text(education_text)
    raw_normalized = clean_text(raw_text)
    strong_normalized = f"{title_normalized} {career_normalized}".strip()
    contextual_normalized = (
        f"{strong_normalized} {education_normalized} {raw_normalized}".strip()
    )
    strong_sentence_pairs = _sentence_pairs((career_text, title_text))
    education_sentence_pairs = _sentence_pairs((education_text,))
    supported: list[str] = []
    weakly_supported: list[str] = []
    unsupported: list[str] = []
    evidence_snippets: dict[str, list[str]] = {}

    for skill in claimed_skills:
        aliases = _aliases_for(skill)
        strong_snippets = _matching_snippets(
            strong_sentence_pairs,
            aliases,
            max_evidence_snippets,
        )
        weak_snippets = _matching_snippets(
            education_sentence_pairs,
            aliases,
            max_evidence_snippets,
        )
        if len(weak_snippets) < max_evidence_snippets:
            weak_snippets.extend(
                snippet
                for snippet in _contextual_raw_snippets(
                    raw_normalized,
                    aliases,
                    max_evidence_snippets - len(weak_snippets),
                )
                if snippet not in weak_snippets
            )
        if strong_snippets:
            supported.append(skill)
            evidence_snippets[skill] = strong_snippets
        elif weak_snippets:
            weakly_supported.append(skill)
            evidence_snippets[skill] = weak_snippets
        else:
            unsupported.append(skill)

    total_claims = len(claimed_skills)
    proof_alignment = (
        clamp((len(supported) + 0.4 * len(weakly_supported)) / total_claims)
        if total_claims
        else 0.0
    )
    known_skills = technical_terms | set(supported) | set(weakly_supported)
    retrieval_score = _group_score(
        strong_normalized,
        known_skills,
        RETRIEVAL_RANKING_SKILLS,
    )
    evaluation_score = _group_score(
        strong_normalized,
        known_skills,
        EVALUATION_SKILLS,
    )
    production_score = _group_score(
        strong_normalized,
        known_skills,
        PRODUCTION_SKILLS | {"Deployment", "Scale"},
    )
    ai_depth_score = _group_score(
        contextual_normalized,
        known_skills,
        AI_ML_DEPTH_TERMS,
    )

    top_supported = supported[:4]
    if top_supported:
        proof_summary = f"Career evidence supports: {', '.join(top_supported)}."
    elif weakly_supported:
        proof_summary = (
            "Skills appear in profile context but have limited career evidence: "
            f"{', '.join(weakly_supported[:4])}."
        )
    else:
        proof_summary = "No claimed technical skill has clear supporting profile evidence."
    if unsupported:
        proof_summary += f" Unsupported claims include: {', '.join(unsupported[:3])}."

    return {
        "candidate_id": str(fingerprint.get("candidate_id") or ""),
        "claimed_skills": claimed_skills,
        "supported_skills": supported,
        "weakly_supported_skills": weakly_supported,
        "unsupported_skills": unsupported,
        "evidence_snippets": evidence_snippets,
        "retrieval_ranking_evidence_score": round(retrieval_score, 4),
        "evaluation_evidence_score": round(evaluation_score, 4),
        "production_evidence_score": round(production_score, 4),
        "ai_ml_depth_score": round(ai_depth_score, 4),
        "proof_alignment_score": round(proof_alignment, 4),
        "proof_summary": proof_summary,
    }
