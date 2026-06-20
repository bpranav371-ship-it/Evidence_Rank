from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from .text_normalizer import clean_text, flatten_value, tokenize_simple
from .utils import clamp, safe_float, safe_list


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "candidate_id": ("candidate_id", "candidateid", "profile_id", "user_id", "id"),
    "profile": ("profile", "candidate_profile", "personal_details"),
    "summary": ("summary", "profile_summary", "about", "bio", "description"),
    "headline": ("headline", "profile_headline", "professional_headline"),
    "current_title": ("current_title", "current_role", "job_title", "designation", "title"),
    "years_of_experience": (
        "years_of_experience",
        "experience_years",
        "total_experience",
        "years_experience",
    ),
    "location": ("location", "current_location", "city", "address"),
    "skills": ("skills", "skill_set", "technical_skills", "competencies"),
    "career_history": (
        "career_history",
        "work_experience",
        "experience_history",
        "employment_history",
        "work_history",
    ),
    "projects": ("projects", "project_history", "portfolio", "achievements"),
    "education": ("education", "education_history", "qualifications"),
}

BEHAVIOR_ALIASES = (
    "recruiter_response_rate",
    "response_rate",
    "avg_response_time_hours",
    "last_active_date",
    "last_activity",
    "profile_views_received_30d",
    "profile_views",
    "saved_by_recruiters_30d",
    "saved_by_recruiters",
    "interview_completion_rate",
    "applications_submitted_30d",
    "skill_assessment_scores",
    "assessment_scores",
    "endorsements_received",
)

AVAILABILITY_ALIASES = (
    "notice_period_days",
    "notice_period",
    "notice_days",
    "willing_to_relocate",
    "relocation",
    "open_to_work_flag",
    "open_to_work",
    "available_for_work",
    "preferred_work_mode",
    "work_mode",
    "employment_status",
)

TECHNICAL_TERM_ALIASES: dict[str, tuple[str, ...]] = {
    "Python": ("python",),
    "Machine Learning": ("machine learning", "ml"),
    "Artificial Intelligence": ("artificial intelligence", "ai"),
    "LLM": ("llm", "llms", "large language model", "large language models"),
    "RAG": ("rag", "retrieval augmented generation"),
    "Embeddings": ("embedding", "embeddings"),
    "Retrieval": ("retrieval", "search relevance", "semantic search", "vector search"),
    "Ranking": ("ranking", "ranker", "learning to rank", "ltr"),
    "Recommendation Systems": ("recommender", "recommendation system", "recommendation systems"),
    "NLP": ("nlp", "natural language processing"),
    "TensorFlow": ("tensorflow",),
    "PyTorch": ("pytorch",),
    "scikit-learn": ("scikit-learn", "sklearn"),
    "SQL": ("sql",),
    "AWS": ("aws",),
    "GCP": ("gcp", "google cloud"),
    "Azure": ("azure",),
    "Docker": ("docker",),
    "Kubernetes": ("kubernetes", "k8s"),
    "APIs": ("api", "apis", "rest api", "rest apis", "graphql"),
    "Backend": ("backend",),
    "Frontend": ("frontend",),
    "React": ("react", "react.js", "reactjs"),
    "Java": ("java",),
    "C++": ("c++",),
    "Spark": ("spark", "apache spark"),
    "Kafka": ("kafka",),
    "Airflow": ("airflow",),
    "Elasticsearch": ("elasticsearch",),
    "FAISS": ("faiss",),
    "Pinecone": ("pinecone",),
    "Qdrant": ("qdrant",),
    "Milvus": ("milvus",),
    "LangChain": ("langchain",),
}


def _normalized_key(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _walk_items(value: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key), child
            yield from _walk_items(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_items(child)


def _build_field_index(record: dict[str, Any]) -> dict[str, list[tuple[str, Any]]]:
    index: dict[str, list[tuple[str, Any]]] = {}
    for key, value in _walk_items(record):
        index.setdefault(_normalized_key(key), []).append((key, value))
    return index


def _find_first(
    record: dict[str, Any],
    aliases: Iterable[str],
    index: dict[str, list[tuple[str, Any]]] | None = None,
) -> Any:
    targets = list(dict.fromkeys(_normalized_key(alias) for alias in aliases))
    if index is not None:
        for target in targets:
            for _, value in index.get(target, []):
                if value not in (None, "", [], {}):
                    return value
    else:
        for key, value in _walk_items(record):
            if _normalized_key(key) in targets and value not in (None, "", [], {}):
                return value
    return None


def _find_all(
    record: dict[str, Any],
    aliases: Iterable[str],
    index: dict[str, list[tuple[str, Any]]] | None = None,
) -> list[tuple[str, Any]]:
    targets = list(dict.fromkeys(_normalized_key(alias) for alias in aliases))
    found: list[tuple[str, Any]] = []
    if index is not None:
        for target in targets:
            found.extend(
                (key, value)
                for key, value in index.get(target, [])
                if value not in (None, "", [], {})
            )
    else:
        for key, value in _walk_items(record):
            if _normalized_key(key) in targets and value not in (None, "", [], {}):
                found.append((key, value))
    return found


def _value_at_path(record: dict[str, Any], path: str) -> Any:
    current: Any = record
    for part in path.split("."):
        if isinstance(current, list):
            return None
        if not isinstance(current, dict):
            return None
        target = _normalized_key(part)
        matched_key = next(
            (key for key in current if _normalized_key(str(key)) == target),
            None,
        )
        if matched_key is None:
            return None
        current = current[matched_key]
    return current


def _extract_skill_names(value: Any) -> list[str]:
    skills: list[str] = []
    for item in safe_list(value):
        if isinstance(item, dict):
            name = _find_first(item, ("name", "skill", "skill_name", "technology"))
            if name is not None:
                skills.append(str(name))
        elif item is not None:
            if isinstance(item, str) and any(separator in item for separator in (",", ";", "|")):
                skills.extend(re.split(r"[,;|]", item))
            else:
                skills.append(str(item))

    unique: list[str] = []
    seen: set[str] = set()
    for skill in skills:
        normalized = clean_text(skill)
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(skill.strip())
    return unique


def _technical_analysis(text: str) -> tuple[list[str], float]:
    normalized_text = clean_text(text)
    tokens = tokenize_simple(normalized_text)
    if not tokens:
        return [], 0.0
    padded = f" {normalized_text} "
    terms: list[str] = []
    occurrence_count = 0
    for name, aliases in TECHNICAL_TERM_ALIASES.items():
        alias_counts = [padded.count(f" {alias} ") for alias in aliases]
        total = sum(alias_counts)
        if total:
            terms.append(name)
            occurrence_count += total
    return terms, clamp(occurrence_count / len(tokens))


def _summarize_fields(
    record: dict[str, Any],
    aliases: Iterable[str],
    index: dict[str, list[tuple[str, Any]]] | None = None,
) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key, value in _find_all(record, aliases, index=index):
        normalized_key = clean_text(key).replace(" ", "_")
        if normalized_key in summary:
            continue
        if isinstance(value, (dict, list)):
            compact = flatten_value(value)
            summary[normalized_key] = compact[:500]
        else:
            summary[normalized_key] = value
    return summary


def _has_value(value: Any) -> bool:
    return value not in (None, "", [], {})


def _skill_evidence_score(claimed_skills: list[str], career_text: str) -> float:
    if not claimed_skills or not career_text:
        return 0.0
    normalized_career = f" {clean_text(career_text)} "
    career_tokens = set(tokenize_simple(normalized_career))
    supported = 0
    for skill in claimed_skills:
        normalized_skill = clean_text(skill)
        if not normalized_skill:
            continue
        phrase_match = f" {normalized_skill} " in normalized_career
        tokens = [token for token in tokenize_simple(normalized_skill) if len(token) > 1]
        token_match = bool(tokens) and all(token in career_tokens for token in tokens)
        if phrase_match or token_match:
            supported += 1
    return clamp(supported / max(1, len(claimed_skills)))


@dataclass(frozen=True)
class CandidateProfilerConfig:
    max_text_length_per_candidate: int = 12000


class CandidateProfiler:
    def __init__(
        self,
        config: CandidateProfilerConfig | None = None,
        schema_report: dict[str, Any] | None = None,
    ) -> None:
        self.config = config or CandidateProfilerConfig()
        self.schema_paths: dict[str, list[str]] = (
            schema_report.get("likely_fields", {}) if schema_report else {}
        )

    def _field(
        self,
        record: dict[str, Any],
        category: str,
        index: dict[str, list[tuple[str, Any]]],
    ) -> Any:
        schema_category = {"summary": "profile_summary"}.get(category, category)
        scalar_categories = {
            "candidate_id",
            "summary",
            "headline",
            "current_title",
            "years_of_experience",
            "location",
        }
        for path in self.schema_paths.get(schema_category, []):
            value = _value_at_path(record, path)
            if category in scalar_categories and isinstance(value, (dict, list)):
                continue
            if _has_value(value):
                return value
        return _find_first(record, FIELD_ALIASES[category], index=index)

    def profile(self, record: dict[str, Any], row_number: int) -> dict[str, Any]:
        field_index = _build_field_index(record)
        candidate_id_value = self._field(record, "candidate_id", field_index)
        missing_candidate_id = not _has_value(candidate_id_value)
        candidate_id = (
            str(candidate_id_value).strip()
            if not missing_candidate_id
            else f"GENERATED_{row_number:09d}"
        )

        summary = self._field(record, "summary", field_index)
        headline = self._field(record, "headline", field_index)
        current_title = self._field(record, "current_title", field_index)
        years_value = self._field(record, "years_of_experience", field_index)
        location = self._field(record, "location", field_index)
        skills_value = self._field(record, "skills", field_index)
        career_value = self._field(record, "career_history", field_index)
        projects_value = self._field(record, "projects", field_index)
        education_value = self._field(record, "education", field_index)

        career_evidence_text = " ".join(
            part for part in (flatten_value(career_value), flatten_value(projects_value)) if part
        )
        education_text = flatten_value(education_value)
        explicit_skills = _extract_skill_names(skills_value)
        raw_text_compact = " ".join(
            part
            for part in (
                flatten_value(headline),
                flatten_value(summary),
                flatten_value(current_title),
                flatten_value(skills_value),
                career_evidence_text,
                education_text,
            )
            if part
        )[: self.config.max_text_length_per_candidate]
        technical_terms, density = _technical_analysis(raw_text_compact)
        claimed_skills = list(explicit_skills)
        claimed_normalized = {clean_text(skill) for skill in claimed_skills}
        for term in technical_terms:
            if clean_text(term) not in claimed_normalized:
                claimed_skills.append(term)
                claimed_normalized.add(clean_text(term))

        behavioral_summary = _summarize_fields(record, BEHAVIOR_ALIASES, index=field_index)
        availability_summary = _summarize_fields(record, AVAILABILITY_ALIASES, index=field_index)
        has_availability_signal = bool(availability_summary)
        if _has_value(location):
            availability_summary.setdefault("location", location)

        important_values = {
            "candidate_id": candidate_id_value,
            "profile_summary": summary or headline,
            "current_title": current_title,
            "skills": skills_value,
            "career_history": career_value,
            "education": education_value,
            "years_of_experience": years_value,
            "location": location,
            "behavioral_signals": behavioral_summary,
            "availability_signals": has_availability_signal,
        }
        missing_fields = [key for key, value in important_values.items() if not _has_value(value)]
        completeness = clamp(
            sum(1 for value in important_values.values() if _has_value(value))
            / len(important_values)
        )
        evidence_hint = _skill_evidence_score(claimed_skills, career_evidence_text)

        anomaly_flags: list[str] = []
        if missing_candidate_id:
            anomaly_flags.append("missing_candidate_id")
        if not raw_text_compact:
            anomaly_flags.append("empty_profile_text")
        if density >= 0.25 and len(tokenize_simple(raw_text_compact)) >= 20:
            anomaly_flags.append("extremely_high_keyword_density")
        if not explicit_skills:
            anomaly_flags.append("missing_skills")
        if not _has_value(years_value) and not career_evidence_text:
            anomaly_flags.append("missing_experience")

        return {
            "candidate_id": candidate_id,
            "raw_text_compact": raw_text_compact,
            "claimed_skills": claimed_skills,
            "technical_terms": technical_terms,
            "current_title": "" if current_title is None else str(current_title),
            "years_of_experience": safe_float(years_value),
            "location": "" if location is None else flatten_value(location),
            "career_evidence_text": career_evidence_text,
            "education_text": education_text,
            "behavioral_signal_summary": behavioral_summary,
            "availability_signal_summary": availability_summary,
            "anomaly_flags": anomaly_flags,
            "missing_fields": missing_fields,
            "profile_completeness_score": round(completeness, 4),
            "keyword_density_score": round(density, 4),
            "skill_evidence_hint_score": round(evidence_hint, 4),
        }
