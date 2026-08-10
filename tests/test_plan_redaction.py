from __future__ import annotations

from opspilot.plan_redaction import redact_terraform_plan


def test_terraform_plan_redaction_removes_injected_identifiers() -> None:
    source = """
    project = "private-project"
    bucket = "private-state-bucket"
    parent = "billingAccounts/ABCDEF-123456-ABCDEF"
    target = "projects/123456789012"
    """

    redacted = redact_terraform_plan(
        source,
        {
            "private-project": "<project-id>",
            "private-state-bucket": "<state-bucket>",
        },
    )

    assert "private-project" not in redacted
    assert "private-state-bucket" not in redacted
    assert "ABCDEF-123456-ABCDEF" not in redacted
    assert "123456789012" not in redacted
    assert "<project-id>" in redacted
    assert "<state-bucket>" in redacted
