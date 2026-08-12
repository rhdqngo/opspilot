# Lean MVP v1 Requirements Traceability

Status: implemented baseline verified locally

This matrix compares the M0-M10 North Star specification with the deployed read-only Lean MVP v1.
`Implemented` means a current test or operator record covers the requirement. `Partial` means the
MVP implements only a bounded subset. `Deferred` is an intentional product boundary, not an
accidental omission.

## Functional requirements

| ID | Status | Lean MVP evidence or boundary |
| --- | --- | --- |
| FR-001 | Partial | Parser recognizes allowlisted service names and basic symptoms; environment and explicit time parsing remain fixed. |
| FR-002 | Implemented | Parser and Runtime apply and record the recent 30-minute assumption. |
| FR-003 | Implemented | Bounded Logging filter/client and live evidence tests. |
| FR-004 | Implemented | Bounded error-ratio and latency Monitoring queries, including zero-point gaps. |
| FR-005 | Partial | Cloud Run revisions are collected; Cloud Deploy rollouts are not. |
| FR-006 | Implemented | Agent Search corpus, sync plan, ten retrieval cases, and live search normalization. |
| FR-007 | Implemented | All four sources normalize to versioned `EvidenceItem` records. |
| FR-008 | Implemented | Operational evidence is time-sorted; knowledge is excluded from incident Timeline. |
| FR-009 | Implemented | ADK contracts permit three hypotheses and deterministic verification/ranking. |
| FR-010 | Implemented | Forged, missing, duplicate, and direction-mismatched evidence references are rejected. |
| FR-011 | Partial | Fixture reports classify advisory actions; live Runtime deliberately emits no actions. |
| FR-012 | Implemented | Investigator identity and public surfaces are read-only. |
| FR-013 | Deferred | No remediation request object or route exists. |
| FR-014 | Deferred | Approval lifecycle is post-MVP. |
| FR-015 | Deferred | Post-action verification is post-MVP. |
| FR-016 | Partial | API correlation IDs, demo traces, and anonymous Runtime/agent run IDs exist; no persisted cross-system trace index exists. |
| FR-017 | Partial | Evidence metadata and privacy-safe Runtime run summaries are structured; raw inputs and identities are intentionally excluded. |
| FR-018 | Implemented | Versioned 7-case core and 40-case portfolio evaluation suites enforce deterministic gates. |
| FR-019 | Deferred | User feedback persistence is post-MVP. |
| FR-020 | Partial | Seven offline scenarios replay; only SCN-001 executes against the live demo workload. |
| FR-021 | Deferred | Public backend switching was removed; each surface has a fixed documented execution mode. |
| FR-022 | Implemented | Agent Runtime and Gemini Enterprise Preview acceptance are recorded. |
| FR-023 | Partial | JSON and Markdown are produced; API storage is process-local rather than durable. |
| FR-024 | Deferred | Report-version comparison requires persistent storage. |
| FR-025 | Partial | CLI fixture replay exists; no replay API is exposed. |

## Non-functional requirements

| ID | Status | Lean MVP evidence or boundary |
| --- | --- | --- |
| NFR-001 | Implemented | Custom IAM role and Runtime package contain read-only evidence operations. |
| NFR-002 | Deferred | No write operation exists, so executor identity and approval tokens are not provisioned. |
| NFR-003 | Implemented | Project, resource, filter, metric, and URL inputs are server-built from allowlists. |
| NFR-004 | Implemented | Malicious knowledge content stays evidence and has no tool authority. |
| NFR-005 | Implemented | Source failures and zero-point metrics produce partial/inconclusive reports. |
| NFR-006 | Implemented | Transport, source, collection, model, and whole-run deadlines are bounded. |
| NFR-007 | Implemented | LOG, METRIC, CHANGE, and KNOWLEDGE collection is parallel. |
| NFR-008 | Implemented | Log, metric, revision, knowledge, model-input, and output sizes are bounded. |
| NFR-009 | Implemented | Demo services and Runtime use scale-to-zero boundaries. |
| NFR-010 | Deferred | BigQuery is not part of Lean MVP v1. |
| NFR-011 | Partial | Anonymous run IDs correlate stages without retaining question, user, or session identity. |
| NFR-012 | Implemented | No user identity is persisted; sensitive synthetic content is redacted. |
| NFR-013 | Implemented | Provider transport/client adapters are separated from domain normalization. |
| NFR-014 | Implemented | HTTP normalization, auth/error mapping, mock, fixture, and Terraform contracts are tested. |
| NFR-015 | Implemented | Terraform, deterministic packages, knowledge sync, and documented commands rebuild the environment. |
| NFR-016 | Deferred | Lean MVP has no owned HTML report or approval UI. |
| NFR-017 | Partial | Model/project/data-store settings are injected; fixed Runtime region and product scope remain policy constants. |
| NFR-018 | Implemented | Hypotheses distinguish supporting and contradicting evidence. |
| NFR-019 | Implemented | Support scores and product taxonomy are computed from verified evidence in code. |
| NFR-020 | Implemented | Pydantic validation and fixed safe failure protect structured outputs. |

## Verification commands

```powershell
uv run --extra agent pytest
uv run ruff format --check .
uv run ruff check .
uv run --extra agent mypy src tests
uv run --extra agent opspilot agent eval --suite core --format summary
uv run --extra agent opspilot agent eval --suite portfolio --format summary --output .tmp/evaluation
uv run opspilot cleanup plan --format summary
```
