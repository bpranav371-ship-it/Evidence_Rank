import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.candidate_profiler import CandidateProfiler
from src.feature_store import IncrementalFeatureStore


REQUIRED_KEYS = {
    "candidate_id",
    "raw_text_compact",
    "claimed_skills",
    "technical_terms",
    "current_title",
    "years_of_experience",
    "location",
    "career_evidence_text",
    "education_text",
    "behavioral_signal_summary",
    "availability_signal_summary",
    "anomaly_flags",
    "missing_fields",
    "profile_completeness_score",
    "keyword_density_score",
    "skill_evidence_hint_score",
}


class CandidateProfilerTests(unittest.TestCase):
    def test_profiler_produces_required_keys_and_handles_nulls(self) -> None:
        record = {
            "candidate_id": None,
            "profile": {
                "headline": "ML Engineer using Python",
                "summary": None,
                "current_title": "Machine Learning Engineer",
                "years_of_experience": 6,
                "location": "Pune",
            },
            "skills": [
                {"name": "Python", "duration_months": 48},
                {"name": "Embeddings"},
            ],
            "career_history": [
                {
                    "title": "ML Engineer",
                    "description": "Deployed Python embedding retrieval services.",
                }
            ],
            "education": None,
            "redrob_signals": {
                "recruiter_response_rate": 0.8,
                "notice_period_days": 30,
                "open_to_work_flag": True,
            },
        }
        fingerprint = CandidateProfiler().profile(record, row_number=7)

        self.assertTrue(REQUIRED_KEYS.issubset(set(fingerprint)))
        self.assertEqual(fingerprint["candidate_id"], "GENERATED_000000007")
        self.assertIn("missing_candidate_id", fingerprint["anomaly_flags"])
        self.assertIn("Python", fingerprint["technical_terms"])
        self.assertGreater(fingerprint["skill_evidence_hint_score"], 0)
        self.assertGreaterEqual(fingerprint["profile_completeness_score"], 0)
        self.assertLessEqual(fingerprint["profile_completeness_score"], 1)

    def test_feature_store_writes_each_record_incrementally(self) -> None:
        fingerprint = CandidateProfiler().profile({"id": "one"}, row_number=1)
        with tempfile.TemporaryDirectory() as directory:
            with IncrementalFeatureStore(directory) as store:
                store.write_fingerprint(fingerprint)
                store._handle.flush()  # Verify visibility before store finalization.
                lines = store.fingerprints_path.read_text(encoding="utf-8").splitlines()
            decoded = json.loads(lines[0])

        self.assertEqual(len(lines), 1)
        self.assertEqual(decoded["candidate_id"], "one")

    def test_cli_limit(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "candidates.jsonl"
            output_dir = root / "output"
            input_path.write_text(
                "\n".join(json.dumps({"id": index}) for index in range(5)),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "run.py"),
                    "--input",
                    str(input_path),
                    "--output-dir",
                    str(output_dir),
                    "--limit",
                    "2",
                ],
                cwd=project_root,
                capture_output=True,
                text=True,
                check=False,
            )
            summary = json.loads(
                (output_dir / "profiler_summary.json").read_text(encoding="utf-8")
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(summary["total_candidates_processed"], 2)
        self.assertIn("schema_health", summary)
        self.assertIsNotNone(summary["schema_health"]["warning"])


if __name__ == "__main__":
    unittest.main()
