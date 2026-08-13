# Lean MVP v1 Requirements Traceability

Status: MVP complete / long-spec defect remediation locally verified

This matrix compares the M0-M10 North Star specification with the deployed MVP investigation and
approval-gated M8 control planes.
`Implemented` means a current test or operator record covers the requirement. `Partial` means the
MVP implements only a bounded subset. `Deferred` is an intentional product boundary, not an
accidental omission.

## Functional requirements

| ID | Status | Lean MVP evidence or boundary |
| --- | --- | --- |
| FR-001 | Implemented | [`parser.py`](../src/opspilot/parser.py) extracts one incident ID, normalizes dev aliases, rejects explicit prod/stage scope, and retains bounded service/symptom/window parsing covered by [`test_parser.py`](../tests/test_parser.py). |
| FR-002 | Implemented | Missing service defaults to all three and missing time to 30 minutes; both assumptions are recorded. |
| FR-003 | Implemented | Bounded Logging filter/client and live evidence tests. |
| FR-004 | Implemented | Bounded error-ratio and latency Monitoring queries, including zero-point gaps. |
| FR-005 | Implemented | The specification permits Cloud Run revision or Cloud Deploy rollout collection; the bounded Cloud Run revision path is implemented and tested. |
| FR-006 | Implemented | Agent Search corpus, sync plan, ten retrieval cases, and live search normalization. |
| FR-007 | Implemented | All four sources normalize to versioned `EvidenceItem` records. |
| FR-008 | Implemented | Operational evidence is time-sorted; knowledge is excluded from incident Timeline. |
| FR-009 | Implemented | ADK contracts permit three hypotheses and deterministic verification/ranking; [`report_policy.py`](../src/opspilot/report_policy.py) adds one non-assertive H-02 when only one operational cause is identified. |
| FR-010 | Implemented | Forged, missing, duplicate, and direction-mismatched evidence references are rejected. |
| FR-011 | Implemented | [`report_policy.py`](../src/opspilot/report_policy.py) emits at most one evidence-grounded containment, mitigation, and root-fix recommendation; [`reporting.py`](../src/opspilot/reporting.py) renders separate sections. Generalized execution remains an intentional boundary. |
| FR-012 | Implemented | Investigator identity and public surfaces are read-only. |
| FR-013 | Implemented | The isolated M8 API supports only the canonical SCN-008 payment rollback and was verified in dev. |
| FR-014 | Implemented | Firestore transaction, 15-minute Workflow callback, hash-bound approval, TTL cleanup, and actor audit were verified end to end. |
| FR-015 | Implemented | Exact target traffic, revision/digest binding, metric windows, and 10/10 recovery were verified in dev. |
| FR-016 | Implemented | [`audit.py`](../src/opspilot/audit.py), Runtime, API, task worker, executors, and report audit reuse one trace/correlation identity; concurrent run-ID idempotency is covered by [`test_investigation_service.py`](../tests/test_investigation_service.py). |
| FR-017 | Implemented | Each logical evidence tool emits the fixed privacy-safe `ToolCallAuditEvent` schema with scope, timing, result, truncation/cache, and safe error fields; success and partial/error cases are covered by [`test_audit_retry.py`](../tests/test_audit_retry.py). |
| FR-018 | Implemented | Versioned 7-case core and 40-case portfolio evaluation suites enforce deterministic gates. |
| FR-019 | Deferred | User feedback persistence is post-MVP. |
| FR-020 | Implemented | Seven fixture scenarios, SCN-001 workload execution, and SCN-008 prepare/approve/execute/reset/abort are covered. |
| FR-021 | Deferred | Public backend switching was removed; each surface has a fixed documented execution mode. |
| FR-022 | Implemented | Agent Runtime and Gemini Enterprise Preview acceptance are recorded. |
| FR-023 | Implemented | Incidents, investigations, and immutable JSON/Markdown reports are persisted in Firestore. |
| FR-024 | Implemented | Transactional report versions and deterministic version comparison are exposed by API. |
| FR-025 | Implemented | Persisted incident replay creates a new investigation and report version; fixture CLI replay remains available. |

## Non-functional requirements

| ID | Status | Lean MVP evidence or boundary |
| --- | --- | --- |
| NFR-001 | Implemented | Runtime can only invoke the API; API-owned identities hold bounded read and persistence permissions. |
| NFR-002 | Implemented | Isolated M8 control, Workflow, and payment-only executor identities passed cloud IAM negative checks. |
| NFR-003 | Implemented | Project, resource, filter, metric, and URL inputs are server-built from allowlists. |
| NFR-004 | Implemented | Malicious knowledge content stays evidence and has no tool authority. |
| NFR-005 | Implemented | Source failures and zero-point metrics produce partial/inconclusive reports. |
| NFR-006 | Implemented | [`retry.py`](../src/opspilot/retry.py) provides maximum-three exponential full-jitter retries within a deadline; Evidence, Runtime API, and remediation clients retry only transient failures and require an idempotency key for state-changing POSTs. |
| NFR-007 | Implemented | LOG, METRIC, CHANGE, and KNOWLEDGE collection is parallel. |
| NFR-008 | Implemented | Log, metric, revision, knowledge, model-input, and output sizes are bounded. |
| NFR-009 | Implemented | Demo services and Runtime use scale-to-zero boundaries. |
| NFR-010 | Deferred | BigQuery is not part of Lean MVP v1. |
| NFR-011 | Implemented | `InvestigationAudit` links source, pseudonymous actor/session/query hashes, run ID, and trace ID without retaining raw identifiers; internal service callers are issuer/audience/identity checked and source-domain hashed. |
| NFR-012 | Implemented | Runtime hashes user/session identifiers, the API persists only a redacted query plus source-domain query hash, logs exclude prompts/identities/URLs/projects/raw errors, and legacy records load through additive optional fields. |
| NFR-013 | Implemented | Provider transport/client adapters are separated from domain normalization. |
| NFR-014 | Implemented | HTTP normalization, auth/error mapping, mock, fixture, and Terraform contracts are tested. |
| NFR-015 | Implemented | Terraform, deterministic packages, knowledge sync, and documented commands rebuild the environment. |
| NFR-016 | Deferred | Lean MVP has no owned HTML report or approval UI. |
| NFR-017 | Implemented | Model/project/store settings are injected while region, catalog, provider filters, and resource scope remain server policy. |
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
uv run opspilot remediation eval --suite remediation --format summary
uv run --extra agent opspilot scenario prepare --scenario SCN-008 --mode plan --auth gcloud
uv run --extra agent opspilot scenario abort --scenario SCN-008 --mode plan --auth gcloud
uv run python scripts/m8_release.py preflight --output .tmp/m8-release
uv run python scripts/m8_release.py verify --phase image --output .tmp/m8-release
uv run python scripts/m8_release.py verify --phase terraform-plan --output .tmp/m8-release
uv run opspilot cleanup plan --format summary
```
