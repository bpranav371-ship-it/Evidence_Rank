import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.candidate_loader import CandidateLoader


class CandidateLoaderTests(unittest.TestCase):
    def test_jsonl_streaming_skips_malformed_rows_and_honors_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidates.jsonl"
            path.write_text(
                '{"candidate_id":"A"}\nnot json\n{"candidate_id":"B"}\n'
                '{"candidate_id":"C"}\n',
                encoding="utf-8",
            )
            loader = CandidateLoader(path, limit=2, progress_every=0)
            records = list(loader)

        self.assertEqual([record["candidate_id"] for record in records], ["A", "B"])
        self.assertEqual(loader.stats.errors, 1)
        self.assertEqual(loader.stats.records_yielded, 2)

    def test_csv_loader_handles_missing_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candidates.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["id", "headline"])
                writer.writeheader()
                writer.writerow({"id": "1", "headline": ""})
            records = list(CandidateLoader(path, progress_every=0))

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["id"], "1")


if __name__ == "__main__":
    unittest.main()
