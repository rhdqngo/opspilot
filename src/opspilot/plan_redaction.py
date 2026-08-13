"""Sanitize Terraform plan text before storing it as a CI artifact."""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Mapping, Sequence

REDACTION_ENV = {
    "OPSPILOT_REDACT_PROJECT_ID": "<project-id>",
    "OPSPILOT_REDACT_PROJECT_NUMBER": "<project-number>",
    "OPSPILOT_REDACT_BILLING_ACCOUNT_ID": "<billing-account-id>",
    "OPSPILOT_REDACT_STATE_BUCKET": "<state-bucket>",
    "OPSPILOT_REDACT_BUDGET_EMAIL": "<budget-email>",
    "OPSPILOT_REDACT_DEMO_IMAGE_URI": "<demo-image-uri>",
    "OPSPILOT_REDACT_INVESTIGATION_IMAGE_URI": "<investigation-image-uri>",
    "OPSPILOT_REDACT_REMEDIATION_IMAGE_URI": "<remediation-image-uri>",
    "OPSPILOT_REDACT_REMEDIATION_APPROVER_GROUP": "<remediation-approver-group>",
}


def redact_terraform_plan(text: str, values: Mapping[str, str]) -> str:
    """Replace provided identifiers plus standard GCP resource-name forms."""

    redacted = text
    for value, placeholder in sorted(values.items(), key=lambda item: len(item[0]), reverse=True):
        if value:
            redacted = redacted.replace(value, placeholder)
    redacted = re.sub(r"billingAccounts/[A-Za-z0-9-]+", "billingAccounts/<redacted>", redacted)
    redacted = re.sub(r"projects/[0-9]{6,}", "projects/<redacted-number>", redacted)
    return redacted


def main(argv: Sequence[str] | None = None) -> int:
    if argv:
        raise ValueError(
            "plan redaction accepts input only through stdin and environment variables"
        )
    replacements = {
        os.environ.get(name, ""): placeholder for name, placeholder in REDACTION_ENV.items()
    }
    sys.stdout.write(redact_terraform_plan(sys.stdin.read(), replacements))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
