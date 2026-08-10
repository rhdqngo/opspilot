from __future__ import annotations

from opspilot.plan_redaction import redact_terraform_plan


def test_terraform_plan_redaction_removes_injected_identifiers() -> None:
    image_uri = (
        "region-docker.pkg.dev/private-project/private-repo/"
        "demo@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )
    source = f"""
    project = "private-project"
    bucket = "private-state-bucket"
    recipient = "private-operator@example.invalid"
    image = "{image_uri}"
    parent = "billingAccounts/ABCDEF-123456-ABCDEF"
    target = "projects/123456789012"
    """

    redacted = redact_terraform_plan(
        source,
        {
            "private-project": "<project-id>",
            "private-state-bucket": "<state-bucket>",
            "private-operator@example.invalid": "<budget-email>",
            image_uri: "<demo-image-uri>",
        },
    )

    assert "private-project" not in redacted
    assert "private-state-bucket" not in redacted
    assert "private-operator@example.invalid" not in redacted
    assert "private-repo" not in redacted
    assert "ABCDEF-123456-ABCDEF" not in redacted
    assert "123456789012" not in redacted
    assert "<project-id>" in redacted
    assert "<state-bucket>" in redacted
    assert "<budget-email>" in redacted
    assert "<demo-image-uri>" in redacted
