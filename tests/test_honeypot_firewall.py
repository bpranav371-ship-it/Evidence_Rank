import unittest

from src.honeypot_firewall import HoneypotFirewall


def _proof(alignment: float = 0.9) -> dict:
    return {
        "claimed_skills": ["Python", "Retrieval"],
        "supported_skills": ["Python", "Retrieval"] if alignment > 0.5 else [],
        "weakly_supported_skills": [],
        "unsupported_skills": [] if alignment > 0.5 else ["Python", "Retrieval"],
        "proof_alignment_score": alignment,
        "retrieval_ranking_evidence_score": 0.5 if alignment > 0.5 else 0.0,
        "evaluation_evidence_score": 0.25 if alignment > 0.5 else 0.0,
        "production_evidence_score": 0.5 if alignment > 0.5 else 0.0,
    }


class HoneypotFirewallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.firewall = HoneypotFirewall()

    def test_low_risk_candidate_gets_low_score(self) -> None:
        report = self.firewall.assess(
            {
                "candidate_id": "SAFE",
                "current_title": "Senior ML Engineer",
                "years_of_experience": 7,
                "raw_text_compact": "built python retrieval services",
                "career_evidence_text": "Built and deployed Python retrieval services.",
                "claimed_skills": ["Python", "Retrieval"],
                "technical_terms": ["Python", "Retrieval"],
                "keyword_density_score": 0.03,
                "behavioral_signal_summary": {"recruiter_response_rate": 0.8},
                "availability_signal_summary": {"notice_period_days": 30},
                "anomaly_flags": [],
            },
            _proof(),
            component_scores={"unsupported_required_skills": []},
        )
        self.assertEqual(report["risk_level"], "low")
        self.assertLessEqual(report["risk_score"], 0.24)

    def test_keyword_stuffer_gets_medium_or_high_risk(self) -> None:
        report = self.firewall.assess(
            {
                "candidate_id": "STUFFER",
                "current_title": "Marketing Manager",
                "years_of_experience": 6,
                "raw_text_compact": "rag ranking llm embeddings vector database",
                "career_evidence_text": "Managed content campaigns.",
                "claimed_skills": ["RAG"] * 14,
                "technical_terms": ["RAG", "Ranking", "LLM"] * 4,
                "keyword_density_score": 0.35,
                "behavioral_signal_summary": {},
                "availability_signal_summary": {},
                "anomaly_flags": [],
            },
            _proof(0.0),
            component_scores={"unsupported_required_skills": ["RAG", "Ranking"]},
        )
        self.assertIn(report["risk_level"], {"high", "severe"})

    def test_empty_profile_is_severe_and_disqualified(self) -> None:
        report = self.firewall.assess(
            {
                "candidate_id": "EMPTY",
                "raw_text_compact": "",
                "career_evidence_text": "",
                "claimed_skills": [],
                "technical_terms": [],
                "keyword_density_score": 0.0,
                "behavioral_signal_summary": {},
                "availability_signal_summary": {},
                "anomaly_flags": ["empty_profile_text"],
            },
            _proof(0.0),
            component_scores={"unsupported_required_skills": ["Python"]},
        )
        self.assertEqual(report["risk_level"], "severe")
        self.assertTrue(report["disqualified"])

    def test_unsupported_senior_ai_claim_gets_high_risk(self) -> None:
        report = self.firewall.assess(
            {
                "candidate_id": "UNSUPPORTED",
                "current_title": "Senior AI Engineer",
                "years_of_experience": 1,
                "raw_text_compact": "Senior AI Engineer RAG ranking expert",
                "career_evidence_text": "Managed spreadsheets.",
                "claimed_skills": ["RAG", "Ranking", "LLM"],
                "technical_terms": ["RAG", "Ranking", "LLM"],
                "keyword_density_score": 0.15,
                "behavioral_signal_summary": {},
                "availability_signal_summary": {},
                "anomaly_flags": [],
            },
            _proof(0.0),
            component_scores={"unsupported_required_skills": ["RAG", "Ranking", "LLM"]},
        )
        self.assertIn(report["risk_level"], {"high", "severe"})

    def test_risk_score_is_bounded(self) -> None:
        report = self.firewall.assess(
            {"candidate_id": "ANY", "anomaly_flags": ["empty_profile_text"]},
            _proof(0.0),
            component_scores={"unsupported_required_skills": ["A"] * 20},
        )
        self.assertGreaterEqual(report["risk_score"], 0)
        self.assertLessEqual(report["risk_score"], 1)


if __name__ == "__main__":
    unittest.main()
