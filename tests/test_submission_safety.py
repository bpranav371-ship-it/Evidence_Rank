import csv
import tempfile
import unittest
from pathlib import Path

from src.submission_safety import validate_final_submission


class SubmissionSafetyTests(unittest.TestCase):
    def _write_outputs(self, root: Path, rows: list[dict], breakdown: list[dict]) -> None:
        with (root / "ranked_candidates.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=("candidate_id", "rank", "score", "reasoning"))
            writer.writeheader()
            writer.writerows(rows)
        with (root / "score_breakdown.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=("candidate_id", "rank", "risk_level", "disqualified", "risk_flags"),
            )
            writer.writeheader()
            writer.writerows(breakdown)
        (root / "top_candidate_proofs.jsonl").write_text("{}\n", encoding="utf-8")

    def test_accepts_valid_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_outputs(
                root,
                [
                    {"candidate_id": "A", "rank": 1, "score": 0.9, "reasoning": "Strong evidence-backed retrieval and production experience."},
                    {"candidate_id": "B", "rank": 2, "score": 0.7, "reasoning": "Good technical match with specific career evidence and availability."},
                ],
                [
                    {"candidate_id": "A", "rank": 1, "risk_level": "low", "disqualified": False, "risk_flags": ""},
                    {"candidate_id": "B", "rank": 2, "risk_level": "low", "disqualified": False, "risk_flags": ""},
                ],
            )
            report = validate_final_submission(root, top_k=2)
        self.assertTrue(report["passed"], report["blocking_errors"])

    def test_rejects_duplicates_missing_reasoning_and_severe_top10(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_outputs(
                root,
                [
                    {"candidate_id": "A", "rank": 1, "score": 0.5, "reasoning": ""},
                    {"candidate_id": "A", "rank": 2, "score": 0.5, "reasoning": ""},
                ],
                [
                    {"candidate_id": "A", "rank": 1, "risk_level": "severe", "disqualified": False, "risk_flags": ""},
                    {"candidate_id": "A", "rank": 2, "risk_level": "low", "disqualified": False, "risk_flags": ""},
                ],
            )
            report = validate_final_submission(root, top_k=2)
        self.assertFalse(report["passed"])
        self.assertTrue(any("duplicate" in error.lower() for error in report["blocking_errors"]))

    def test_warns_on_flat_scores(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_outputs(
                root,
                [
                    {"candidate_id": str(index), "rank": index, "score": 0.5 + index / 10000, "reasoning": "Specific evidence-backed explanation long enough."}
                    for index in range(1, 11)
                ][::-1],
                [
                    {"candidate_id": str(index), "rank": index, "risk_level": "low", "disqualified": False, "risk_flags": ""}
                    for index in range(1, 11)
                ],
            )
            report = validate_final_submission(root, top_k=10)
        self.assertTrue(any("flat" in warning.lower() for warning in report["warnings"]))


if __name__ == "__main__":
    unittest.main()
