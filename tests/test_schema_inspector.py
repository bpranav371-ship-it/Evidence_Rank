import json
import tempfile
import unittest
from pathlib import Path

from src.schema_inspector import detect_format, inspect_schema


class SchemaInspectorTests(unittest.TestCase):
    def test_inspects_sample_jsonl_and_discovers_nested_fields(self) -> None:
        records = [
            {
                "candidate_id": "CAND_1",
                "profile": {"headline": "ML Engineer", "location": "Pune"},
                "skills": ["Python"],
                "redrob_signals": {"open_to_work_flag": True},
            },
            {"candidate_id": "CAND_2", "profile": {"summary": None}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.jsonl"
            path.write_text(
                "\n".join(json.dumps(record) for record in records),
                encoding="utf-8",
            )
            report = inspect_schema(path)

        self.assertEqual(report["detected_format"], "jsonl")
        self.assertEqual(report["record_count"], 2)
        self.assertIn("candidate_id", report["top_level_columns"])
        self.assertIn("profile.headline", report["available_field_paths"])
        self.assertIn("candidate_id", report["likely_fields"])
        self.assertIn("behavioral_signals", report["likely_fields"])

    def test_detect_format(self) -> None:
        self.assertEqual(detect_format("candidates.csv"), "csv")
        self.assertEqual(detect_format("candidates.ndjson"), "jsonl")


if __name__ == "__main__":
    unittest.main()
