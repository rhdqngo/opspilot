# M5 Live Evidence Runbook

Status: M5 Approval 2 complete

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
- There is no automatic pagination. Transient 429, 5xx, timeout, and transport failures retry at
  most three times with exponential full jitter inside the existing deadline; auth, validation,
  and other 4xx failures do not retry. Exhausted sources remain visible as partial failures.

Every logical collector emits one `opspilot_tool_call` JSON event containing only trace/correlation
scope, tool and bounded request dimensions, timestamps/latency, API/result counts, byte size,
truncate/cache state, and safe error classification. Prompts, identities, tokens, URLs, projects,
raw log content, and raw exceptions are excluded.

## Approval 2 boundary

Do not run the live command until a separately reviewed bootstrap custom-role update and exact
three-create dev IAM plan have been applied. The dev graph contains the investigator read role,
its project binding, and one Token Creator binding scoped to the investigator service account for
the `Edu_687` operator. Approval 2 must use this short-lived impersonation path with no
user-managed key, run one bounded SCN-001 profile, and keep actual identifiers in the process
environment or ignored run directory only.

The live collection is one Logging request, two Monitoring requests, one Cloud Run service read,
one revision list, and one Standard Search request. A log evidence item records its redacted
signature count as `occurrences`, allowing the six expected `DB_POOL_TIMEOUT` events to be checked
without retaining raw request or trace identifiers.

The revision collector reports temporal facts as neutral evidence. It must not convert the fixture
statement about a reduced pool size into a live claim unless the actual revision data supports it.

## Approval 2 execution record

- Bootstrap: exact one custom-role update; 14 managed / 15 addresses; zero drift.
- Dev: exact three IAM creates; 31 managed / 32 addresses; zero drift.
- Access: operator and investigator impersonation gates pass; investigator user-managed keys 0.
- Scenario: one remote SCN-001 run completed baseline 5/5, incident 4/6, recovery 5/5.
- Evidence: four logical sources and six API requests, with no retry, error, data gap, or
  pagination.
- Acceptance: six payment timeout occurrences, positive error ratio, latency P95, neutral revision
  evidence, `RB-PAY-001`, complete logical citations, and no sensitive output.
- Hosted: the manual WIF plan produced one redacted text artifact reporting `No changes`.

This acceptance result is evidence collection only. It does not create a hypothesis, call a model,
or turn the neutral revision snapshot into a live configuration-change claim.
