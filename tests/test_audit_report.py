import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.audit_report import HoneypotAuditWriter


class AuditReportTests(unittest.TestCase):
    def test_creates_all_audit_files_and_summary_keys(self) -> None:
        report = {
            "candidate_id": "CAND_1",
            "risk_score": 0.6,
            "risk_level": "high",
            "disqualified": False,
            "risk_flags": ["buzzword_stuffing"],
            "severe_flags": [],
            "warning_flags": ["buzzword_stuffing"],
            "penalty_recommendation": 0.15,
            "top_reasons": ["Weak evidence alignment."],
        }
        candidate = {
            "candidate_id": "CAND_1",
            "original_rank": 1,
            "adjusted_rank": 2,
            "rank": 2,
            "risk_report": report,
            "score": {"final_score": 0.8, "risk_adjusted_score": 0.65},
        }
        with tempfile.TemporaryDirectory() as directory:
            with HoneypotAuditWriter(directory) as audit:
                audit.record(report)
                summary = audit.finalize([candidate])
                paths = audit.output_paths

            audit_payload = json.loads(paths["honeypot_audit"].read_text(encoding="utf-8"))
            with paths["honeypot_flags"].open(encoding="utf-8", newline="") as handle:
                flag_rows = list(csv.DictReader(handle))
            with paths["rerank_audit_top100"].open(encoding="utf-8", newline="") as handle:
                rerank_rows = list(csv.DictReader(handle))
            self.assertTrue(all(path.exists() for path in paths.values()))
            self.assertEqual(len(flag_rows), 1)
            self.assertEqual(len(rerank_rows), 1)
            for key in (
                "total_candidates_scored",
                "total_candidates_flagged",
                "high_risk_count",
                "top_flag_counts",
                "top_10_risk_summary",
            ):
                self.assertIn(key, summary)
                self.assertIn(key, audit_payload)

    def test_deep_report_replaces_lightweight_summary(self) -> None:
        light = {
            "candidate_id": "CAND_2",
            "risk_score": 0.1,
            "risk_level": "low",
            "disqualified": False,
            "risk_flags": ["missing_availability_signals"],
            "severe_flags": [],
            "warning_flags": ["missing_availability_signals"],
            "penalty_recommendation": 0.01,
            "top_reasons": ["Signals missing."],
        }
        deep = {
            "candidate_id": "CAND_2",
            "risk_score": 0.8,
            "risk_level": "severe",
            "disqualified": True,
            "risk_flags": ["empty_profile_text"],
            "severe_flags": ["empty_profile_text"],
            "warning_flags": [],
            "penalty_recommendation": 0.5,
            "top_reasons": ["Profile is empty."],
        }
        with tempfile.TemporaryDirectory() as directory:
            with HoneypotAuditWriter(directory) as audit:
                audit.record(light)
                audit.replace_with_deep_report(light, deep)
                summary = audit.finalize([])
                with audit.flags_path.open(encoding="utf-8", newline="") as handle:
                    rows = list(csv.DictReader(handle))

        self.assertEqual(summary["severe_risk_count"], 1)
        self.assertEqual(summary["disqualified_count"], 1)
        self.assertEqual(rows[0]["risk_flags"], "empty_profile_text")


if __name__ == "__main__":
    unittest.main()
