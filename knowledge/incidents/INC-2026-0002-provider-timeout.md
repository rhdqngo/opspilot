---
document_id: RCA-2026-0002
document_type: prior_rca
service: payment-service
version: "1.0"
owner: payments-team
updated_at: "2026-08-02T00:00:00Z"
review_due_at: "2027-02-01T00:00:00Z"
canonical_uri: opspilot://knowledge/RCA-2026-0002
tags: [rca, provider, latency, scn-002]
---
# RCA: provider dependency exceeded timeout

## Incident
The external payment provider exceeded the dependency timeout while internal database signals were normal.

## Evidence
Provider latency and UPSTREAM_PROVIDER_TIMEOUT supported the cause; pool metrics contradicted DB exhaustion.

## Resolution
The synthetic provider recovered without a retry or write-side action.

## Lesson
Separate external dependency latency from internal payment processing latency.

