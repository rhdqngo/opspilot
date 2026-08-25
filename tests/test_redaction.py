from __future__ import annotations

import pytest

from opspilot.redaction import redact_text


def test_NFR_012_redacts_email_token_and_card_like_values() -> None:
    raw = "user=demo@example.test token=fixture-token-12345678 card=4111    1111-1111 1111"
    redacted = redact_text(raw)
    assert "demo@example.test" not in redacted
    assert "fixture-token-12345678" not in redacted
    assert "4111" not in redacted
    assert redacted.count("[REDACTED_") == 3


def test_card_redaction_preserves_non_card_digit_runs_and_surrounding_spacing() -> None:
    raw = "short=1234 5678 long=12345678901234567890 done"

    assert redact_text(raw) == raw


@pytest.mark.parametrize(
    "raw",
    [
        "token=fixture-token-12345678",
        "token = fixture-token-12345678",
        "Bearer fixture-token-12345678",
        "api_key:fixture-token-12345678",
    ],
)
def test_token_redaction_supports_bounded_separator_forms(raw: str) -> None:
    assert redact_text(raw) == "[REDACTED_TOKEN]"
