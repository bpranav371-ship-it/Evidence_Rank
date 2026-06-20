import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.explanation_cards import build_explanation_cards


class ExplanationCardsTests(unittest.TestCase):
    def _outputs(self, root: Path) -> None:
        with (root / "ranked_candidates.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=("candidate_id", "rank", "score", "reasoning")
            )
            writer.writeheader()
            writer.writerows(
                [
                    {"candidate_id": "A", "rank": 1, "score": 0.9, "reasoning": "Supported retrieval work."},
                    {"candidate_id": "B", "rank": 2, "score": 0.7, "reasoning": "Good Python evidence."},
                ]
            )
        fields = (
            "candidate_id", "rank", "final_score", "risk_adjusted_score",
            "calibrated_final_score", "proof_alignment_score",
            "retrieval_ranking_evidence_score", "evaluation_evidence_score",
            "production_evidence_score", "evidence_confidence_score",
            "calibrated_hireability_score", "honeypot_risk_score", "risk_level",
            "risk_flags", "penalty_score", "calibration_penalty",
        )
        with (root / "score_breakdown.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow(
                {
                    "candidate_id": "A", "rank": 1, "final_score": 0.9,
                    "risk_adjusted_score": 0.88, "calibrated_final_score": 0.91,
                    "proof_alignment_score": 0.8, "retrieval_ranking_evidence_score": 1,
                    "evaluation_evidence_score": 0.7, "production_evidence_score": 0.8,
                    "evidence_confidence_score": 0.75, "calibrated_hireability_score": 0.5,
                    "honeypot_risk_score": 0.1, "risk_level": "low", "risk_flags": "",
                    "penalty_score": 0, "calibration_penalty": 0,
                }
            )
            writer.writerow(
                {
                    "candidate_id": "B", "rank": 2, "final_score": 0.7,
                    "risk_adjusted_score": 0.7, "calibrated_final_score": 0.7,
                    "proof_alignment_score": 0.4, "retrieval_ranking_evidence_score": 0,
                    "evaluation_evidence_score": 0, "production_evidence_score": 0,
                    "evidence_confidence_score": 0.4, "calibrated_hireability_score": 0.5,
                    "honeypot_risk_score": 0, "risk_level": "low", "risk_flags": "",
                    "penalty_score": 0, "calibration_penalty": 0,
                }
            )
        (root / "top_candidate_proofs.jsonl").write_text(
            json.dumps(
                {
                    "candidate_id": "A",
                    "proof_graph": {
                        "supported_skills": ["Retrieval"],
                        "proof_summary": "Retrieval supported by career evidence.",
                    },
                    "top_evidence_snippets": ["Built a retrieval service."],
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def test_creates_cards_supports_top_n_and_missing_snippets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._outputs(root)
            cards, paths = build_explanation_cards(root, top_n=2)
            markdown = paths["top10_explanation_cards_markdown"].read_text(encoding="utf-8")
        self.assertEqual(len(cards), 2)
        self.assertIn("Built a retrieval service.", markdown)
        self.assertEqual(cards[1]["top_evidence_snippets"], ["No explicit snippet available"])
        self.assertNotIn("invented", markdown.lower())


if __name__ == "__main__":
    unittest.main()
