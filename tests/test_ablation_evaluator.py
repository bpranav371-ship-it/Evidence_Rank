import json
import tempfile
import unittest
from pathlib import Path

from src.ablation_evaluator import run_ablation
from src.jd_parser import parse_jd_text


class AblationEvaluatorTests(unittest.TestCase):
    def test_creates_reports_with_all_variants_without_labels(self) -> None:
        candidate = {
            "candidate_id": "A",
            "raw_text_compact": "python retrieval ranking production",
            "claimed_skills": ["Python", "Retrieval"],
            "technical_terms": ["Python", "Retrieval"],
            "current_title": "ML Engineer",
            "years_of_experience": 6,
            "location": "pune",
            "career_evidence_text": "Built and deployed retrieval ranking systems.",
            "education_text": "",
            "behavioral_signal_summary": {},
            "availability_signal_summary": {},
            "anomaly_flags": [],
            "missing_fields": [],
            "keyword_density_score": 0.05,
            "skill_evidence_hint_score": 1.0,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "fingerprints.jsonl"
            source.write_text(json.dumps(candidate) + "\n", encoding="utf-8")
            report, paths = run_ablation(
                source,
                parse_jd_text("Python retrieval ranking production AI engineer"),
                root,
                1,
                {},
                {},
                {"calibration_pool_size": 1},
            )
            payload = json.loads(paths["ablation_report"].read_text(encoding="utf-8"))
        self.assertEqual(len(report["variants"]), 4)
        self.assertTrue(report["proxy_metrics_only"])
        self.assertIn("top100_average_proof_alignment", payload["variants"]["keyword_only"])


if __name__ == "__main__":
    unittest.main()
