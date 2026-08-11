---
document_id: ARC-002
document_type: architecture
service: order-service
version: "1.0"
owner: platform-team
updated_at: "2026-08-03T00:00:00Z"
review_due_at: "2027-02-01T00:00:00Z"
canonical_uri: opspilot://knowledge/ARC-002
tags: [architecture, request-flow, trace, identity-token]
---
# Order request and trace flow

## Entry
An authenticated operator sends a synthetic order to the private order service with a bounded request ID.

## Fan-out
Order obtains audience-specific metadata ID tokens and calls payment and inventory concurrently without write retries.

## Correlation
The same request ID and Cloud Trace ID appear in structured application logs for all three services.

