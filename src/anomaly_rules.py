from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

from .text_normalizer import clean_text, flatten_value, tokenize_simple
from .utils import safe_float


@dataclass(frozen=True)
class RuleFinding:
    flag: str
    severity: str
    weight: float
    note: str


SENIOR_TERMS = ("senior", "lead", "principal", "staff", "head", "director", "architect")
JUNIOR_TERMS = ("intern", "trainee", "junior", "associate", "fresher")
AI_TERMS = (
    "ai",
    "machine learning",
    "ml",
    "nlp",
    "llm",
    "rag",
    "retrieval",
    "ranking",
    "recommendation",
    "data scientist",
)
NON_TECHNICAL_TITLES = (
    "marketing",
    "hr manager",
    "human resources",
    "accountant",
    "sales",
    "content writer",
    "graphic designer",
    "operations manager",
    "customer support",
    "civil engineer",
    "mechanical engineer",
    "data entry",
)
RESEARCH_TERMS = ("research scientist", "researcher", "academic lab", "postdoctoral", "postdoc")
PRODUCTION_TERMS = (
    "production",
    "deployed",
    "shipped",
    "api",
    "monitoring",
    "latency",
    "scale",
    "users",
    "docker",
    "kubernetes",
    "aws",
)
RETRIEVAL_CLAIMS = (
    "rag",
    "retrieval",
    "ranking",
    "search",
    "recommendation systems",
    "embeddings",
    "vector database",
)
EVALUATION_CLAIMS = ("ndcg", "mrr", "map", "a/b testing", "evaluation", "experimentation")
PRODUCTION_CLAIMS = (
    "production ml",
    "mlops",
    "monitoring",
    "docker",
    "kubernetes",
    "aws",
    "apis",
)

EXPERIENCE_RANGE_RE = re.compile(
    r"\b(?P<minimum>\d{1,2})\s*(?:-|–|to)\s*(?P<maximum>\d{1,2})\+?\s*years?\b",
    re.I,
)
EXPERIENCE_SINGLE_RE = re.compile(
    r"\b(?P<years>\d{1,2}(?:\.\d+)?)\+?\s*years?(?:\s+of\s+experience)?\b",
    re.I,
)
DURATION_RE = re.compile(
    r"\b(?P<value>\d{1,3})\s*(?P<unit>months?|years?)\b",
    re.I,
)
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
ZERO_EXPERT_RE = re.compile(
    r"\b(?:expert|advanced|senior)\b.{0,45}\b(?:0|zero)\s*(?:months?|years?)\b"
    r"|\b(?:0|zero)\s*(?:months?|years?)\b.{0,45}\b(?:expert|advanced)\b",
    re.I,
)


def _finding(flag: str, severity: str, weight: float, note: str) -> RuleFinding:
    return RuleFinding(flag=flag, severity=severity, weight=weight, note=note)


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    padded = f" {clean_text(text)} "
    return any(f" {clean_text(term)} " in padded for term in terms)


def extract_experience_years(text: str) -> list[float]:
    values: list[float] = []
    for match in EXPERIENCE_RANGE_RE.finditer(text or ""):
        values.extend((float(match.group("minimum")), float(match.group("maximum"))))
    for match in EXPERIENCE_SINGLE_RE.finditer(text or ""):
        values.append(float(match.group("years")))
    return values


def extract_calendar_years(text: str) -> list[int]:
    return [int(value) for value in YEAR_RE.findall(text or "")]


def extract_durations(text: str) -> list[tuple[float, str]]:
    return [
        (float(match.group("value")), match.group("unit").lower())
        for match in DURATION_RE.finditer(text or "")
    ]


def extract_seniority_terms(text: str) -> list[str]:
    normalized = clean_text(text)
    return [term for term in (*JUNIOR_TERMS, *SENIOR_TERMS) if f" {term} " in f" {normalized} "]


def zero_duration_expert_rules(fingerprint: dict[str, Any]) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    raw = str(fingerprint.get("raw_text_compact") or "")
    skill_details = fingerprint.get("skill_details") or fingerprint.get("skills") or []
    zero_expert = False
    if isinstance(skill_details, list):
        for skill in skill_details:
            if not isinstance(skill, dict):
                continue
            proficiency = clean_text(skill.get("proficiency"))
            duration = safe_float(
                skill.get("duration_months", skill.get("months_of_experience"))
            )
            if proficiency in {"expert", "advanced"} and duration is not None and duration <= 1:
                zero_expert = True
                break
    if not zero_expert:
        zero_expert = bool(ZERO_EXPERT_RE.search(raw))

    if zero_expert:
        findings.append(
            _finding(
                "zero_duration_expert_claim",
                "severe",
                0.25,
                "An expert or advanced claim is paired with zero or near-zero stated duration.",
            )
        )
    return findings


def keyword_stuffing_rules(
    fingerprint: dict[str, Any],
    proof_graph: dict[str, Any] | None = None,
) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    proof_graph = proof_graph or {}
    density = safe_float(fingerprint.get("keyword_density_score"), 0.0) or 0.0
    claimed_count = len(fingerprint.get("claimed_skills") or [])
    technical_count = len(fingerprint.get("technical_terms") or [])
    career_tokens = len(tokenize_simple(str(fingerprint.get("career_evidence_text") or "")))
    alignment = safe_float(proof_graph.get("proof_alignment_score"))
    if alignment is None:
        alignment = safe_float(fingerprint.get("skill_evidence_hint_score"), 0.0) or 0.0

    if density >= 0.18:
        findings.append(
            _finding(
                "excessive_keyword_density",
                "high" if density >= 0.30 else "medium",
                0.15,
                f"Technical keyword density is unusually high ({density:.2f}).",
            )
        )
    if density >= 0.12 and alignment < 0.20:
        findings.append(
            _finding(
                "buzzword_stuffing",
                "high",
                0.15,
                "Dense technical vocabulary has weak claim-to-career evidence alignment.",
            )
        )
    if claimed_count >= 12 and alignment < 0.25:
        findings.append(
            _finding(
                "many_claimed_skills_weak_evidence",
                "high",
                0.18,
                f"{claimed_count} skills are claimed but proof alignment is only {alignment:.2f}.",
            )
        )
    if technical_count >= 10 and career_tokens < 35:
        findings.append(
            _finding(
                "generic_ai_keyword_spam",
                "medium",
                0.10,
                "Many technical concepts appear while career evidence is unusually short.",
            )
        )
    return findings


def experience_timeline_rules(
    fingerprint: dict[str, Any],
    reference_year: int = 2026,
) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    years = safe_float(fingerprint.get("years_of_experience"))
    title = str(fingerprint.get("current_title") or "")
    text = " ".join(
        (
            str(fingerprint.get("career_evidence_text") or ""),
            str(fingerprint.get("raw_text_compact") or ""),
        )
    )
    text_years = extract_experience_years(text)
    calendar_years = extract_calendar_years(text)

    if years is not None and years < 0:
        findings.append(
            _finding(
                "negative_experience",
                "severe",
                0.50,
                f"Years of experience is negative ({years}).",
            )
        )
    if years is not None and years > 45:
        findings.append(
            _finding(
                "suspiciously_high_experience",
                "severe",
                0.40,
                f"Years of experience is implausibly high ({years}).",
            )
        )
    elif years is not None and years > 25:
        findings.append(
            _finding(
                "suspiciously_high_experience",
                "high",
                0.20,
                f"Years of experience is unusually high ({years}).",
            )
        )
    if years is not None and text_years and max(text_years) - years >= 8:
        findings.append(
            _finding(
                "impossible_years_of_experience",
                "severe",
                0.40,
                "Profile-level experience conflicts strongly with experience stated in text.",
            )
        )

    senior = _contains_any(title, SENIOR_TERMS)
    junior = _contains_any(title, JUNIOR_TERMS)
    if senior and (years is None or years < 2):
        findings.append(
            _finding(
                "senior_title_without_experience",
                "high",
                0.20,
                "Senior title has missing or very low stated experience.",
            )
        )
    if junior and years is not None and years >= 10:
        findings.append(
            _finding(
                "unrealistic_experience_for_title",
                "high",
                0.18,
                "Junior or intern title conflicts with high stated experience.",
            )
        )
    if senior and years is None:
        findings.append(
            _finding(
                "experience_missing_for_senior_role",
                "medium",
                0.10,
                "A senior role has no usable experience value.",
            )
        )

    valid_years = sorted(year for year in calendar_years if 1970 <= year <= reference_year + 1)
    if years is not None and valid_years:
        calendar_span = reference_year - min(valid_years)
        if years > calendar_span + 5:
            findings.append(
                _finding(
                    "impossible_years_of_experience",
                    "severe",
                    0.40,
                    "Stated experience substantially exceeds the visible career calendar span.",
                )
            )
    if len(valid_years) >= 5 and any(
        earlier > later for earlier, later in zip(valid_years, valid_years[1:])
    ):
        findings.append(
            _finding(
                "overlapping_roles_possible",
                "medium",
                0.08,
                "Career years may contain overlapping or inconsistent role periods.",
            )
        )
    return findings


def title_career_rules(
    fingerprint: dict[str, Any],
    proof_graph: dict[str, Any] | None = None,
) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    proof_graph = proof_graph or {}
    title = str(fingerprint.get("current_title") or "")
    career = str(fingerprint.get("career_evidence_text") or "")
    claims = " ".join(
        str(value)
        for value in (
            *(fingerprint.get("claimed_skills") or []),
            *(fingerprint.get("technical_terms") or []),
        )
    )
    ai_claims = _contains_any(claims, AI_TERMS)
    ai_career = _contains_any(career, AI_TERMS)
    alignment = safe_float(proof_graph.get("proof_alignment_score"), 0.0) or 0.0

    if _contains_any(title, AI_TERMS) and not ai_career and alignment < 0.20:
        findings.append(
            _finding(
                "title_skill_mismatch",
                "high",
                0.12,
                "AI/ML title has little corresponding career evidence.",
            )
        )
    if _contains_any(title, NON_TECHNICAL_TITLES) and ai_claims and not ai_career:
        findings.append(
            _finding(
                "non_technical_title_with_deep_ai_claims",
                "high",
                0.18,
                "A non-technical title is paired with deep AI claims unsupported by career text.",
            )
        )
    if _contains_any(title, SENIOR_TERMS) and alignment < 0.15 and ai_claims:
        findings.append(
            _finding(
                "seniority_evidence_mismatch",
                "high",
                0.15,
                "Senior technical positioning has weak supporting evidence.",
            )
        )
    if _contains_any(f"{title} {career}", RESEARCH_TERMS) and not _contains_any(
        career, PRODUCTION_TERMS
    ):
        findings.append(
            _finding(
                "research_only_for_production_jd",
                "medium",
                0.08,
                "Research evidence appears without clear production deployment evidence.",
            )
        )
    supported_count = len(proof_graph.get("supported_skills") or [])
    shallow_evidence = len(tokenize_simple(career)) < 45
    no_depth = all(
        (safe_float(proof_graph.get(field), 0.0) or 0.0) < 0.25
        for field in (
            "production_evidence_score",
            "retrieval_ranking_evidence_score",
            "evaluation_evidence_score",
        )
    )
    if ai_claims and shallow_evidence and supported_count <= 2 and no_depth:
        findings.append(
            _finding(
                "shallow_project_evidence",
                "medium",
                0.06,
                "AI/ML claims have short or generic project evidence and little supported depth.",
            )
        )
    return findings


def availability_rules(
    fingerprint: dict[str, Any],
    reference_year: int = 2026,
) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    behavior = fingerprint.get("behavioral_signal_summary") or {}
    availability = fingerprint.get("availability_signal_summary") or {}
    if not behavior and not availability:
        findings.append(
            _finding(
                "missing_availability_signals",
                "low",
                0.03,
                "Behavioral and availability signals are missing.",
            )
        )
        return findings

    if isinstance(behavior, dict):
        response = safe_float(
            behavior.get("recruiter_response_rate", behavior.get("response_rate"))
        )
        if response is not None and response < 0.10:
            findings.append(
                _finding(
                    "low_response_signal",
                    "medium",
                    0.07,
                    f"Recruiter response rate is low ({response:.2f}).",
                )
            )
        last_active = str(
            behavior.get("last_active_date", behavior.get("last_activity", ""))
        )
        try:
            days_stale = (
                date(reference_year, 12, 31) - date.fromisoformat(last_active[:10])
            ).days
            if days_stale > 180:
                findings.append(
                    _finding(
                        "stale_activity_signal",
                        "medium",
                        0.06,
                        f"Last recorded activity is {days_stale} days old.",
                    )
                )
        except (TypeError, ValueError):
            pass

    if isinstance(availability, dict):
        notice = safe_float(
            availability.get("notice_period_days", availability.get("notice_period"))
        )
        if notice is None:
            findings.append(
                _finding(
                    "unclear_notice_period",
                    "low",
                    0.02,
                    "Notice period is unavailable.",
                )
            )
    return findings


def proof_contradiction_rules(
    fingerprint: dict[str, Any],
    proof_graph: dict[str, Any],
    component_scores: dict[str, Any] | None = None,
) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    component_scores = component_scores or {}
    supported = proof_graph.get("supported_skills") or []
    unsupported = proof_graph.get("unsupported_skills") or []
    claimed = proof_graph.get("claimed_skills") or []
    alignment = safe_float(proof_graph.get("proof_alignment_score"), 0.0) or 0.0
    unsupported_required = component_scores.get("unsupported_required_skills") or []

    if unsupported_required:
        severity = "high" if len(unsupported_required) >= 3 else "medium"
        findings.append(
            _finding(
                "unsupported_required_skill",
                severity,
                0.20,
                f"{len(unsupported_required)} JD-required skills lack strong profile proof.",
            )
        )
    if claimed and alignment < 0.15:
        findings.append(
            _finding(
                "weak_proof_alignment",
                "high" if len(claimed) >= 8 else "medium",
                0.15,
                f"Claim-to-evidence alignment is low ({alignment:.2f}).",
            )
        )
    if len(claimed) >= 10 and len(supported) <= 2:
        findings.append(
            _finding(
                "high_skill_claim_low_evidence",
                "high",
                0.18,
                f"{len(claimed)} skills are claimed but only {len(supported)} are career-supported.",
            )
        )

    claims_text = " ".join(str(value) for value in claimed)
    retrieval_claimed = _contains_any(claims_text, RETRIEVAL_CLAIMS)
    evaluation_claimed = _contains_any(claims_text, EVALUATION_CLAIMS)
    production_claimed = _contains_any(claims_text, PRODUCTION_CLAIMS)
    if retrieval_claimed and safe_float(
        proof_graph.get("retrieval_ranking_evidence_score"), 0.0
    ) == 0:
        findings.append(
            _finding(
                "retrieval_claim_without_evidence",
                "high",
                0.15,
                "Retrieval or ranking is claimed without corresponding career evidence.",
            )
        )
    if evaluation_claimed and safe_float(proof_graph.get("evaluation_evidence_score"), 0.0) == 0:
        findings.append(
            _finding(
                "evaluation_claim_without_evidence",
                "medium",
                0.10,
                "Evaluation concepts are claimed without metric or experiment evidence.",
            )
        )
    if production_claimed and safe_float(proof_graph.get("production_evidence_score"), 0.0) == 0:
        findings.append(
            _finding(
                "production_claim_without_evidence",
                "medium",
                0.10,
                "Production tooling is claimed without deployment evidence.",
            )
        )
    return findings


def evaluate_anomaly_rules(
    fingerprint: dict[str, Any],
    proof_graph: dict[str, Any] | None = None,
    component_scores: dict[str, Any] | None = None,
    deep: bool = True,
    reference_year: int = 2026,
) -> list[RuleFinding]:
    proof_graph = proof_graph or {}
    findings = [
        *zero_duration_expert_rules(fingerprint),
        *keyword_stuffing_rules(fingerprint, proof_graph),
        *availability_rules(fingerprint, reference_year=reference_year),
    ]
    if deep:
        findings.extend(experience_timeline_rules(fingerprint, reference_year=reference_year))
        findings.extend(title_career_rules(fingerprint, proof_graph))
        findings.extend(
            proof_contradiction_rules(fingerprint, proof_graph, component_scores)
        )

    existing_flags = set(fingerprint.get("anomaly_flags") or [])
    if "empty_profile_text" in existing_flags:
        findings.append(
            _finding(
                "empty_profile_text",
                "severe",
                0.50,
                "Candidate profile text is empty.",
            )
        )

    unique: dict[str, RuleFinding] = {}
    severity_order = {"low": 0, "medium": 1, "high": 2, "severe": 3}
    for finding in findings:
        previous = unique.get(finding.flag)
        if previous is None or severity_order[finding.severity] > severity_order[previous.severity]:
            unique[finding.flag] = finding
    return list(unique.values())
