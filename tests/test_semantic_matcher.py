import unittest
from unittest.mock import patch

from src.jd_parser import parse_jd_text
from src.proof_graph import build_proof_graph
from src.scoring_engine import score_candidate
from src.semantic_matcher import SemanticMatcher


class SemanticMatcherTests(unittest.TestCase):
    def test_related_text_scores_above_unrelated(self) -> None:
        matcher = SemanticMatcher()
        related = matcher.score_pair(
            "retrieval augmented generation and search ranking",
            "built a RAG retriever for search relevance ranking",
        )
        unrelated = matcher.score_pair(
            "retrieval augmented generation and search ranking",
            "managed payroll and office administration",
        )
        self.assertGreater(related, unrelated)

    def test_hyphenated_variants_and_typo_tolerance(self) -> None:
        matcher = SemanticMatcher()
        self.assertGreater(
            matcher.score_pair("transformers pytorch retrieval", "transformer PyTorch-based retrievel"),
            matcher.score_pair("transformers pytorch retrieval", "sales accounting payroll"),
        )

    def test_empty_text_is_safe(self) -> None:
        self.assertEqual(SemanticMatcher().score_pair("", "candidate"), 0.0)

    def test_scoring_falls_back_to_lexical(self) -> None:
        candidate = {
            "candidate_id": "A",
            "raw_text_compact": "python retrieval engineer",
            "claimed_skills": ["Python", "Retrieval"],
            "technical_terms": ["Python", "Retrieval"],
            "career_evidence_text": "Built Python retrieval systems.",
            "current_title": "ML Engineer",
            "anomaly_flags": [],
        }
        jd = parse_jd_text("Python retrieval engineer")
        graph = build_proof_graph(candidate)
        baseline = score_candidate(jd, candidate, graph)
        with patch("src.scoring_engine.SemanticMatcher.score_pair", return_value=0.0):
            fallback = score_candidate(
                jd, candidate, graph, semantic_config={"enabled": True}
            )
        self.assertEqual(baseline["jd_relevance_score"], fallback["jd_relevance_score"])


if __name__ == "__main__":
    unittest.main()
