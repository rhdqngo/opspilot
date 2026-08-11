# ADR-009: Keep Live Evidence Collection Deterministic and Read-only

Status: accepted; Approval 2 leaf impersonation amendment prepared

## Decision

Cloud Logging, Monitoring, Cloud Run revision, and Agent Search access share one typed
`EvidenceClient` boundary. Fixture and live adapters produce the same `ToolResult` and
`EvidenceItem` contracts, while server-owned builders create every project path and cloud filter.

The live investigator receives one custom role containing only the seven approved read/API-use
permissions. The role and binding remain default-off until a separate apply approval. Local
validation uses the fixture adapter and performs no cloud query.

The operator may mint a short-lived investigator OAuth token through
`roles/iam.serviceAccountTokenCreator`, but the binding is attached only to the fixed investigator
service account. No project-wide impersonation grant or service-account key is permitted. Hosted
Terraform receives only the IAM policy read permission required to refresh that leaf binding.

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
