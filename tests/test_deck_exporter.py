import tempfile
import unittest
import zipfile
from pathlib import Path

from src.deck_exporter import export_deck


class DeckExporterTests(unittest.TestCase):
    def test_creates_pptx_with_expected_title_without_private_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = root / "docs"
            output = root / "output"
            docs.mkdir()
            result = export_deck(docs, output, {}, output_format="pptx")
            pptx = Path(result["created_files"]["pptx"])
            with zipfile.ZipFile(pptx) as archive:
                slide = archive.read("ppt/slides/slide1.xml").decode("utf-8")
                names = archive.namelist()
            self.assertTrue(pptx.exists())
            self.assertIn("EvidenceRank", slide)
            self.assertEqual(len([name for name in names if name.startswith("ppt/slides/slide") and name.endswith(".xml")]), 12)
            self.assertNotIn("candidate_fingerprints", slide)

    def test_pdf_export_creates_pdf_or_instruction_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            result = export_deck(Path(directory) / "docs", output, {}, output_format="pdf")
            created = result["created_files"]
            self.assertTrue("pdf" in created or "pdf_instructions" in created)
            self.assertTrue(Path(next(iter(created.values()))).exists())


if __name__ == "__main__":
    unittest.main()
