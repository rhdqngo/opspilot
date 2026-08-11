---
document_id: ARC-001
document_type: architecture
service: shared
version: "1.0"
owner: platform-team
updated_at: "2026-08-03T00:00:00Z"
review_due_at: "2027-02-01T00:00:00Z"
canonical_uri: opspilot://knowledge/ARC-001
tags: [architecture, services, evidence]
---
# OpsPilot synthetic system overview

## Components
Private order, payment, and inventory Cloud Run services share one immutable image but use distinct identities.

## Investigation boundary
OpsPilot correlates read-only logs, metrics, revisions, and untrusted knowledge into typed evidence.

## Safety boundary
The MVP has no public principal, runtime project role, service-account key, or remediation executor.

