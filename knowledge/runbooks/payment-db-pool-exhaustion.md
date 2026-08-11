---
document_id: RB-PAY-001
document_type: runbook
service: payment-service
version: "1.0"
owner: payments-team
updated_at: "2026-08-01T00:00:00Z"
review_due_at: "2026-12-01T00:00:00Z"
canonical_uri: opspilot://knowledge/RB-PAY-001
tags: [database, connection-pool, timeout, scn-001]
---
# Payment database connection pool exhaustion

## Symptoms
Payment authorizations return DB_POOL_TIMEOUT while order requests fail with a downstream 502.

## Impact
Checkout cannot complete even though inventory remains healthy.

## Metrics
Compare payment latency, 5xx count, and active database connection saturation.

## Log signatures
Look for the exact synthetic code DB_POOL_TIMEOUT and correlate its request and trace IDs.

## Recent changes
Inspect the payment revision for a reduction in the configured database pool size.

## Immediate mitigation
Restore the last reviewed pool setting only through an approved deployment.

## Safety conditions
Do not change IAM, expose the service publicly, or run a database command from this document.

## Recovery verification
Confirm payment and order 5xx return to zero while a bounded five-order recovery batch succeeds.

## Escalation
Escalate to the synthetic payments owner if saturation is not explained by a revision change.

