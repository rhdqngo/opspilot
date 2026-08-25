from __future__ import annotations

from opspilot.plan_redaction import redact_terraform_plan


def test_terraform_plan_redaction_removes_injected_identifiers() -> None:
    demo_image_uri = (
        "region-docker.pkg.dev/private-project/private-repo/"
        "demo@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )
    investigation_image_uri = (
        "region-docker.pkg.dev/private-project/private-repo/"
        "investigation@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    )
    remediation_image_uri = (
        "region-docker.pkg.dev/private-project/private-repo/"
        "remediation@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    )
    workload_identity_provider = (
        "projects/123456789012/locations/global/workloadIdentityPools/private-pool/"
        "providers/private-provider"
    )
    service_account = "terraform-plan@private-project.iam.gserviceaccount.com"
    source = f"""
    project = "private-project"
    bucket = "private-state-bucket"
    recipient = "private-operator@example.invalid"
    investigator = "private-investigator@example.invalid"
    approver = "private-approvers@example.invalid"
    service_account = "{service_account}"
    workload_identity_provider = "{workload_identity_provider}"
    demo_image = "{demo_image_uri}"
    investigation_image = "{investigation_image_uri}"
    remediation_image = "{remediation_image_uri}"
    parent = "billingAccounts/ABCDEF-123456-ABCDEF"
    target = "projects/123456789012"
    endpoint = "https://private-service-abcdef-an.a.run.app/internal"
    """

    redacted = redact_terraform_plan(
        source,
        {
            "private-project": "<project-id>",
            "private-state-bucket": "<state-bucket>",
            "private-operator@example.invalid": "<budget-email>",
            "private-investigator@example.invalid": "<investigator-operator-email>",
            "private-approvers@example.invalid": "<remediation-approver-group>",
            workload_identity_provider: "<workload-identity-provider>",
            service_account: "<terraform-plan-service-account>",
            demo_image_uri: "<demo-image-uri>",
            investigation_image_uri: "<investigation-image-uri>",
            remediation_image_uri: "<remediation-image-uri>",
        },
    )

    assert "private-project" not in redacted
    assert "private-state-bucket" not in redacted
    assert "private-operator@example.invalid" not in redacted
    assert "private-investigator@example.invalid" not in redacted
    assert "private-approvers@example.invalid" not in redacted
    assert "private-pool" not in redacted
    assert service_account not in redacted
    assert "private-repo" not in redacted
    assert "ABCDEF-123456-ABCDEF" not in redacted
    assert "123456789012" not in redacted
    assert "private-service-abcdef-an.a.run.app" not in redacted
    assert "<project-id>" in redacted
    assert "<state-bucket>" in redacted
    assert "<budget-email>" in redacted
    assert "<demo-image-uri>" in redacted
    assert "<investigation-image-uri>" in redacted
    assert "<remediation-image-uri>" in redacted
    assert "<remediation-approver-group>" in redacted
    assert "<workload-identity-provider>" in redacted
    assert "<terraform-plan-service-account>" in redacted


def test_terraform_plan_redaction_has_safe_fallbacks_without_injected_values() -> None:
    source = """
    parent = "projects/actual-looking-project/locations/asia-northeast3"
    service_account = "runtime@actual-looking-project.iam.gserviceaccount.com"
    image = "asia-northeast3-docker.pkg.dev/actual-project/apps/api@sha256:abc123"
    endpoint = "https://service-abcdef-an.a.run.app/private"
    operator = "operator@actual-domain.example"
    """

    redacted = redact_terraform_plan(source, {})

    for forbidden in (
        "actual-looking-project",
        "runtime@",
        "actual-project",
        "service-abcdef-an.a.run.app",
        "operator@actual-domain.example",
    ):
        assert forbidden not in redacted
