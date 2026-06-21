from __future__ import annotations

from typing import Any

from .text_normalizer import clean_text


ARCHETYPE_TERMS = {
    "retrieval_ranking_engineer": ("retrieval", "ranking", "recommendation", "ndcg", "mrr", "map"),
    "ai_engineer": ("ai engineer", "llm", "rag", "embeddings"),
    "ml_engineer": ("machine learning", "ml engineer", "mlops", "model deployment"),
    "data_scientist": ("data scientist", "statistics", "analytics"),
    "backend_engineer": ("backend", "api", "distributed systems"),
    "research_scientist": ("research scientist", "papers", "research lab"),
    "product_engineer": ("product engineer", "shipped", "users", "customer"),
}
CORE_HARD_SKILLS = {
    "Python",
    "Embeddings",
    "Vector Database",
    "Retrieval",
    "Ranking",
    "Evaluation",
}


def _contains(text: str, term: str) -> bool:
    return f" {clean_text(term)} " in f" {text} "


def build_jd_constraint_profile(jd_profile: dict[str, Any]) -> dict[str, Any]:
    text = clean_text(jd_profile.get("normalized_jd_text", ""))
    detected_required = list(jd_profile.get("required_skills") or [])
    detected_preferred = list(jd_profile.get("preferred_skills") or [])
    required = [skill for skill in detected_required if skill in CORE_HARD_SKILLS]
    if not required:
        required = detected_required[:6]
    preferred = list(
        dict.fromkeys(
            detected_preferred
            + [skill for skill in detected_required if skill not in required]
        )
    )
    scores = {
        archetype: sum(_contains(text, term) for term in terms)
        for archetype, terms in ARCHETYPE_TERMS.items()
    }
    role_archetype = max(scores, key=scores.get) if text and max(scores.values(), default=0) else "unknown"
    production_heavy = any(
        _contains(text, term)
        for term in ("production", "deployed", "ship", "users", "api", "backend", "monitoring")
    )
    retrieval_heavy = any(
        _contains(text, term)
        for term in ("retrieval", "ranking", "recommendation", "search", "embeddings")
    )
    evaluation_heavy = any(
        _contains(text, term)
        for term in ("ndcg", "mrr", "map", "a/b testing", "evaluation")
    )
    negatives = [
        "keyword_only_without_evidence",
        "missing_must_have_skill",
    ]
    if production_heavy:
        negatives.extend(("research_only_without_production", "no_production_evidence"))
    if retrieval_heavy:
        negatives.extend(("shallow_project_evidence", "no_retrieval_or_ranking_evidence"))
    if evaluation_heavy:
        negatives.append("no_evaluation_evidence")
    priorities = {
        "proof_alignment": 0.25,
        "production": 0.20 if production_heavy else 0.10,
        "retrieval_ranking": 0.25 if retrieval_heavy else 0.10,
        "evaluation": 0.20 if evaluation_heavy else 0.10,
        "hireability": 0.10,
    }
    top10_terms = list(
        dict.fromkeys(
            list(jd_profile.get("retrieval_ranking_keywords") or [])
            + list(jd_profile.get("evaluation_keywords") or [])
            + list(jd_profile.get("production_keywords") or [])
        )
    )
    return {
        "required_positive_skills": required,
        "preferred_positive_skills": preferred,
        "hard_constraints": required,
        "soft_constraints": preferred,
        "negative_constraints": list(dict.fromkeys(negatives)),
        "role_archetype": role_archetype,
        "priority_weights": priorities,
        "top10_priority_terms": top10_terms,
        "disqualifier_terms": [
            term
            for term in ("pure research", "research only", "consulting only", "demo only")
            if term in text
        ],
        "constraint_notes": [
            f"Detected role archetype: {role_archetype}.",
            f"Production-heavy requirement: {production_heavy}.",
            f"Retrieval/ranking-heavy requirement: {retrieval_heavy}.",
            f"Evaluation-heavy requirement: {evaluation_heavy}.",
        ],
        "production_heavy": production_heavy,
        "retrieval_heavy": retrieval_heavy,
        "evaluation_heavy": evaluation_heavy,
    }
