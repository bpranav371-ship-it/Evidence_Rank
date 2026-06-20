import unittest

from src.proof_graph import build_proof_graph


class ProofGraphTests(unittest.TestCase):
    def test_supports_skill_when_career_evidence_exists(self) -> None:
        graph = build_proof_graph(
            {
                "candidate_id": "CAND_1",
                "claimed_skills": ["Python", "Ranking", "RAG"],
                "technical_terms": ["Python", "Ranking", "RAG"],
                "current_title": "Machine Learning Engineer",
                "career_evidence_text": (
                    "Built Python search ranking services and evaluated them with NDCG. "
                    "Deployed a retrieval augmented generation system using embeddings."
                ),
                "education_text": "",
                "raw_text_compact": "",
            }
        )

        self.assertIn("Python", graph["supported_skills"])
        self.assertIn("Ranking", graph["supported_skills"])
        self.assertIn("RAG", graph["supported_skills"])
        self.assertTrue(graph["evidence_snippets"]["Ranking"])
        self.assertGreater(graph["retrieval_ranking_evidence_score"], 0)

    def test_marks_skill_unsupported_without_evidence(self) -> None:
        graph = build_proof_graph(
            {
                "candidate_id": "CAND_2",
                "claimed_skills": ["PyTorch"],
                "technical_terms": [],
                "current_title": "Marketing Manager",
                "career_evidence_text": "Managed brand campaigns and content operations.",
                "education_text": "",
                "raw_text_compact": "Marketing leader.",
            }
        )

        self.assertIn("PyTorch", graph["unsupported_skills"])
        self.assertEqual(graph["evidence_snippets"], {})


if __name__ == "__main__":
    unittest.main()
