# Persistent Investigation API

Status: local contract verified; cloud rollout pending

`POST /api/v1/investigations` accepts a bounded natural-language query, optional incident ID, and
requested depth. The parser accepts only the catalog services and `dev`/`development`/`개발`,
rejects explicit prod/stage/qa scope, extracts at most one incident ID, and rejects body/field ID
conflicts. An omitted environment is normalized to dev and recorded as an assumption.

The response adds `trace_id` alongside investigation, correlation, and incident IDs. When
`OPSPILOT_INVESTIGATION_AUDIENCE` is configured, the API verifies the Google ID token and stores
only a source-domain hash of the verified subject. The original query is never persisted: it is
redacted first, while a normalized source-domain SHA-256 `query_hash` is kept in
`InvestigationAudit`.

The Runtime bridge `POST /internal/v1/runtime/investigations` requires Runtime-generated run,
correlation, trace, actor/session hash, and query hash fields. The query hash is recomputed, the
configured Runtime service account is verified, and the run ID maps deterministically to the
investigation ID. Repeated submissions safely reuse the same investigation; Cloud Tasks retains
its deterministic task-name deduplication.

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
Task redelivery, and 20 concurrent submissions of one Runtime run ID.
