import json
import tempfile
import unittest
from pathlib import Path

from src.jd_parser import parse_jd_text
from src.runtime_profiler import profile_ranking_runtime


class RuntimeProfilerTests(unittest.TestCase):
    def test_runtime_report_contains_runtime_and_memory_keys(self) -> None:
        candidate = {
            "candidate_id": "A",
            "raw_text_compact": "python retrieval production",
            "claimed_skills": ["Python", "Retrieval"],
            "technical_terms": ["Python", "Retrieval"],
            "current_title": "ML Engineer",
            "years_of_experience": 4,
            "career_evidence_text": "Deployed a Python retrieval API.",
            "education_text": "",
            "behavioral_signal_summary": {},
            "availability_signal_summary": {},
            "anomaly_flags": [],
            "missing_fields": [],
            "keyword_density_score": 0.03,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "fingerprints.jsonl"
            source.write_text(json.dumps(candidate) + "\n", encoding="utf-8")
            report = profile_ranking_runtime(
                source,
                parse_jd_text("Python retrieval production engineer"),
                root,
                1,
                {},
                {"risk_rerank_pool_size": 1},
                {"calibration_pool_size": 1},
            )
            self.assertTrue((root / "runtime_profile_report.json").exists())
        self.assertEqual(report["candidate_count"], 1)
        self.assertIn("ranking_runtime_seconds", report)
        self.assertIn("peak_rss_memory_mb", report)
        self.assertIn("available_ram_mb", report)


if __name__ == "__main__":
    unittest.main()
