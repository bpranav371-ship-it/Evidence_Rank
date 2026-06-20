import csv
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from src.submission_packager import build_submission_package


class SubmissionPackagerTests(unittest.TestCase):
    def test_package_includes_required_files_and_excludes_raw_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "data" / "output"
            input_dir = root / "data" / "input"
            output.mkdir(parents=True)
            input_dir.mkdir(parents=True)
            with (output / "ranked_candidates.csv").open(
                "w", encoding="utf-8", newline=""
            ) as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=("candidate_id", "rank", "score", "reasoning")
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "candidate_id": "A",
                        "rank": 1,
                        "score": 0.9,
                        "reasoning": "Specific evidence-backed production retrieval profile.",
                    }
                )
            (output / "score_breakdown.csv").write_text(
                "candidate_id,rank,final_score\nA,1,0.9\n", encoding="utf-8"
            )
            (output / "final_submission_safety_report.json").write_text(
                json.dumps({"passed": True}), encoding="utf-8"
            )
            (output / "reproducibility_manifest.json").write_text(
                json.dumps({"current_git_commit_hash": "abc123"}), encoding="utf-8"
            )
            (input_dir / "candidates.jsonl").write_text("private\n", encoding="utf-8")

            manifest, paths = build_submission_package(root, output, {}, top_k=1)
            with zipfile.ZipFile(paths["submission_package"]) as archive:
                names = set(archive.namelist())
            self.assertTrue(paths["submission_package"].exists())
            self.assertIn("ranked_candidates.csv", names)
            self.assertIn("final_submission_manifest.json", names)
            self.assertNotIn("candidates.jsonl", names)
            self.assertEqual(manifest["ranked_csv_rows"], 1)


if __name__ == "__main__":
    unittest.main()
