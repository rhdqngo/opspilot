# M3 Synthetic Incident Scenarios

Status: M3 complete; offline corpus and bounded live SCN-001 validated

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

The live gate is now configured for the manual read-only workflow. M3 adds no resource, IAM
binding, rollback automation, public access, or remediation path.
