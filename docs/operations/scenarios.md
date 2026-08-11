# M3 Synthetic Incident Scenarios

Status: offline corpus complete; SCN-001 ready for separate live approval

## Safety model

- Scenario behavior is disabled by default and has no persistent state.
- No fault-injector service, Cloud Run Job, management endpoint, secret, custom metric, alert, or
  remediation identity is created.
- Only `SCN-001` can execute against the demo workload in the M3 MVP.
- A strict scenario ID, synthetic run ID, and step are propagated only for the incident phase.
- Baseline and recovery requests carry no scenario context and exercise the normal API contract.
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

Expected result:

- baseline: 5/5 fulfilled
- incident: 4 fulfilled and 6 failed
- recovery: 5/5 fulfilled
- `recovered=true` and `ground_truth_matched=true`

The JSON and summary outputs contain no service URL, project, account, email, token, response body,
or gcloud stderr. The synthetic run ID is intentionally returned so the separately approved live
run can be correlated with its fixed-shape logs.

## Live Approval 2 boundary

Approval 2 rebuilds and pushes one immutable image, sets the M3 image gate, and reviews an exact
three-service in-place plan. It must not add a resource or IAM binding. After apply, SCN-001 must
reproduce three times and each run must return to a 5/5 recovery baseline. Cloud Run request count,
latency, 5xx, request logs, and correlated application logs are checked with a bounded ingestion
wait. No rollback, public access, or automatic remediation is part of M3.
