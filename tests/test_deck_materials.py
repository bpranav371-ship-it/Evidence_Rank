import tempfile
import unittest
from pathlib import Path

from src.deck_materials import build_deck_materials


class DeckMaterialsTests(unittest.TestCase):
    def test_creates_deck_and_judge_documents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = build_deck_materials(directory)
            deck = paths["approach_deck"].read_text(encoding="utf-8")
            faq = paths["faq_for_judges"].read_text(encoding="utf-8")
            for name in (
                "approach_deck", "demo_script", "judge_walkthrough",
                "submission_checklist", "faq_for_judges",
            ):
                self.assertTrue(paths[name].exists())
            self.assertEqual(deck.count("## Slide "), 12)
            self.assertIn("Is this just keyword matching?", faq)
            self.assertIn("Does it run under CPU-only constraints?", faq)


if __name__ == "__main__":
    unittest.main()
