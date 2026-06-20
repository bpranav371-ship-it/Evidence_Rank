import unittest

from src.honeypot_firewall import HoneypotFirewall
from src.risk_reranker import apply_risk_adjusted_reranking


def _item(
    candidate_id: str,
    base_score: float,
    safe: bool,
    empty: bool = False,
) -> dict:
    if safe:
        fingerprint = {
            "candidate_id": candidate_id,
            "current_title": "Senior ML Engineer",
            "years_of_experience": 7,
            "raw_text_compact": "built python retrieval systems",
            "career_evidence_text": "Built and deployed Python retrieval systems.",
            "claimed_skills": ["Python", "Retrieval"],
            "technical_terms": ["Python", "Retrieval"],
            "keyword_density_score": 0.03,
            "behavioral_signal_summary": {"recruiter_response_rate": 0.8},
            "availability_signal_summary": {"notice_period_days": 30},
            "anomaly_flags": [],
        }
        proof = {
            "claimed_skills": ["Python", "Retrieval"],
            "supported_skills": ["Python", "Retrieval"],
            "weakly_supported_skills": [],
            "unsupported_skills": [],
            "proof_alignment_score": 1.0,
            "retrieval_ranking_evidence_score": 0.5,
            "evaluation_evidence_score": 0.25,
            "production_evidence_score": 0.5,
        }
        unsupported = []
    else:
        fingerprint = {
            "candidate_id": candidate_id,
            "current_title": "Marketing Manager",
            "years_of_experience": 6,
            "raw_text_compact": "" if empty else "rag ranking embeddings expert",
            "career_evidence_text": "",
            "claimed_skills": ["RAG"] * 14,
            "technical_terms": ["RAG", "Ranking"] * 6,
            "keyword_density_score": 0.40,
            "behavioral_signal_summary": {},
            "availability_signal_summary": {},
            "anomaly_flags": ["empty_profile_text"] if empty else [],
        }
        proof = {
            "claimed_skills": ["RAG"] * 14,
            "supported_skills": [],
            "weakly_supported_skills": [],
            "unsupported_skills": ["RAG"] * 14,
            "proof_alignment_score": 0.0,
            "retrieval_ranking_evidence_score": 0.0,
            "evaluation_evidence_score": 0.0,
            "production_evidence_score": 0.0,
        }
        unsupported = ["RAG", "Ranking"]
    return {
        "candidate_id": candidate_id,
        "fingerprint": fingerprint,
        "proof_graph": proof,
        "score": {
            "final_score": base_score,
            "proof_alignment_score": proof["proof_alignment_score"],
            "unsupported_required_skills": unsupported,
        },
    }


class RiskRerankerTests(unittest.TestCase):
    def test_high_risk_candidate_moves_down_and_safe_candidate_moves_up(self) -> None:
        risky = _item("RISKY", 0.90, safe=False)
        safe = _item("SAFE", 0.75, safe=True)
        ranked = apply_risk_adjusted_reranking(
            [risky, safe],
            top_k=2,
            strict_top_n=1,
            firewall=HoneypotFirewall(),
        )
        self.assertEqual(ranked[0]["candidate_id"], "SAFE")
        self.assertGreater(ranked[0]["original_rank"], ranked[0]["adjusted_rank"])

    def test_severe_candidate_is_excluded(self) -> None:
        ranked = apply_risk_adjusted_reranking(
            [_item("EMPTY", 0.99, safe=False, empty=True), _item("SAFE", 0.70, safe=True)],
            top_k=2,
            firewall=HoneypotFirewall(),
        )
        self.assertEqual([item["candidate_id"] for item in ranked], ["SAFE"])

    def test_top_10_excludes_severe_risk(self) -> None:
        candidates = [_item("EMPTY", 0.99, safe=False, empty=True)]
        candidates.extend(_item(f"SAFE_{index}", 0.80 - index / 100, safe=True) for index in range(12))
        ranked = apply_risk_adjusted_reranking(
            candidates,
            top_k=10,
            strict_top_n=10,
            firewall=HoneypotFirewall(),
        )
        self.assertNotIn("EMPTY", [item["candidate_id"] for item in ranked[:10]])


if __name__ == "__main__":
    unittest.main()
