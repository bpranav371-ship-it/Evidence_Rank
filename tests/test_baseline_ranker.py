import json
import tempfile
import unittest
from pathlib import Path

from src.baseline_ranker import rank_fingerprints
from src.jd_parser import parse_jd_text
from src.proof_graph import build_proof_graph
from src.scoring_engine import score_candidate


def _fingerprint(
    candidate_id: str,
    title: str,
    skills: list[str],
    career: str,
    raw: str,
    behavior: dict | None = None,
    availability: dict | None = None,
    anomalies: list[str] | None = None,
) -> dict:
    return {
        "candidate_id": candidate_id,
        "raw_text_compact": raw,
        "claimed_skills": skills,
        "technical_terms": skills,
        "current_title": title,
        "years_of_experience": 7,
        "location": "pune",
        "career_evidence_text": career,
        "education_text": "",
        "behavioral_signal_summary": behavior or {},
        "availability_signal_summary": availability or {},
        "anomaly_flags": anomalies or [],
        "missing_fields": [],
        "profile_completeness_score": 0.9,
        "keyword_density_score": 0.05,
        "skill_evidence_hint_score": 0.8,
    }


class BaselineRankerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.jd = parse_jd_text(
            "Senior AI Engineer must have Python, embeddings, retrieval, ranking, "
            "NDCG evaluation, production ML, Docker and AWS."
        )

    def test_strong_candidate_ranks_above_keyword_stuffer(self) -> None:
        strong = _fingerprint(
            "CAND_STRONG",
            "Senior Machine Learning Engineer",
            ["Python", "Embeddings", "Retrieval", "Ranking", "NDCG", "Docker", "AWS"],
            (
                "Built and deployed Python embedding retrieval and search ranking services. "
                "Evaluated ranking quality with NDCG and monitored production latency on AWS "
                "using Docker."
            ),
            "Senior ML engineer building production retrieval systems.",
            {"recruiter_response_rate": 0.8, "interview_completion_rate": 0.9},
            {"notice_period_days": 30, "open_to_work_flag": True},
        )
        weak = _fingerprint(
            "CAND_WEAK",
            "Marketing Manager",
            ["Python", "Embeddings", "Retrieval", "Ranking", "NDCG", "Docker", "AWS"],
            "Managed campaigns, brand content, and marketing operations.",
            "Python embeddings retrieval ranking NDCG Docker AWS expert.",
            anomalies=["extremely_high_keyword_density"],
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fingerprints.jsonl"
            path.write_text(
                "\n".join(json.dumps(item) for item in (weak, strong)),
                encoding="utf-8",
            )
            result = rank_fingerprints(path, self.jd, top_k=2, strict_rerank_pool_size=2)

        self.assertEqual(result.ranked_candidates[0]["candidate_id"], "CAND_STRONG")
        self.assertGreater(
            result.ranked_candidates[0]["score"]["final_score"],
            result.ranked_candidates[1]["score"]["final_score"],
        )

    def test_missing_signals_and_skills_are_safe_and_score_is_bounded(self) -> None:
        candidate = _fingerprint(
            "CAND_MISSING",
            "",
            [],
            "",
            "",
            behavior=None,
            availability=None,
            anomalies=["missing_skills", "missing_experience"],
        )
        graph = build_proof_graph(candidate)
        score = score_candidate(self.jd, candidate, graph)

        self.assertTrue(score["neutral_hireability_used"])
        self.assertGreaterEqual(score["final_score"], 0)
        self.assertLessEqual(score["final_score"], 1)


if __name__ == "__main__":
    unittest.main()
