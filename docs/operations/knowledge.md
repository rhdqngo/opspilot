# Synthetic Knowledge and Agent Search Runbook

Status: M4 live Search accepted; hosted plan blocked

## Recovery and import record

- The bootstrap read-only custom role update completed and is zero drift.
- The recovery apply created only the explicit schema and Standard Search engine. Remote dev state
  contains 28 managed resources and 29 total state addresses with operator zero drift.
- The schema regression tests now keep array annotations on scalar items and prohibit searchable
  or indexable annotations on the title key property.
- One FULL import completed with 13 successes and zero failures. The bucket contains thirteen text
  objects, one manifest, and one current snapshot; the following sync plan is a no-op.
- Approval 3 added a zero-query readiness diagnostic, separately gated fixed-case probe, redacted
  HTTP/RPC failure classification, and canonical engine serving-config resolution.
- The readiness diagnostic used zero Search requests. The fixed KQ-001 probe passed once, followed
  by an independent ten-query acceptance batch with 10/10 top-five coverage, complete citations,
  and the malicious-document safety flag.
- The hosted plan failed on missing `serviceusage.services.use`. It was not retried because this is
  a custom-role contract gap rather than IAM propagation. Both hosted gates are false/unset.
- Do not modify the corpus, reimport, destroy, or broaden IAM during the live-smoke recovery.

## Local validation

Run these commands from the repository root. They do not authenticate to Google Cloud.

```powershell
uv run opspilot knowledge validate --format summary
uv run opspilot knowledge smoke --backend local --env dev --format summary
```

Success requires exactly 13 documents, ten queries, a matching deterministic catalog, 10/10
expected documents in top five, complete logical citation metadata, and no executed untrusted
instruction.

The source catalog uses `opspilot://knowledge/<document-id>` URIs. Actual bucket, project, data
store, engine, credential, and import-operation identifiers must not be copied into a tracked file,
terminal transcript, or artifact.

## Synchronization contract

The safe default only computes the difference against the remote snapshot:

```powershell
uv run opspilot knowledge sync --env dev --mode plan --format summary
```

Any future approved apply must explicitly enable `OPSPILOT_KNOWLEDGE_APPLY_ENABLED=true` before
`--mode apply`.
Apply uploads only changed stable document objects, writes one JSONL import manifest, requests one
FULL reconciliation import, waits for successful completion, and writes the new snapshot last.
Failed imports leave the prior snapshot unchanged. Runtime GCS URIs exist only in temporary or
remote data.

Agent Search smoke is independently gated by `OPSPILOT_KNOWLEDGE_SMOKE_ENABLED=true`. It issues
exactly the ten versioned queries, never paginates, caps top-k at eight and returned chunk text at
24 KiB, and emits only synthetic IDs and aggregate results.

## Live-smoke recovery gates

- intended `Edu_687` default project, KRW billing, and General pay-as-you-go confirmed
- current dev state has 28 managed resources and 29 total state addresses with zero drift
- the dedicated bucket, data store, schema, and engine are Terraform-owned
- sync plan is a no-op and the imported document set remains exactly thirteen
- hosted gates remain false until an approved bootstrap role correction and successful hosted plan
- existing Search data stores and engine remain untouched

Run the identifier-free readiness diagnostic before enabling any query gate:

```powershell
uv run opspilot knowledge diagnose --env dev --format summary
```

It must report one engine-owned serving configuration, a filter-ready schema, thirteen indexed
documents, zero index errors, `backend_ready=true`, and `search_query_count=0`. The diagnostic never
accepts or prints a resource identifier.

The probe always uses versioned case `KQ-001`; it does not accept raw query text:

```powershell
$env:OPSPILOT_KNOWLEDGE_PROBE_ENABLED = "true"
uv run opspilot knowledge probe --env dev --format summary
Remove-Item Env:OPSPILOT_KNOWLEDGE_PROBE_ENABLED
```

Only safe error categories and allowlisted request field paths may appear. A failed probe is not
retried. The ten-query smoke remains independently gated and runs only after a successful probe or
an explicitly allowed request-shape correction.

Stop without cleanup or retry if a configurable subscription, add-on, broader IAM, different
resource graph, corpus drift, or unexpected cost boundary appears.
