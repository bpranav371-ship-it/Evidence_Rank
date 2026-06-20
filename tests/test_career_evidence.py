import unittest

from src.career_evidence import build_career_evidence_profile


class CareerEvidenceTests(unittest.TestCase):
    def test_extracts_experience_and_evidence_terms(self) -> None:
        profile = build_career_evidence_profile(
            {
                "candidate_id": "A",
                "current_title": "Senior Search Engineer",
                "years_of_experience": 7,
                "career_evidence_text": (
                    "Built and deployed semantic search and ranking APIs on AWS. "
                    "Evaluated with NDCG, MRR and A/B testing for live users."
                ),
                "raw_text_compact": "7+ years experience",
            }
        )
        self.assertIn(7.0, profile["parsed_years_of_experience"])
        self.assertIn("deployed", profile["production_terms_found"])
        self.assertIn("ranking", profile["retrieval_ranking_terms_found"])
        self.assertIn("ndcg", profile["evaluation_terms_found"])
        self.assertGreater(profile["career_depth_score"], 0)

    def test_missing_fields_are_safe(self) -> None:
        profile = build_career_evidence_profile({})
        self.assertEqual(profile["candidate_id"], "")
        self.assertGreaterEqual(profile["career_consistency_score"], 0)
        self.assertLessEqual(profile["career_consistency_score"], 1)


if __name__ == "__main__":
    unittest.main()
