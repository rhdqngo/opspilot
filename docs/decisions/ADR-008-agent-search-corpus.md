# ADR-008: Dedicated Synthetic Agent Search Corpus

Status: accepted for M4 Approval 1

## Decision

OpsPilot uses a dedicated, default-off Agent Search data store and Standard Search engine in the
`global` location. It does not attach the corpus to existing project Search assets. Source
Markdown, metadata, hashes, and retrieval expectations are versioned; actual GCS URIs are generated
only during an approved synchronization.

Terraform owns the protected bucket, data store, explicit metadata schema, and engine. The sync
tool owns document objects and FULL reconciliation imports. This separation avoids putting corpus
content in Terraform state and provides document-hash idempotency.

General pay-as-you-go Standard Search is the only accepted pricing path. Configurable subscription,
Enterprise tier, AI Overview, LLM add-ons, OCR, and layout parsing are excluded from the MVP.

## Consequences

- Existing data stores and engine are isolated from OpsPilot changes and evaluation noise.
- Local CI can validate all content, filters, safety flags, and ten retrieval contracts without a
  credential or billable query.
- Approval 2 must separately review the bootstrap role update, four-resource dev plan, corpus
  import, and ten-query live smoke.
- M5 may wrap the normalized Search response as a read-only evidence tool but may not weaken the
  query/filter, size, citation, or untrusted-data boundaries established here.
