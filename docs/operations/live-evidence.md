# M5 Live Evidence Runbook

Status: Approval 1 code complete; cloud access not applied

## Purpose

M5 provides deterministic, read-only collectors for Cloud Logging, Cloud Monitoring, Cloud Run
revisions, and the existing Agent Search corpus. It does not generate hypotheses, call a model, or
execute remediation.

## Local validation

The default smoke uses fixture data and makes no Google Cloud request:

```powershell
uv run opspilot evidence smoke --backend fixture --scenario SCN-001 --env dev --format summary
```

Expected fixed budget:

- four logical collectors
- zero API calls
- LOG, METRIC, CHANGE, and KNOWLEDGE source status `pass`
- four existing SCN-001 evidence IDs

The live backend is disabled unless `OPSPILOT_LIVE_EVIDENCE_ENABLED=true`. It also requires a
process-scoped synthetic `OPSPILOT_SCENARIO_RUN_ID`. Neither setting belongs in a tracked file.

## Query boundaries

- Only the current gcloud default project is used.
- Services and metrics come from `config/services.yaml`.
- Time ranges use UTC and cannot exceed two hours.
- Logging reads one newest-first page of at most 100 entries and retains at most 30 KiB.
- Monitoring returns at most 600 points per series. `db_pool_waiters` remains fixture-only.
- Cloud Run reads one fixed service and at most 20 revisions; environment values are hashed and
  withheld.
- Agent Search performs one top-six request against the existing dedicated engine and preserves
  the M4 24 KiB result cap and untrusted-content flags.
- There is no automatic retry or pagination. Partial source failures remain visible.

## Approval 2 boundary

Do not run the live command until a separately reviewed bootstrap custom-role update and exact
two-create dev IAM plan have been applied. Approval 2 must use service-account impersonation with
no user-managed key, run one bounded SCN-001 profile, and keep actual identifiers in the process
environment or ignored run directory only.

The revision collector reports temporal facts as neutral evidence. It must not convert the fixture
statement about a reduced pool size into a live claim unless the actual revision data supports it.
