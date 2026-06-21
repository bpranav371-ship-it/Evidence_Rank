from __future__ import annotations

import re


_PHRASES = (
    (r"\bsaal\s+ka\b", "years of"),
    (r"\bkaam\s+kiya\b", "worked"),
    (r"\bmaine\b", "i"),
    (r"\bbanaya\b|\bbanayi\b|\bbanaaya\b", "built"),
    (r"\bsikha\b|\bseekha\b", "learned"),
    (r"\btajurba\b", "experience"),
    (r"\bsaal\b", "years"),
    (r"\bkaam\b", "work"),
)
_NUMBERS = {
    "ek": "1", "do": "2", "teen": "3", "chaar": "4", "paanch": "5",
    "cheh": "6", "saat": "7", "aath": "8", "nau": "9", "das": "10",
}


def normalize_indian_text(text: str) -> str:
    value = str(text or "")
    for pattern, replacement in _PHRASES:
        value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
    for word, number in _NUMBERS.items():
        value = re.sub(rf"\b{word}\b", number, value, flags=re.IGNORECASE)
    return value
