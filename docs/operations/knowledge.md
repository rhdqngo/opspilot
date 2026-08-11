# Synthetic Knowledge and Agent Search Runbook

Status: M4 search deployed; live smoke blocked

## Recovery and import record

- The bootstrap read-only custom role update completed and is zero drift.
- The recovery apply created only the explicit schema and Standard Search engine. Remote dev state
  contains 28 managed resources and 29 total state addresses with operator zero drift.
- The schema regression tests now keep array annotations on scalar items and prohibit searchable
  or indexable annotations on the title key property.
- One FULL import completed with 13 successes and zero failures. The bucket contains thirteen text
  objects, one manifest, and one current snapshot; the following sync plan is a no-op.
- Index readiness passed, but the first live Search request returned a safe HTTP 400 before any hit
  was normalized. No second Search request was made and the hosted gates remain disabled.
- Do not repeat the smoke, modify the corpus, reimport, destroy, or broaden IAM under the completed
  recovery approval. A separate live-smoke recovery plan must diagnose the request contract first.

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
- hosted gates remain false until a successful bounded live smoke
- existing Search data stores and engine remain untouched

Stop without cleanup or retry if a configurable subscription, add-on, broader IAM, different
resource graph, corpus drift, or unexpected cost boundary appears.
