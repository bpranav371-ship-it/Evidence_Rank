import json
import tempfile
import unittest
from pathlib import Path

from src.reproducibility import build_reproducibility_manifest


class ReproducibilityTests(unittest.TestCase):
    def test_manifest_is_safe_and_handles_missing_git(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "output"
            (root / "requirements.txt").write_text("pytest\n", encoding="utf-8")
            (root / "config.yaml").write_text("batch_size: 1000\n", encoding="utf-8")
            manifest = build_reproducibility_manifest(
                root,
                output,
                {
                    "reproducibility": {
                        "repository_url": "https://example.test/repo.git",
                        "random_seed": 42,
                    }
                },
            )
            payload = json.loads(
                (output / "reproducibility_manifest.json").read_text(encoding="utf-8")
            )
        self.assertEqual(payload["repository_url"], "https://example.test/repo.git")
        self.assertIn("requirements_hash", payload)
        self.assertIn("config_hash", payload)
        self.assertNotIn("candidate_data", payload)
        self.assertIsNone(manifest["current_git_commit_hash"])


if __name__ == "__main__":
    unittest.main()
