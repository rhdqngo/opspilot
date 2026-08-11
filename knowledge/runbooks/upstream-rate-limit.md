---
document_id: RB-PAY-003
document_type: runbook
service: payment-service
version: "1.0"
owner: payments-team
updated_at: "2026-08-01T00:00:00Z"
review_due_at: "2026-12-01T00:00:00Z"
canonical_uri: opspilot://knowledge/RB-PAY-003
tags: [rate-limit, upstream, cache-warning, scn-005]
---
# Upstream payment rate limiting

## Symptoms
Provider calls return a rate-limit response while an unrelated cache warning appears nearby.

## Impact
Payment authorization is temporarily unavailable and orders fail safely.

## Metrics
Compare upstream response codes and request rate; do not infer cause from warning volume alone.

## Log signatures
Look for UPSTREAM_RATE_LIMIT and treat CACHE_REFRESH_WARNING as contradictory evidence.

## Recent changes
Check bounded load rate and provider quota configuration.

## Immediate mitigation
Stop synthetic load and wait for the documented provider window; do not retry writes automatically.

## Safety conditions
Do not clear caches or change quota without evidence and approval.

## Recovery verification
Confirm the rate-limit code disappears and a bounded order succeeds.

## Escalation
Escalate to the provider owner when throttling persists below the expected request rate.

