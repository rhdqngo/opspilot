---
document_id: RB-ORD-001
document_type: runbook
service: order-service
version: "1.0"
owner: checkout-team
updated_at: "2026-08-01T00:00:00Z"
review_due_at: "2026-12-01T00:00:00Z"
canonical_uri: opspilot://knowledge/RB-ORD-001
tags: [cloud-run, capacity, scaling, scn-004]
---
# Cloud Run capacity lag

## Symptoms
Order latency rises during a bounded burst while downstream services remain healthy.

## Impact
Some synthetic checkout requests time out before capacity becomes available.

## Metrics
Compare instance count, pending request latency, concurrency, and request count.

## Log signatures
Look for deadline exceeded at order without matching payment or inventory domain errors.

## Recent changes
Inspect max instances, concurrency, CPU, memory, and revision traffic settings.

## Immediate mitigation
End the manual load window before proposing a reviewed capacity change.

## Safety conditions
Keep scale-to-zero, the two-instance cap, and private IAM unless separately approved.

## Recovery verification
Confirm latency returns to baseline after the bounded burst ends.

## Escalation
Escalate when normal traffic exceeds the documented two-instance MVP boundary.

