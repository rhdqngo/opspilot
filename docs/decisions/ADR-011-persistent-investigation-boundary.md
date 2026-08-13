# ADR-011: Persistent Investigation Boundary

Status: accepted

## Context

ADR-010 placed bounded live investigation logic inside the managed ADK Runtime. That design gave
Gemini Enterprise a direct surface, but duplicated execution logic, coupled Runtime packaging to
provider collectors, and could not support durable incidents, task retry, report versions, alerts,
replay, or comparison through one production path.

## Decision

Gemini Enterprise Runtime is a thin authenticated adapter to a private investigation API. The API
creates persisted `QUEUED` investigations and Cloud Tasks invokes an idempotent executor. Provider
reads and immutable report writes use API-owned identities. Firestore stores incidents,
investigations, and versioned report subdocuments; a transaction allocates report versions.

Monitoring/Pub/Sub accepts catalog-bounded open and close events and stores only a minimal incident
seed. Alerts never start remediation. Replay reuses persisted incident scope, and comparison is a
deterministic code-owned projection of two immutable reports.

Runtime has API invoke permission only and no fallback access to operational evidence or
Firestore. Server code owns project, environment, URL, resource, metric, and provider-filter
selection.

## Consequences

- Enterprise, REST, alert, replay, and retry flows converge on one execution implementation.
- Cloud Task redelivery and concurrent replay require explicit dedupe and transactional versions.
- API availability is required for Runtime; configuration or transport failures are safe and
  localized instead of falling back.
- The offline seven-node graph remains useful for deterministic fixture evaluation but is not a
  production execution path.
- The isolated, approval-gated M8 control plane remains unchanged and receives no implicit trigger
  from investigation or alert ingestion.
