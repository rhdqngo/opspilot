# Synthetic Incident Scenarios

**English** | [한국어](scenarios.ko.md)

Status: request-scoped SCN-001 validated; optional 30-minute dev experience supported

## Safety model

- Scenario behavior is disabled by default and has no persistent state.
- No persistent fault-injector state, management endpoint, secret, custom metric, alert, or
  remediation identity is created.
- Only `SCN-001` can execute against the demo workload in the M3 MVP.
- A strict scenario ID, synthetic run ID, and step are propagated only for the incident phase.
- Baseline and recovery requests carry no scenario context and exercise the normal API contract.
- Before the counted baseline, the runner probes the authenticated order `/ready` endpoint with a
  bounded 15-attempt, two-second interval. This wakes a scale-to-zero revision without adding an
  order, scenario header, or counted trace to the fixed profile.
- The fixed run profile is 5 baseline, 10 incident, and 5 recovery orders at concurrency two.

## Commands

Replay the seven deterministic investigation fixtures:

```powershell
uv run opspilot replay --scenario SCN-001 --format json
uv run opspilot replay --scenario SCN-002 --format json
uv run opspilot replay --scenario SCN-003 --format json
uv run opspilot replay --scenario SCN-004 --format json
uv run opspilot replay --scenario SCN-005 --format json
uv run opspilot replay --scenario SCN-006 --format json
uv run opspilot replay --scenario SCN-007 --format json
```

Run the request-scoped scenario against local Compose:

```powershell
docker compose up -d --no-build
docker compose exec -T -e OPSPILOT_ORDER_URL=http://127.0.0.1:8080 order `
  opspilot scenario run --scenario SCN-001 --auth local --format summary
docker compose down --remove-orphans
```

For a managed run, set `OPSPILOT_ORDER_URL` from the existing private order service before invoking
the same command with `--auth gcloud`. Omitting it intentionally targets the local default and is
not a managed scenario execution.

Expected result:

- baseline: 5/5 fulfilled
- incident: 4 fulfilled and 6 failed
- recovery: 5/5 fulfilled
- `recovered=true` and `ground_truth_matched=true`

The JSON and summary outputs contain no service URL, project, account, email, token, response body,
or gcloud stderr. The synthetic run ID is intentionally returned so the separately approved live
run can be correlated with its fixed-shape logs.

## Live Approval 2 execution record

- Rebuilt the approved `main` image as Linux/amd64 and verified non-root execution, normal 10/10
  orders, and three local scenario reproductions before one commit-SHA image push.
- Applied the reviewed binary plan with exactly `0 create / 3 update / 0 delete / 0 replacement`.
  Only the three Cloud Run services changed; managed resources remained 24.
- Verified three Ready private revisions with full traffic, one immutable digest, distinct runtime
  identities, and `OPSPILOT_SCENARIOS_ENABLED=true`.
- Reproduced SCN-001 exactly three times. Every run returned baseline 5/5, incident 4 fulfilled and
  6 failed, recovery 5/5, `recovered=true`, and `ground_truth_matched=true`.
- Correlated 60 request IDs and 60 traces across all three services. Logging contained the expected
  18 payment timeout events and 36 incident-only application 5xx entries, with no sensitive-log or
  non-incident 5xx finding.
- Cloud Monitoring exposed request-count and latency points for all three services and expected
  5xx points for order and payment. Operator and hosted plans returned zero drift.

## Scheduled portfolio experience

When `enable_scheduled_scenarios=true`, Terraform creates one dedicated Cloud Run Job and a Cloud
Scheduler trigger at `5,35 * * * *` in `Asia/Seoul`. The Job runs only:

```powershell
opspilot scenario run --scenario SCN-001 --env dev --auth workload --format json
```

Application Default Credentials mint an ID token whose audience is the fixed dev order URL. The
runner has only resource-level invocation permission on dev order; the Scheduler identity has only
resource-level invocation permission on the Job. Every execution must report baseline `5/5`,
incident `4/6`, recovery `5/5`, `recovered=true`, and matching ground truth or exit with code 2.

Operator commands:

```powershell
gcloud run jobs execute <job> --region <region> --wait
gcloud scheduler jobs pause <scheduler-job> --location <region>
gcloud scheduler jobs resume <scheduler-job> --location <region>
gcloud run jobs executions list --job <job> --region <region> --limit 5
```

Use resource names from Terraform outputs or a read-only cloud inventory; do not put them in
versioned evidence. A stopped Job leaves no fault behind because injection is carried only by the
six incident request headers. The schedule never targets staging, prod-sim, M8, or actual
production and never initiates an investigation or model call.

For a first failure, inspect the Job execution status and sanitized aggregate output. Pause the
Scheduler only if repeated executions fail recovery or violate the fixed request counts. Resume it
after a manual Job run passes the complete contract.
