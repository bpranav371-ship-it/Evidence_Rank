from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path
from typing import Any

from .baseline_ranker import rank_fingerprints
from .honeypot_firewall import HoneypotFirewall
from .jd_parser import parse_jd_file
from .utils import write_json


def _candidate(
    candidate_id: str,
    title: str,
    skills: list[str],
    career: str,
    raw: str,
    *,
    years: float | None = 6,
    keyword_density: float = 0.05,
    behavior: dict[str, Any] | None = None,
    availability: dict[str, Any] | None = None,
    anomalies: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "raw_text_compact": raw,
        "claimed_skills": skills,
        "technical_terms": skills,
        "current_title": title,
        "years_of_experience": years,
        "location": "India",
        "career_evidence_text": career,
        "education_text": "",
        "behavioral_signal_summary": behavior or {},
        "availability_signal_summary": availability or {},
        "anomaly_flags": anomalies or [],
        "missing_fields": [],
        "profile_completeness_score": 0.85,
        "keyword_density_score": keyword_density,
        "skill_evidence_hint_score": 0.8 if career else 0.0,
    }


def build_benchmark_candidates() -> list[dict[str, Any]]:
    """Return fixed synthetic profiles used only for offline sanity checks."""
    return [
        _candidate(
            "BENCH_PRODUCTION_RETRIEVAL",
            "Senior Retrieval and Ranking Engineer",
            ["Python", "LLM", "RAG", "Retrieval", "Ranking", "NDCG", "Docker", "AWS"],
            (
                "Built Python semantic retrieval and learning-to-rank services using embeddings. "
                "Deployed APIs on AWS with Docker, monitored latency, and evaluated NDCG and MRR "
                "through offline experiments and A/B tests."
            ),
            "Senior engineer shipping production search, RAG, retrieval, and ranking systems.",
            behavior={"response_rate": 0.9, "interview_completion_rate": 0.9},
            availability={"open_to_work": True, "notice_period_days": 30},
        ),
        _candidate(
            "BENCH_KEYWORD_STUFFER",
            "AI Expert",
            [
                "Python", "Machine Learning", "LLM", "RAG", "Embeddings", "Retrieval",
                "Ranking", "NDCG", "MRR", "Docker", "AWS", "Kubernetes",
            ],
            "Created presentations and listed technology trends.",
            "AI ML LLM RAG embeddings retrieval ranking NDCG MRR Docker AWS Kubernetes expert.",
            years=0,
            keyword_density=0.55,
            anomalies=["extremely_high_keyword_density"],
        ),
        _candidate(
            "BENCH_RESEARCH_ONLY",
            "Research Scientist",
            ["Python", "Machine Learning", "NLP", "Transformers", "Evaluation"],
            (
                "Published papers on transformer representations and benchmarked models using "
                "precision, recall, and F1. No production deployment responsibility."
            ),
            "Research scientist focused on papers, benchmarks, and model experiments.",
        ),
        _candidate(
            "BENCH_SERVICE_ONLY",
            "Customer Support Lead",
            ["AI", "APIs"],
            "Led customer support operations, ticket resolution, and service delivery.",
            "Support operations professional interested in AI tools.",
        ),
        _candidate(
            "BENCH_GENERAL_ML",
            "Machine Learning Engineer",
            ["Python", "Machine Learning", "PyTorch", "SQL", "Docker"],
            "Built classification pipelines in Python and deployed batch models with Docker.",
            "Machine learning engineer with supervised learning and data pipeline experience.",
        ),
        _candidate(
            "BENCH_HIDDEN_GEM",
            "Software Engineer",
            ["Python", "Backend", "APIs"],
            (
                "Improved search result ordering from user feedback, built a service that selected "
                "the best documents for each query, measured click quality, and shipped the API "
                "to production with monitoring."
            ),
            "Engineer who shipped a monitored document-search service used by customers.",
            keyword_density=0.02,
            behavior={"response_rate": 0.8},
            availability={"open_to_work": True},
        ),
        _candidate(
            "BENCH_SEVERE_HONEYPOT",
            "Principal AI Architect",
            ["LLM", "RAG", "Retrieval", "Ranking", "NDCG", "AWS"],
            "",
            "",
            years=0,
            keyword_density=0.9,
            anomalies=["empty_profile_text", "extremely_high_keyword_density"],
        ),
        _candidate(
            "BENCH_MISSING_BEHAVIOR",
            "Search ML Engineer",
            ["Python", "Retrieval", "Ranking", "Evaluation", "Docker"],
            (
                "Built Python retrieval and ranking pipelines, evaluated MRR and precision, "
                "and deployed a Docker API with production monitoring."
            ),
            "Search ML engineer with evidence-backed retrieval and production work.",
            behavior={},
            availability={},
        ),
    ]


def run_offline_benchmarks(
    jd_path: str | Path,
    output_dir: str | Path,
    *,
    min_pass_rate: float = 0.75,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    candidates = build_benchmark_candidates()
    jd_profile = parse_jd_file(jd_path)
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "benchmark_fingerprints.jsonl"
        source.write_text(
            "".join(json.dumps(candidate) + "\n" for candidate in candidates),
            encoding="utf-8",
        )
        result = rank_fingerprints(
            source,
            jd_profile,
            top_k=len(candidates),
            strict_rerank_pool_size=len(candidates),
            progress_every=0,
            enable_honeypot_firewall=True,
            firewall=HoneypotFirewall(),
            risk_rerank_pool_size=len(candidates),
            enable_evidence_calibration=True,
            calibration_pool_size=len(candidates),
        )

    ranked = {item["candidate_id"]: item for item in result.ranked_candidates}
    rank = {item["candidate_id"]: index for index, item in enumerate(result.ranked_candidates, 1)}

    def score(candidate_id: str) -> float:
        item = ranked.get(candidate_id, {})
        values = item.get("score", {})
        return float(values.get("calibrated_final_score", 0.0))

    checks = {
        "strong production retrieval candidate": (
            rank.get("BENCH_PRODUCTION_RETRIEVAL", 99) < rank.get("BENCH_KEYWORD_STUFFER", 99),
            "Evidence-backed production retrieval profile should beat keyword stuffing.",
        ),
        "keyword stuffer": (
            rank.get("BENCH_KEYWORD_STUFFER", 99) > rank.get("BENCH_HIDDEN_GEM", 99),
            "Keyword-only claims should lose to concrete shipped-system evidence.",
        ),
        "research-only candidate": (
            rank.get("BENCH_RESEARCH_ONLY", 99) > rank.get("BENCH_PRODUCTION_RETRIEVAL", 99),
            "Research-only evidence should not beat production evidence for this JD.",
        ),
        "service-only profile": (
            rank.get("BENCH_SERVICE_ONLY", 99) > rank.get("BENCH_GENERAL_ML", 99),
            "A service profile with weak AI proof should rank below a real ML profile.",
        ),
        "strong ML without retrieval depth": (
            rank.get("BENCH_GENERAL_ML", 99) > rank.get("BENCH_PRODUCTION_RETRIEVAL", 99),
            "General ML should rank decently but below retrieval/ranking depth.",
        ),
        "low-risk hidden gem": (
            rank.get("BENCH_HIDDEN_GEM", 99) < rank.get("BENCH_KEYWORD_STUFFER", 99),
            "Plain-language shipped evidence should beat buzzword density.",
        ),
        "severe-risk honeypot": (
            rank.get("BENCH_SEVERE_HONEYPOT", 99) > 3,
            "An empty contradictory profile must not enter the top three.",
        ),
        "missing behavior signals": (
            rank.get("BENCH_MISSING_BEHAVIOR", 99) < rank.get("BENCH_SERVICE_ONLY", 99),
            "Missing behavior data must not erase strong technical evidence.",
        ),
    }
    id_by_case = {
        "strong production retrieval candidate": "BENCH_PRODUCTION_RETRIEVAL",
        "keyword stuffer": "BENCH_KEYWORD_STUFFER",
        "research-only candidate": "BENCH_RESEARCH_ONLY",
        "service-only profile": "BENCH_SERVICE_ONLY",
        "strong ML without retrieval depth": "BENCH_GENERAL_ML",
        "low-risk hidden gem": "BENCH_HIDDEN_GEM",
        "severe-risk honeypot": "BENCH_SEVERE_HONEYPOT",
        "missing behavior signals": "BENCH_MISSING_BEHAVIOR",
    }
    rows: list[dict[str, Any]] = []
    for case_name, (passed, expected) in checks.items():
        candidate_id = id_by_case[case_name]
        item = ranked.get(candidate_id, {})
        values = item.get("score", {})
        rows.append(
            {
                "case_name": case_name,
                "candidate_id": candidate_id,
                "expected_behavior": expected,
                "observed_rank": rank.get(candidate_id),
                "observed_score": round(score(candidate_id), 6),
                "passed": bool(passed),
                "explanation": (
                    "Observed ordering matches the expected sanity behavior."
                    if passed else "Observed ordering needs review."
                ),
                "important_scores": {
                    "proof_alignment": values.get("proof_alignment_score", 0.0),
                    "risk": values.get("honeypot_risk_score", 0.0),
                    "evidence_confidence": values.get("evidence_confidence_score", 0.0),
                    "top10_readiness": values.get("top10_readiness_score", 0.0),
                },
            }
        )
    pass_rate = sum(row["passed"] for row in rows) / len(rows)
    report = {
        "passed": pass_rate >= min_pass_rate,
        "pass_rate": round(pass_rate, 4),
        "minimum_pass_rate": min_pass_rate,
        "cases": rows,
        "notes": (
            "Synthetic benchmark cases are deterministic sanity checks, not official "
            "hackathon labels or leaderboard metrics."
        ),
    }
    report_path = output / "benchmark_report.json"
    summary_path = output / "benchmark_summary.csv"
    write_json(report_path, report)
    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = (
            "case_name", "candidate_id", "expected_behavior", "observed_rank",
            "observed_score", "passed", "explanation",
        )
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in fieldnames})
    report["output_paths"] = {
        "benchmark_report": str(report_path),
        "benchmark_summary": str(summary_path),
    }
    return report
