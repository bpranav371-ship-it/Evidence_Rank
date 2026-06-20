import json
import tempfile
import unittest
from pathlib import Path

from src.artifact_hasher import build_artifact_hashes


class ArtifactHasherTests(unittest.TestCase):
    def test_hashes_outputs_and_skips_private_or_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "ranked_candidates.csv").write_text("candidate_id\nA\n", encoding="utf-8")
            (output / "candidate_fingerprints.jsonl").write_text("private", encoding="utf-8")
            report = build_artifact_hashes(
                output,
                (
                    "ranked_candidates.csv",
                    "missing.csv",
                    "candidate_fingerprints.jsonl",
                    "data/input/candidates.jsonl",
                ),
            )
            payload = json.loads(
                (output / "final_artifact_hashes.json").read_text(encoding="utf-8")
            )
        self.assertEqual(len(payload["artifacts"]), 1)
        self.assertEqual(len(payload["artifacts"][0]["sha256"]), 64)
        self.assertIn("missing.csv", report["missing_files"])
        self.assertFalse(payload["raw_data_hashed"])
        self.assertFalse(payload["candidate_fingerprints_hashed"])


if __name__ == "__main__":
    unittest.main()
