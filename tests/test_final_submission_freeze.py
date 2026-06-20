import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from src.artifact_hasher import build_artifact_hashes
from src.final_submission_freeze import (
    build_final_submission_bundle,
    build_freeze_report,
    write_final_guides,
)


class FinalSubmissionFreezeTests(unittest.TestCase):
    def test_creates_guides_bundle_and_excludes_private_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "data" / "output"
            input_dir = root / "data" / "input"
            output.mkdir(parents=True)
            input_dir.mkdir(parents=True)
            for filename in (
                "ranked_candidates.csv",
                "score_breakdown.csv",
                "EvidenceRank_Approach_Deck.pptx",
                "final_submission_safety_report.json",
                "reproducibility_manifest.json",
            ):
                (output / filename).write_text("safe", encoding="utf-8")
            (output / "candidate_fingerprints.jsonl").write_text("private", encoding="utf-8")
            (input_dir / "candidates.jsonl").write_text("private", encoding="utf-8")
            guides = write_final_guides(output)
            build_artifact_hashes(output)
            manifest, paths = build_final_submission_bundle(
                output,
                {"submission_freeze": {"final_bundle_name": "final_submission_bundle.zip"}},
                top_k=1,
            )
            with zipfile.ZipFile(paths["final_submission_bundle"]) as archive:
                names = set(archive.namelist())
            self.assertTrue(guides["one_page_summary"].exists())
            self.assertTrue(guides["final_submission_guide"].exists())
            self.assertIn("ranked_candidates.csv", names)
            self.assertNotIn("candidate_fingerprints.jsonl", names)
            self.assertNotIn("candidates.jsonl", names)
            self.assertFalse(manifest["raw_data_included"])

    def test_freeze_report_has_required_status_keys_and_missing_deck_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "output"
            output.mkdir()
            report = build_freeze_report(
                root,
                output,
                {
                    "submission_freeze": {
                        "require_ranked_candidates": False,
                        "require_score_breakdown": False,
                        "require_deck": True,
                        "require_safety_report": False,
                        "require_reproducibility_manifest": False,
                    }
                },
                validation={"errors": []},
                safety={"blocking_errors": []},
                judge_check={"blocking_errors": []},
                bundle_manifest={},
            )
            payload = json.loads(
                (output / "final_submission_freeze_report.json").read_text(encoding="utf-8")
            )
        self.assertFalse(report["passed"])
        self.assertIn("blocking_errors", payload)
        self.assertIn("warnings", payload)
        self.assertTrue(any("Deck" in error or "deck" in error for error in report["blocking_errors"]))


if __name__ == "__main__":
    unittest.main()
