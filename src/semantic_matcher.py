from __future__ import annotations

import math
from collections import Counter
from functools import lru_cache
from typing import Any

from .text_normalizer import clean_text
from .utils import clamp


@lru_cache(maxsize=16)
def _prepare_jd_vectors(
    jd_text: str,
    word_range: tuple[int, int],
    char_range: tuple[int, int],
    max_features: int,
) -> tuple[Any, dict[str, float], Any, dict[str, float]]:
    """Fit reusable local vectorizers once per JD instead of once per candidate."""
    from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore

    word_vectorizer = TfidfVectorizer(
        ngram_range=word_range,
        max_features=max_features,
        sublinear_tf=True,
    )
    char_vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=char_range,
        max_features=max_features,
        sublinear_tf=True,
    )
    word_jd = word_vectorizer.fit_transform((jd_text,))
    char_jd = char_vectorizer.fit_transform((jd_text,))
    word_weights = {
        term: float(word_jd[0, index])
        for term, index in word_vectorizer.vocabulary_.items()
    }
    char_weights = {
        term: float(char_jd[0, index])
        for term, index in char_vectorizer.vocabulary_.items()
    }
    return (
        word_vectorizer.build_analyzer(),
        word_weights,
        char_vectorizer.build_analyzer(),
        char_weights,
    )


def _cosine_from_prepared(
    analyzer: Any,
    jd_weights: dict[str, float],
    candidate_text: str,
) -> float:
    counts = Counter(term for term in analyzer(candidate_text) if term in jd_weights)
    if not counts:
        return 0.0
    candidate_weights = {
        term: 1.0 + math.log(count) if count > 0 else 0.0
        for term, count in counts.items()
    }
    norm = math.sqrt(sum(weight * weight for weight in candidate_weights.values()))
    if norm <= 0:
        return 0.0
    return sum(
        jd_weights[term] * weight for term, weight in candidate_weights.items()
    ) / norm


class SemanticMatcher:
    """Lightweight local similarity using word and character TF-IDF."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    def score_pair(self, jd_text: str, candidate_text: str) -> float:
        left = clean_text(jd_text)
        right = clean_text(candidate_text)
        if not left or not right:
            return 0.0
        try:
            word_range = tuple(self.config.get("word_ngram_range", (1, 2)))
            char_range = tuple(self.config.get("char_ngram_range", (3, 5)))
            maximum = int(self.config.get("max_features", 50000))
            maximum_chars = int(self.config.get("max_candidate_chars", 4000))
            bounded_right = right[:maximum_chars]
            word_analyzer, word_jd, char_analyzer, char_jd = _prepare_jd_vectors(
                left,
                (int(word_range[0]), int(word_range[1])),
                (int(char_range[0]), int(char_range[1])),
                maximum,
            )
            word_score = _cosine_from_prepared(word_analyzer, word_jd, bounded_right)
            char_score = _cosine_from_prepared(char_analyzer, char_jd, bounded_right)
            return clamp(0.55 * word_score + 0.45 * char_score)
        except (ImportError, ValueError, TypeError):
            return 0.0
