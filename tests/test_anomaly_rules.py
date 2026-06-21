import unittest

from src.anomaly_rules import (
    evaluate_anomaly_rules,
    experience_timeline_rules,
    keyword_stuffing_rules,
    proof_contradiction_rules,
    zero_duration_expert_rules,
    title_career_rules,
)


class AnomalyRulesTests(unittest.TestCase):
    def test_detects_zero_duration_expert_claim(self) -> None:
        findings = zero_duration_expert_rules(
            {
                "skill_details": [
                    {"name": "RAG", "proficiency": "expert", "duration_months": 0}
                ],
                "raw_text_compact": "",
            }
        )
        self.assertIn("zero_duration_expert_claim", [finding.flag for finding in findings])

    def test_detects_excessive_keyword_density(self) -> None:
        findings = keyword_stuffing_rules(
            {
                "keyword_density_score": 0.35,
                "claimed_skills": ["Python"] * 14,
                "technical_terms": ["RAG"] * 10,
                "career_evidence_text": "short",
            },
            {"proof_alignment_score": 0.05},
        )
        flags = {finding.flag for finding in findings}
        self.assertIn("excessive_keyword_density", flags)
        self.assertIn("buzzword_stuffing", flags)

    def test_detects_unsupported_skill_pattern(self) -> None:
        findings = proof_contradiction_rules(
            {"claimed_skills": ["RAG", "Ranking"]},
            {
                "claimed_skills": ["RAG", "Ranking"],
                "supported_skills": [],
                "unsupported_skills": ["RAG", "Ranking"],
                "proof_alignment_score": 0.0,
                "retrieval_ranking_evidence_score": 0.0,
                "evaluation_evidence_score": 0.0,
                "production_evidence_score": 0.0,
            },
            {"unsupported_required_skills": ["RAG", "Ranking"]},
        )
        flags = {finding.flag for finding in findings}
        self.assertIn("unsupported_required_skill", flags)
        self.assertIn("retrieval_claim_without_evidence", flags)

    def test_handles_missing_fields_safely(self) -> None:
        findings = evaluate_anomaly_rules({}, {}, {}, deep=True)
        self.assertIsInstance(findings, list)

    def test_normal_candidate_is_not_aggressively_flagged(self) -> None:
        findings = evaluate_anomaly_rules(
            {
                "current_title": "Senior Machine Learning Engineer",
                "years_of_experience": 7,
                "raw_text_compact": "built python retrieval systems",
                "career_evidence_text": (
                    "Built and deployed Python retrieval systems with monitoring."
                ),
                "claimed_skills": ["Python", "Retrieval"],
                "technical_terms": ["Python", "Retrieval"],
                "keyword_density_score": 0.03,
                "behavioral_signal_summary": {"recruiter_response_rate": 0.8},
                "availability_signal_summary": {"notice_period_days": 30},
                "anomaly_flags": [],
            },
            {
                "claimed_skills": ["Python", "Retrieval"],
                "supported_skills": ["Python", "Retrieval"],
                "unsupported_skills": [],
                "proof_alignment_score": 1.0,
                "retrieval_ranking_evidence_score": 0.5,
                "evaluation_evidence_score": 0.0,
                "production_evidence_score": 0.5,
            },
            {"unsupported_required_skills": []},
            deep=True,
        )
        self.assertFalse(any(finding.severity in {"high", "severe"} for finding in findings))

    def test_service_company_with_strong_ai_evidence_is_not_penalized(self) -> None:
        findings = title_career_rules(
            {
                "current_title": "AI Engineer",
                "career_evidence_text": (
                    "At TCS built and deployed a production retrieval ranking API "
                    "with NDCG evaluation, monitoring, Docker and AWS."
                ),
                "claimed_skills": ["Python", "Retrieval", "Ranking"],
                "technical_terms": ["Python", "Retrieval", "Ranking"],
            },
            {
                "supported_skills": ["Python", "Retrieval", "Ranking"],
                "proof_alignment_score": 1.0,
                "production_evidence_score": 1.0,
                "retrieval_ranking_evidence_score": 1.0,
                "evaluation_evidence_score": 1.0,
            },
        )
        self.assertNotIn("shallow_project_evidence", {item.flag for item in findings})

    def test_generic_ai_claims_can_receive_shallow_evidence_flag(self) -> None:
        findings = title_career_rules(
            {
                "current_title": "Support Engineer",
                "career_evidence_text": "Handled support tickets.",
                "claimed_skills": ["AI", "RAG", "Ranking"],
                "technical_terms": ["AI", "RAG", "Ranking"],
            },
            {
                "supported_skills": [],
                "proof_alignment_score": 0.0,
                "production_evidence_score": 0.0,
                "retrieval_ranking_evidence_score": 0.0,
                "evaluation_evidence_score": 0.0,
            },
        )
        self.assertIn("shallow_project_evidence", {item.flag for item in findings})

    def test_fixed_reference_year_is_deterministic(self) -> None:
        candidate = {
            "years_of_experience": 8,
            "current_title": "Senior Engineer",
            "career_evidence_text": "Worked from 2020 to 2025.",
        }
        first = experience_timeline_rules(candidate, reference_year=2026)
        second = experience_timeline_rules(candidate, reference_year=2026)
        self.assertEqual(first, second)

    def test_scoring_rules_do_not_use_system_year(self) -> None:
        source = (
            __import__("pathlib").Path(__file__).resolve().parents[1]
            / "src"
            / "anomaly_rules.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("date.today().year", source)
        self.assertNotIn("datetime.now().year", source)


if __name__ == "__main__":
    unittest.main()
