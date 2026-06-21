import unittest

from src.text_normalizer import clean_text
from src.transliterator import normalize_indian_text


class TransliteratorTests(unittest.TestCase):
    def test_hinglish_experience_normalization(self) -> None:
        text = clean_text("maine 3 saal ka kaam kiya python mein")
        self.assertIn("3 years", text)
        self.assertTrue("work" in text or "worked" in text)

    def test_rag_is_preserved_and_banaya_maps_to_built(self) -> None:
        text = clean_text("RAG system banaya")
        self.assertIn("rag system built", text)

    def test_empty_is_safe(self) -> None:
        self.assertEqual(normalize_indian_text(""), "")


if __name__ == "__main__":
    unittest.main()
