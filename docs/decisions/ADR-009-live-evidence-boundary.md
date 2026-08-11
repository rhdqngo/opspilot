# ADR-009: Keep Live Evidence Collection Deterministic and Read-only

Status: accepted for M5 Approval 1

## Decision

Cloud Logging, Monitoring, Cloud Run revision, and Agent Search access share one typed
`EvidenceClient` boundary. Fixture and live adapters produce the same `ToolResult` and
`EvidenceItem` contracts, while server-owned builders create every project path and cloud filter.

The live investigator receives one custom role containing only the seven approved read/API-use
permissions. The role and binding remain default-off until a separate apply approval. Local
validation uses the fixture adapter and performs no cloud query.

## Consequences

- M6 can attach ADK reasoning to already-bounded evidence instead of exposing raw cloud clients to
  a model.
- A source timeout or permission error produces a partial collection with explicit tool errors and
  data gaps.
- Cloud Run revision proximity is neutral evidence and cannot prove a causal configuration change.
- The project-level Logging and Monitoring read scope is constrained operationally by the
  synthetic-only project and deterministic service/time/metric allowlists.
- No Google client dependency, custom metric, alert, model call, or remediation path is added in
  M5 Approval 1.
