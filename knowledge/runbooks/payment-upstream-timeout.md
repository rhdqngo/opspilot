---
document_id: RB-PAY-002
document_type: runbook
service: payment-service
version: "1.0"
owner: payments-team
updated_at: "2026-08-01T00:00:00Z"
review_due_at: "2026-12-01T00:00:00Z"
canonical_uri: opspilot://knowledge/RB-PAY-002
tags: [provider, dependency, timeout, scn-002]
---
# External payment provider timeout

## Symptoms
Payment requests exceed the three-second dependency timeout without a database saturation signal.

## Impact
Orders return a safe partial failure while inventory results can still be observed.

## Metrics
Compare provider latency with internal payment processing latency and database utilization.

## Log signatures
Look for UPSTREAM_PROVIDER_TIMEOUT and preserve the dependency error category.

## Recent changes
Check provider endpoint and timeout configuration without assembling a URL from user input.

## Immediate mitigation
Pause the demo window or use an approved provider fallback; do not retry authorization writes.

## Safety conditions
Never log authorization headers, tokens, or payment-like input.

## Recovery verification
Verify provider latency is below three seconds and bounded orders are fulfilled once each.

## Escalation
Escalate to the synthetic provider owner when the external latency remains elevated.

