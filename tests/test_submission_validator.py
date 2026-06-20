import csv
import tempfile
import unittest
from pathlib import Path

from src.submission_validator import validate_ranked_candidates


class SubmissionValidatorTests(unittest.TestCase):
    def _write(self, path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
        fieldnames = fields or ["candidate_id", "rank", "score", "reasoning"]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_accepts_valid_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ranked.csv"
            self._write(
                path,
                [
                    {"candidate_id": "A", "rank": 1, "score": 0.9, "reasoning": "Evidence A"},
                    {"candidate_id": "B", "rank": 2, "score": 0.8, "reasoning": "Evidence B"},
                ],
            )
            result = validate_ranked_candidates(path, expected_rows=2)
        self.assertTrue(result["valid"], result["errors"])

    def test_rejects_missing_columns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ranked.csv"
            self._write(path, [{"candidate_id": "A", "rank": 1}], ["candidate_id", "rank"])
            result = validate_ranked_candidates(path)
        self.assertFalse(result["valid"])

    def test_rejects_duplicate_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ranked.csv"
            self._write(
                path,
                [
                    {"candidate_id": "A", "rank": 1, "score": 0.9, "reasoning": "One"},
                    {"candidate_id": "A", "rank": 2, "score": 0.8, "reasoning": "Two"},
                ],
            )
            result = validate_ranked_candidates(path)
        self.assertFalse(result["valid"])

    def test_rejects_invalid_score(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ranked.csv"
            self._write(
                path,
                [{"candidate_id": "A", "rank": 1, "score": 1.5, "reasoning": "Invalid"}],
            )
            result = validate_ranked_candidates(path)
        self.assertFalse(result["valid"])


if __name__ == "__main__":
    unittest.main()
