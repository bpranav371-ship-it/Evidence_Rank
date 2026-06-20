import tempfile
import unittest
from pathlib import Path

from src.diagram_generator import generate_diagrams


class DiagramGeneratorTests(unittest.TestCase):
    def test_creates_valid_mermaid_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = generate_diagrams(directory)
            contents = [path.read_text(encoding="utf-8") for path in paths.values()]
        self.assertEqual(len(paths), 3)
        self.assertTrue(all(content.startswith("flowchart") for content in contents))
        combined = "\n".join(contents)
        self.assertIn("Candidate Proof Graph", combined)
        self.assertIn("Honeypot Firewall", combined)
        self.assertIn("Final Score", combined)


if __name__ == "__main__":
    unittest.main()
