"""Small deterministic redaction helpers used before evidence is persisted."""

from __future__ import annotations

import re

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
TOKEN_PATTERN = re.compile(r"\b(?:token|bearer|api[_-]?key)\s*[:=]?\s*[A-Za-z0-9._-]{8,}\b", re.I)
CARD_PATTERN = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")


def redact_text(value: str) -> str:
    value = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", value)
    value = TOKEN_PATTERN.sub("[REDACTED_TOKEN]", value)
    return CARD_PATTERN.sub("[REDACTED_CARD]", value)
