from __future__ import annotations

import re
from typing import Any, Iterable

from .text_normalizer import clean_text
from .utils import clamp, safe_float


EXPERIENCE_RE = re.compile(r"\b(\d{1,2}(?:\.\d+)?)\+?\s*(?:years?|yrs?)\b", re.I)
DATE_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
SENIORITY_ORDER = (
    "intern",
    "trainee",
    "junior",
    "associate",
    "engineer",
    "senior",
    "lead",
    "staff",
    "principal",
    "architect",
    "manager",
    "head",
    "director",
    "founder",
)
PRODUCTION_TERMS = (
    "production", "deployed", "deployment", "scalable", "latency", "monitoring",
    "api", "backend", "cloud", "aws", "docker", "kubernetes", "ci/cd", "users",
    "live", "rollout", "pipeline",
)
RETRIEVAL_TERMS = (
    "retrieval", "search", "ranking", "recommender", "recommendation", "vector",
    "embedding", "embeddings", "semantic search", "vector database", "rag",
    "retriever", "candidate ranking", "information retrieval",
)
EVALUATION_TERMS = (
    "ndcg", "mrr", "map", "a/b testing", "experiment", "metrics", "precision",
    "recall", "f1", "offline evaluation", "online evaluation", "benchmark",
    "evaluation pipeline",
)
LEADERSHIP_TERMS = (
    "led", "owned", "shipped", "designed", "architected", "mentored", "product",
    "customer", "users", "roadmap", "stakeholder",
)
PROJECT_TERMS = ("project", "built", "implemented", "developed", "launched", "delivered")
COMPANY_RE = re.compile(
    r"\b(?:at|@|with)\s+([A-Z][A-Za-z0-9&.\- ]{1,40}?)(?=\s+(?:as|where|from|for|and)|[,.]|$)"
)
TITLE_RE = re.compile(
    r"\b(?:intern|trainee|junior|associate|senior|lead|staff|principal|architect|"
    r"manager|head|director|founder)?\s*(?:ai|ml|machine learning|data|software|"
    r"backend|search|ranking|nlp|research)?\s*(?:engineer|scientist|architect|"
    r"manager|developer|researcher)\b",
    re.I,
)
NORMALIZED_TERM_GROUPS = {
    "seniority": tuple(clean_text(term) for term in SENIORITY_ORDER),
    "production": tuple(clean_text(term) for term in PRODUCTION_TERMS),
    "retrieval": tuple(clean_text(term) for term in RETRIEVAL_TERMS),
    "evaluation": tuple(clean_text(term) for term in EVALUATION_TERMS),
    "leadership": tuple(clean_text(term) for term in LEADERSHIP_TERMS),
    "projects": tuple(clean_text(term) for term in PROJECT_TERMS),
}


def _found_normalized(normalized_text: str, terms: Iterable[str]) -> list[str]:
    padded = f" {normalized_text} "
    return [term for term in terms if f" {term} " in padded]


def _depth(found: list[str], target: int) -> float:
    return clamp(len(set(found)) / max(1, target))


def build_career_evidence_profile(fingerprint: dict[str, Any]) -> dict[str, Any]:
    candidate_id = str(fingerprint.get("candidate_id") or "")
    title = str(fingerprint.get("current_title") or "")
    career = str(fingerprint.get("career_evidence_text") or "")
    raw = str(fingerprint.get("raw_text_compact") or "")
    text = f"{title} {career}"
    normalized = clean_text(text)

    parsed_titles = list(dict.fromkeys(match.group(0).strip() for match in TITLE_RE.finditer(text)))
    if title and title not in parsed_titles:
        parsed_titles.insert(0, title)
    title_normalized = clean_text(title)
    seniority_found = _found_normalized(
        title_normalized,
        NORMALIZED_TERM_GROUPS["seniority"],
    )
    seniority_level = max(
        seniority_found,
        key=lambda value: SENIORITY_ORDER.index(value),
        default="unknown",
    )
    years = [float(value) for value in EXPERIENCE_RE.findall(f"{text} {raw}")]
    structured_years = safe_float(fingerprint.get("years_of_experience"))
    if structured_years is not None:
        years.insert(0, structured_years)
    calendar_years = sorted({int(value) for value in DATE_YEAR_RE.findall(text)})
    parsed_companies = (
        list(dict.fromkeys(match.group(1).strip() for match in COMPANY_RE.finditer(text)))
        if " at " in f" {text.lower()} " or " with " in f" {text.lower()} "
        else []
    )

    production = _found_normalized(normalized, NORMALIZED_TERM_GROUPS["production"])
    retrieval = _found_normalized(normalized, NORMALIZED_TERM_GROUPS["retrieval"])
    evaluation = _found_normalized(normalized, NORMALIZED_TERM_GROUPS["evaluation"])
    leadership = _found_normalized(normalized, NORMALIZED_TERM_GROUPS["leadership"])
    projects = _found_normalized(normalized, NORMALIZED_TERM_GROUPS["projects"])

    career_tokens = len(normalized.split())
    career_depth = clamp(
        0.35 * min(career_tokens / 160.0, 1.0)
        + 0.20 * min(len(parsed_titles) / 3.0, 1.0)
        + 0.15 * min(len(years) / 2.0, 1.0)
        + 0.15 * _depth(projects, 4)
        + 0.15 * _depth(leadership, 4)
    )
    consistency = 0.5
    if structured_years is not None:
        consistency += 0.2
    if calendar_years:
        consistency += 0.15
        visible_span = max(calendar_years) - min(calendar_years)
        if structured_years is not None and structured_years > visible_span + 7:
            consistency -= 0.35
    if seniority_level in {"senior", "lead", "staff", "principal", "architect", "manager", "head", "director"}:
        if structured_years is not None and structured_years < 2:
            consistency -= 0.35
    consistency = clamp(consistency)

    notes: list[str] = []
    if production:
        notes.append(f"Production evidence: {', '.join(production[:5])}.")
    if retrieval:
        notes.append(f"Retrieval/ranking evidence: {', '.join(retrieval[:5])}.")
    if evaluation:
        notes.append(f"Evaluation evidence: {', '.join(evaluation[:5])}.")
    if leadership:
        notes.append(f"Ownership evidence: {', '.join(leadership[:4])}.")
    if not notes:
        notes.append("Limited structured career evidence was detected.")

    return {
        "candidate_id": candidate_id,
        "parsed_titles": parsed_titles,
        "seniority_level": seniority_level,
        "parsed_companies": parsed_companies,
        "parsed_years_of_experience": years,
        "explicit_duration_mentions": EXPERIENCE_RE.findall(f"{text} {raw}"),
        "calendar_years": calendar_years,
        "production_terms_found": production,
        "retrieval_ranking_terms_found": retrieval,
        "evaluation_terms_found": evaluation,
        "leadership_terms_found": leadership,
        "project_terms_found": projects,
        "career_depth_score": round(career_depth, 4),
        "production_depth_score": round(_depth(production, 6), 4),
        "evaluation_depth_score": round(_depth(evaluation, 4), 4),
        "retrieval_depth_score": round(_depth(retrieval, 5), 4),
        "leadership_depth_score": round(_depth(leadership, 5), 4),
        "career_consistency_score": round(consistency, 4),
        "career_evidence_notes": notes,
    }
