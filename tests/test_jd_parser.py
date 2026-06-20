import unittest

from src.jd_parser import parse_jd_text


class JDParserTests(unittest.TestCase):
    def test_extracts_ai_engineer_skills(self) -> None:
        profile = parse_jd_text(
            """
            Senior AI Engineer with 5-9 years of experience.
            Must have Python, embeddings, vector databases, retrieval, ranking,
            NDCG, MRR, MAP, A/B testing, Docker, AWS, and production ML.
            Nice to have fine-tuning and Kubernetes. Location: Pune or Noida, hybrid.
            """
        )

        self.assertIn("Python", profile["required_skills"])
        self.assertIn("Retrieval", profile["required_skills"])
        self.assertIn("Ranking", profile["required_skills"])
        self.assertIn("NDCG", profile["evaluation_keywords"])
        self.assertIn("Fine-tuning", profile["preferred_skills"])
        self.assertIn("senior", profile["seniority_keywords"])
        self.assertIn("pune", profile["location_requirements"])
        self.assertEqual(profile["experience_requirements"][0]["minimum_years"], 5)

    def test_empty_jd_is_safe(self) -> None:
        profile = parse_jd_text("")

        self.assertEqual(profile["required_skills"], [])
        self.assertEqual(profile["normalized_jd_text"], "")
        self.assertEqual(profile["experience_requirements"], [])


if __name__ == "__main__":
    unittest.main()
