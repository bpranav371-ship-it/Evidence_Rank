import unittest

from src.jd_constraints import build_jd_constraint_profile
from src.jd_parser import parse_jd_text


class JDConstraintTests(unittest.TestCase):
    def test_detects_retrieval_ranking_archetype_and_constraints(self) -> None:
        profile = build_jd_constraint_profile(
            parse_jd_text(
                "Senior AI engineer must build retrieval, ranking and recommendation "
                "systems with embeddings, NDCG evaluation and production APIs."
            )
        )
        self.assertEqual(profile["role_archetype"], "retrieval_ranking_engineer")
        self.assertTrue(profile["required_positive_skills"])
        self.assertIn("no_retrieval_or_ranking_evidence", profile["negative_constraints"])
        self.assertIn("no_production_evidence", profile["negative_constraints"])

    def test_empty_jd_is_safe(self) -> None:
        profile = build_jd_constraint_profile(parse_jd_text(""))
        self.assertEqual(profile["role_archetype"], "unknown")
        self.assertEqual(profile["required_positive_skills"], [])


if __name__ == "__main__":
    unittest.main()
