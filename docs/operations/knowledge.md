# Synthetic Knowledge and Agent Search Runbook

Status: M4 complete; live Search and hosted plan accepted

## Deployed state

The protected bucket contains thirteen synthetic documents, one import manifest, and one current
snapshot. One FULL import completed with thirteen successes and no failures. The dedicated global
Standard Search data store, schema, and engine are Terraform-managed and zero drift. Existing
unrelated Search assets are not connected or modified.

## Local validation

Run these commands from the repository root. They do not authenticate to Google Cloud.

```powershell
uv run opspilot knowledge validate --format summary
uv run opspilot knowledge smoke --format summary
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

Local smoke issues exactly the ten versioned queries, never paginates, caps top-k at eight and
returned chunk text at 24 KiB, and emits only synthetic IDs and aggregate results. Runtime live
Search uses the same allowlisted request/response contract but is not exposed as a standalone CLI.

Stop without cleanup or retry if a configurable subscription, add-on, broader IAM, different
resource graph, corpus drift, or unexpected cost boundary appears.
