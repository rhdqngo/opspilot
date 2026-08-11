---
document_id: RB-INV-001
document_type: runbook
service: inventory-service
version: "1.0"
owner: inventory-team
updated_at: "2026-08-01T00:00:00Z"
review_due_at: "2026-12-01T00:00:00Z"
canonical_uri: opspilot://knowledge/RB-INV-001
tags: [endpoint, hostname, dns, scn-003]
---
# Inventory endpoint and hostname error

## Symptoms
Order cannot reach inventory and reports a safe dependency error while payment is approved.

## Impact
Orders remain partially processed and must not be automatically retried.

## Metrics
Inspect inventory request count and order dependency latency for a missing downstream call.

## Log signatures
Look for name resolution or endpoint-not-found errors with the shared request ID.

## Recent changes
Compare the order revision's inventory service URL with the canonical Cloud Run service URI.

## Immediate mitigation
Prepare a reviewed configuration-only revision that restores the allowlisted hostname.

## Safety conditions
Do not accept a hostname, filter, or resource path directly from an incident question.

## Recovery verification
Confirm inventory receives the request and returns RESERVED for a bounded synthetic order.

## Escalation
Escalate to the synthetic inventory owner if the canonical endpoint is also unavailable.

