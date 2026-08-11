# Synthetic Knowledge and Agent Search Runbook

Status: M4 Approval 1 code complete; cloud apply and live query not approved

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

Approval 2 must explicitly enable `OPSPILOT_KNOWLEDGE_APPLY_ENABLED=true` before `--mode apply`.
Apply uploads only changed stable document objects, writes one JSONL import manifest, requests one
FULL reconciliation import, waits for successful completion, and writes the new snapshot last.
Failed imports leave the prior snapshot unchanged. Runtime GCS URIs exist only in temporary or
remote data.

Agent Search smoke is independently gated by `OPSPILOT_KNOWLEDGE_SMOKE_ENABLED=true`. It issues
exactly the ten versioned queries, never paginates, caps top-k at eight and returned chunk text at
24 KiB, and emits only synthetic IDs and aggregate results.

## Approval 2 hard gates

- intended `Edu_687` default project, KRW billing, and General pay-as-you-go confirmed
- current dev state still has 24 managed resources
- candidate bucket, data store, and engine conflicts remain zero
- bootstrap plan is exactly one read-only custom-role update
- dev plan is exactly four creates with no update, delete, replacement, IAM, network, or workload
- existing Search data stores and engine remain untouched

Stop without cleanup or retry if a configurable subscription, add-on, broader IAM, different
resource graph, import failure, or unexpected cost boundary appears.

