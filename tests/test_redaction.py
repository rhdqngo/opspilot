from __future__ import annotations

from opspilot.redaction import redact_text


def test_NFR_012_redacts_email_token_and_card_like_values() -> None:
    raw = "user=demo@example.test token=fixture-token-12345678 card=4111 1111 1111 1111"
    redacted = redact_text(raw)
    assert "demo@example.test" not in redacted
    assert "fixture-token-12345678" not in redacted
    assert "4111" not in redacted
    assert redacted.count("[REDACTED_") == 3
