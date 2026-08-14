# Persistent Investigation API

Status: deployed v1 contract; formal-agent v2 candidate locally verified and not yet deployed

`POST /internal/v2/runtime/turns` is the authoritative conversational endpoint. It resolves
investigate, refine, explain, compare, status, capability, and bounded remediation-request intents.
Conversation state is limited to incident/environment/services/window/depth/report/hypothesis
references under a domain-separated session hash and expires after 24 hours.
The requested `output_language` is stored with the bounded investigation scope and is passed to the
tool-free RCA graph so server-owned narrative is produced in Korean or English without translating
evidence IDs or technical identifiers. Model root-cause codes outside the seven-value server
taxonomy are rejected before scoring.

The formal parser accepts three services individually or together, `dev`, `staging`, and synthetic
`prod-sim`, relative or explicit 1-120 minute windows, six symptoms, and three investigation depths.
Unqualified `prod`/`production`/`운영` remains real production and is rejected without coercion.

`POST /api/v1/investigations` remains a compatible single-turn path accepting a bounded
natural-language query, optional incident ID, and requested depth. It uses the same expanded parser,
extracts at most one incident ID, and rejects body/field ID conflicts. An omitted environment is
normalized to dev and recorded as an assumption.
An incident ID does not need to exist before the request: a valid unused ID creates a new
user-source incident transactionally, while an existing ID receives the new investigation.

The response adds `trace_id` alongside investigation, correlation, and incident IDs. When
`OPSPILOT_INVESTIGATION_AUDIENCE` is configured, the API verifies the Google ID token and stores
only a source-domain hash of the verified subject. The original query is never persisted: it is
redacted first, while a normalized source-domain SHA-256 `query_hash` is kept in
`InvestigationAudit`.

The Runtime bridge `POST /internal/v1/runtime/investigations` requires Runtime-generated run,
correlation, trace, actor/session hash, query hash, and `output_language` fields. The query hash is recomputed, the
configured Runtime service account is verified, and the run ID maps deterministically to the
investigation ID. Repeated submissions safely reuse the same investigation; Cloud Tasks retains
its deterministic task-name deduplication. The language field affects Markdown rendering only;
persisted reports remain language-neutral.

Task and Monitoring/Pub/Sub internal endpoints verify their separately configured service-account
emails when the audience is enabled. Internal caller logs contain only caller source and a
source-domain actor hash. Workers reuse the stored trace/correlation IDs and never derive evidence
filters from the orchestration trace ID.

Firestore changes are additive. `trace_id` has a safe default and `audit` is optional, so documents
written before this contract remain readable without a migration.

## Local verification

```powershell
uv run --extra agent pytest tests/test_api.py tests/test_investigation_service.py
uv run opspilot replay --scenario SCN-001 --format markdown
```

The tests cover authenticated actor hashing, redaction, trace propagation, legacy records, Cloud
Task redelivery, localized assumptions, and 20 concurrent submissions of one Runtime run ID with
both generated and caller-supplied incident IDs.
