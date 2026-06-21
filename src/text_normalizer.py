from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

from .transliterator import normalize_indian_text


_SPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s+#./-]+", flags=re.UNICODE)
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[+#.][a-z0-9]+)*", flags=re.IGNORECASE)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = normalize_indian_text(unicodedata.normalize("NFKC", str(value))).lower()
    text = text.replace("_", " ").replace("|", " ").replace("—", "-").replace("–", "-")
    text = _PUNCT_RE.sub(" ", text)
    return _SPACE_RE.sub(" ", text).strip()


def flatten_value(value: Any) -> str:
    """Turn nested profile content into deterministic searchable text."""
    parts: list[str] = []

    def visit(item: Any) -> None:
        if item is None:
            return
        if isinstance(item, dict):
            for key in sorted(item, key=lambda current: str(current).lower()):
                visit(item[key])
        elif isinstance(item, (list, tuple, set)):
            for child in item:
                visit(child)
        elif isinstance(item, bool):
            parts.append("true" if item else "false")
        else:
            cleaned = clean_text(item)
            if cleaned:
                parts.append(cleaned)

    visit(value)
    return " ".join(parts)


def tokenize_simple(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(clean_text(text))]


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def safe_get(
    record: dict[str, Any] | None,
    possible_keys: Iterable[str],
    default: Any = None,
) -> Any:
    """Case-insensitive key lookup supporting direct and dotted paths."""
    if not isinstance(record, dict):
        return default

    for possible_key in possible_keys:
        if "." in possible_key:
            current: Any = record
            found = True
            for part in possible_key.split("."):
                if not isinstance(current, dict):
                    found = False
                    break
                target = _normalized_key(part)
                match = next(
                    (key for key in current if _normalized_key(str(key)) == target),
                    None,
                )
                if match is None:
                    found = False
                    break
                current = current[match]
            if found and current is not None:
                return current
        else:
            target = _normalized_key(possible_key)
            for key, value in record.items():
                if _normalized_key(str(key)) == target and value is not None:
                    return value
    return default
