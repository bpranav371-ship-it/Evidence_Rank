from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .text_normalizer import clean_text


SKILL_DICTIONARY: dict[str, tuple[str, ...]] = {
    "Python": ("python",),
    "Machine Learning": ("machine learning", "ml"),
    "Deep Learning": ("deep learning",),
    "NLP": ("nlp", "natural language processing"),
    "LLM": ("llm", "llms", "large language model", "large language models"),
    "RAG": ("rag", "retrieval augmented generation"),
    "Embeddings": ("embedding", "embeddings", "sentence transformer"),
    "Vector Database": (
        "vector database",
        "vector databases",
        "vector db",
        "pinecone",
        "weaviate",
        "qdrant",
        "milvus",
        "faiss",
    ),
    "Retrieval": (
        "retrieval",
        "retriever",
        "semantic search",
        "dense retrieval",
        "hybrid retrieval",
    ),
    "Search": ("search", "search relevance", "search engine"),
    "Ranking": ("ranking", "ranker", "learning to rank", "ltr"),
    "Recommendation Systems": (
        "recommendation system",
        "recommendation systems",
        "recommender",
        "recommenders",
        "personalization",
    ),
    "Information Retrieval": ("information retrieval", "ir system", "ir systems"),
    "NDCG": ("ndcg",),
    "MRR": ("mrr", "mean reciprocal rank"),
    "MAP": ("mean average precision", "map@", "map"),
    "A/B Testing": ("a/b testing", "a/b test", "ab testing", "online experiment"),
    "Evaluation": (
        "evaluation",
        "offline evaluation",
        "ranking metrics",
        "precision",
        "recall",
    ),
    "Fine-tuning": ("fine tuning", "fine-tuning", "lora", "qlora", "peft"),
    "Transformers": ("transformer", "transformers", "hugging face"),
    "PyTorch": ("pytorch",),
    "TensorFlow": ("tensorflow",),
    "Scikit-learn": ("scikit learn", "scikit-learn", "sklearn"),
    "SQL": ("sql",),
    "FastAPI": ("fastapi",),
    "APIs": ("api", "apis", "rest api", "rest APIs"),
    "Backend": ("backend", "back end"),
    "AWS": ("aws", "amazon web services"),
    "Docker": ("docker",),
    "Kubernetes": ("kubernetes", "k8s"),
    "MLOps": ("mlops", "ml ops", "model serving", "model registry"),
    "CI/CD": ("ci/cd", "continuous integration", "continuous deployment"),
    "Data Pipelines": ("data pipeline", "data pipelines", "etl", "airflow", "spark"),
    "Production ML": (
        "production ml",
        "production machine learning",
        "deployed model",
        "model deployment",
        "model serving",
    ),
    "Monitoring": ("monitoring", "observability", "model drift", "data drift"),
    "Experimentation": ("experimentation", "experiment design", "experiments"),
}

SENIORITY_KEYWORDS = (
    "senior",
    "staff",
    "lead",
    "principal",
    "founding",
    "architect",
    "manager",
)

DOMAIN_KEYWORDS = (
    "ai",
    "machine learning",
    "data",
    "software",
    "search",
    "ranking",
    "recommendation",
    "recruiting",
    "talent",
    "hr tech",
    "marketplace",
    "fintech",
    "ecommerce",
)

EVALUATION_SKILLS = {"NDCG", "MRR", "MAP", "A/B Testing", "Evaluation", "Experimentation"}
PRODUCTION_SKILLS = {
    "Production ML",
    "Monitoring",
    "APIs",
    "FastAPI",
    "Backend",
    "AWS",
    "Docker",
    "Kubernetes",
    "MLOps",
    "CI/CD",
    "Data Pipelines",
}
RETRIEVAL_RANKING_SKILLS = {
    "RAG",
    "Embeddings",
    "Vector Database",
    "Retrieval",
    "Search",
    "Ranking",
    "Recommendation Systems",
    "Information Retrieval",
}

PREFERRED_MARKERS = (
    "preferred",
    "nice to have",
    "good to have",
    "bonus",
    "would like",
    "like you to have",
    "won't reject",
    "will not reject",
    "desirable",
    "optional",
)

REQUIRED_MARKERS = (
    "required",
    "must have",
    "must-have",
    "absolutely need",
    "essential",
    "minimum qualification",
)

LOCATION_NAMES = (
    "pune",
    "noida",
    "delhi",
    "gurgaon",
    "gurugram",
    "mumbai",
    "hyderabad",
    "bangalore",
    "bengaluru",
    "chennai",
    "india",
    "remote",
    "hybrid",
    "onsite",
)


def _contains_alias(text: str, alias: str) -> bool:
    normalized_alias = clean_text(alias)
    if not normalized_alias:
        return False
    return re.search(rf"(?<!\w){re.escape(normalized_alias)}(?!\w)", text) is not None


def _extract_skills(normalized_text: str) -> list[str]:
    return [
        skill
        for skill, aliases in SKILL_DICTIONARY.items()
        if any(_contains_alias(normalized_text, alias) for alias in aliases)
    ]


def _classify_skills(raw_text: str, skills: list[str]) -> tuple[list[str], list[str]]:
    segments = [
        clean_text(segment)
        for segment in re.split(r"[\r\n.!?;]+", raw_text)
        if clean_text(segment)
    ]
    required: list[str] = []
    preferred: list[str] = []
    for skill in skills:
        aliases = SKILL_DICTIONARY[skill]
        matching_segments = [
            segment
            for segment in segments
            if any(_contains_alias(segment, alias) for alias in aliases)
        ]
        if matching_segments and all(
            any(marker in segment for marker in PREFERRED_MARKERS)
            for segment in matching_segments
        ):
            preferred.append(skill)
        else:
            required.append(skill)
    return required, preferred


def _extract_experience_requirements(text: str) -> list[dict[str, Any]]:
    patterns = (
        re.compile(r"\b(\d{1,2})\s*(?:-|–|to)\s*(\d{1,2})\+?\s*years?\b", re.I),
        re.compile(r"\b(?:at least|min(?:imum)?(?: of)?)\s*(\d{1,2})\+?\s*years?\b", re.I),
        re.compile(r"\b(\d{1,2})\+\s*years?\b", re.I),
    )
    requirements: list[dict[str, Any]] = []
    seen: set[tuple[int, int | None]] = set()
    for pattern in patterns:
        for match in pattern.finditer(text):
            minimum = int(match.group(1))
            maximum = int(match.group(2)) if match.lastindex and match.lastindex >= 2 else None
            key = (minimum, maximum)
            if key not in seen:
                seen.add(key)
                requirements.append(
                    {
                        "minimum_years": minimum,
                        "maximum_years": maximum,
                        "matched_text": match.group(0),
                    }
                )
    return requirements


def parse_jd_text(raw_text: str) -> dict[str, Any]:
    raw_text = raw_text or ""
    normalized = clean_text(raw_text)
    skills = _extract_skills(normalized)
    required_skills, preferred_skills = _classify_skills(raw_text, skills)
    seniority = [keyword for keyword in SENIORITY_KEYWORDS if _contains_alias(normalized, keyword)]
    domains = [keyword for keyword in DOMAIN_KEYWORDS if _contains_alias(normalized, keyword)]
    locations = [name for name in LOCATION_NAMES if _contains_alias(normalized, name)]

    return {
        "raw_jd_text": raw_text,
        "normalized_jd_text": normalized,
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
        "seniority_keywords": seniority,
        "domain_keywords": domains,
        "evaluation_keywords": [skill for skill in skills if skill in EVALUATION_SKILLS],
        "production_keywords": [skill for skill in skills if skill in PRODUCTION_SKILLS],
        "retrieval_ranking_keywords": [
            skill for skill in skills if skill in RETRIEVAL_RANKING_SKILLS
        ],
        "experience_requirements": _extract_experience_requirements(raw_text),
        "location_requirements": locations,
    }


def parse_jd_file(path: Path | str) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Job description file not found: {source}")
    return parse_jd_text(source.read_text(encoding="utf-8-sig"))
