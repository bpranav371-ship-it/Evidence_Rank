import copy
import json
import tempfile
import unittest
from pathlib import Path

from src.jd_parser import parse_jd_text
from src.weight_sensitivity import VARIANTS, run_weight_sensitivity


class WeightSensitivityTests(unittest.TestCase):
    def test_variants_run_without_mutating_config(self) -> None:
        candidate = {
            "candidate_id": "A",
            "raw_text_compact": "python retrieval ranking production docker",
            "claimed_skills": ["Python", "Retrieval", "Ranking", "Docker"],
            "technical_terms": ["Python", "Retrieval", "Ranking", "Docker"],
            "current_title": "ML Engineer",
            "years_of_experience": 5,
            "career_evidence_text": "Built and deployed retrieval ranking APIs.",
            "education_text": "",
            "behavioral_signal_summary": {},
            "availability_signal_summary": {},
            "anomaly_flags": [],
            "missing_fields": [],
            "keyword_density_score": 0.04,
        }
        ranking = {"strict_rerank_pool_size": 2}
        firewall = {"risk_rerank_pool_size": 2}
        calibration = {"calibration_pool_size": 2}
        originals = copy.deepcopy((ranking, firewall, calibration))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "fingerprints.jsonl"
            source.write_text(json.dumps(candidate) + "\n", encoding="utf-8")
            report, paths = run_weight_sensitivity(
                source,
                parse_jd_text("Python retrieval ranking production engineer"),
                root,
                1,
                ranking,
                firewall,
                calibration,
            )
            self.assertTrue(paths["weight_sensitivity_report"].exists())
            self.assertTrue(paths["weight_sensitivity_summary"].exists())
        self.assertEqual(set(report["variants"]), set(VARIANTS))
        self.assertIn("average_proof_alignment_top100", report["variants"]["default"])
        self.assertEqual((ranking, firewall, calibration), originals)


if __name__ == "__main__":
    unittest.main()
