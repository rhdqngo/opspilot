---
document_id: ARC-003
document_type: architecture
service: shared
version: "1.0"
owner: platform-team
updated_at: "2026-08-03T00:00:00Z"
review_due_at: "2027-02-01T00:00:00Z"
canonical_uri: opspilot://knowledge/ARC-003
tags: [architecture, service-catalog, ownership]
---
# Synthetic service catalog

## Order service
Coordinates payment authorization and inventory reservation; owned by checkout-team.

## Payment service
Returns synthetic approvals and bounded scenario errors; owned by payments-team.

## Inventory service
Returns synthetic reservations; owned by inventory-team.

