import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from src.deck_materials import build_deck_materials
from src.judge_packet import build_judge_packet


class JudgePacketTests(unittest.TestCase):
    def test_packet_includes_docs_and_excludes_raw_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = root / "docs"
            output = root / "data" / "output"
            input_dir = root / "data" / "input"
            output.mkdir(parents=True)
            input_dir.mkdir(parents=True)
            build_deck_materials(docs)
            (output / "top10_explanation_cards.md").write_text("# Cards\n", encoding="utf-8")
            (output / "top10_explanation_cards.json").write_text(
                json.dumps({"cards": []}), encoding="utf-8"
            )
            (input_dir / "candidates.jsonl").write_text("private", encoding="utf-8")
            manifest, paths = build_judge_packet(docs, output)
            with zipfile.ZipFile(paths["demo_packet_zip"]) as archive:
                names = set(archive.namelist())
            self.assertTrue(paths["judge_demo_packet"].exists())
            self.assertTrue(paths["demo_packet_manifest"].exists())
            self.assertIn("docs/approach_deck.md", names)
            self.assertIn("data/output/top10_explanation_cards.md", names)
            self.assertNotIn("candidates.jsonl", names)
            self.assertFalse(manifest["raw_data_included"])


if __name__ == "__main__":
    unittest.main()
