"""Small deterministic redaction helpers used before evidence is persisted."""

from __future__ import annotations

import re

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
TOKEN_WITH_SEPARATOR_PATTERN = re.compile(
    r"\b(?:token|bearer|api[_-]?key)\s*[:=]\s*[A-Za-z0-9._-]{8,}\b", re.I
)
TOKEN_WITH_SPACE_PATTERN = re.compile(
    r"\b(?:token|bearer|api[_-]?key)\s+[A-Za-z0-9._-]{8,}\b", re.I
)


def _redact_card_like_values(value: str) -> str:
    """Replace bounded digit runs in one pass without regex backtracking."""

    output: list[str] = []
    index = 0
    while index < len(value):
        if not value[index].isdigit():
            output.append(value[index])
            index += 1
            continue

        start = index
        digit_count = 0
        while index < len(value) and (value[index].isdigit() or value[index] in " -"):
            if value[index].isdigit():
                digit_count += 1
            index += 1

        content_end = index
        while content_end > start and value[content_end - 1] in " -":
            content_end -= 1

        if 13 <= digit_count <= 19:
            output.append("[REDACTED_CARD]")
        else:
            output.append(value[start:content_end])
        output.append(value[content_end:index])

    return "".join(output)


def redact_text(value: str) -> str:
    value = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", value)
    value = TOKEN_WITH_SEPARATOR_PATTERN.sub("[REDACTED_TOKEN]", value)
    value = TOKEN_WITH_SPACE_PATTERN.sub("[REDACTED_TOKEN]", value)
    return _redact_card_like_values(value)
