# OpsPilot

OpsPilot is an evidence-grounded incident commander for a synthetic ecommerce environment. The
MVP collects read-only operational evidence, runs a bounded seven-node ADK investigation, and
returns a cited `IncidentReport`. It never executes remediation.

## Local setup

```powershell
uv sync --frozen --extra agent
uv run opspilot replay --scenario SCN-001 --format markdown
uv run opspilot serve
```

The investigation API keeps `/healthz` and `/readyz`. The demo services use `/health` and `/ready`.

## Demo workload

One non-root Linux image runs the order, payment, and inventory roles with in-memory synthetic
data.

```powershell
docker build --platform linux/amd64 -t opspilot-demo:local .
docker compose up -d --no-build
docker compose exec -T -e OPSPILOT_ORDER_URL=http://127.0.0.1:8080 order `
  opspilot demo load --orders 10 --concurrency 2 --auth local
docker compose exec -T -e OPSPILOT_ORDER_URL=http://127.0.0.1:8080 order `
  opspilot scenario run --scenario SCN-001 --auth local --format summary
docker compose down --remove-orphans
```

SCN-001 is bounded to `5 baseline → 10 incident → 5 recovery` requests. Six incident payment
requests return the synthetic `DB_POOL_TIMEOUT`; the recovery phase must return to normal.

## Knowledge, evidence, and reasoning

The repository contains 13 synthetic knowledge documents and ten deterministic retrieval cases.
All public smoke and evaluation commands are offline:

```powershell
uv run opspilot knowledge validate --format summary
uv run opspilot knowledge smoke --format summary
uv run opspilot knowledge sync --env dev --mode plan --format summary
uv run opspilot evidence smoke --scenario SCN-001 --env dev --format summary
uv run --extra agent opspilot agent run --scenario SCN-001 --format summary
uv run --extra agent opspilot agent eval --format summary
```

The graph performs evidence preparation, two model calls, deterministic citation review and
scoring, report composition, and final validation. Each model node has a 30-second timeout; the
graph has a 75-second deadline. Models receive no tools. Product root-cause taxonomy is derived
from verified evidence, not from a model label.

## Managed Runtime

The deployed Runtime accepts only a read-only `payment-service` investigation for the recent
30-minute window. Other services, windows, recovery requests, project IDs, URLs, tokens, and raw
filters are rejected before evidence or model work.

```powershell
uv run --extra agent opspilot agent runtime package --output .tmp/runtime
```

The deterministic archive uses an explicit production allowlist. It excludes CLI, API/demo code,
fixtures, tests, docs, Terraform, corpus synchronization, and retired diagnostic/acceptance tools.
The Runtime exposes only `streaming_agent_run_with_events` through the official `AdkApp` wrapper.

## Validation

```powershell
uv sync --frozen --extra agent
uv run ruff format --check .
uv run ruff check .
uv run --extra agent mypy src tests
uv run --extra agent pytest
uv build
terraform fmt -check -recursive infra/terraform
terraform -chdir=infra/terraform/bootstrap validate
terraform -chdir=infra/terraform/bootstrap test
terraform -chdir=infra/terraform/environments/dev validate
terraform -chdir=infra/terraform/environments/dev test
```

GitHub workflows are retained as manual-only definitions and are not MVP completion gates. Local
tests and operator Terraform plans are authoritative.

## Safety and cost boundary

- Synthetic data only; sensitive values are redacted before evidence reaches the model.
- Service, environment, time window, metrics, and Search filters are built from allowlists.
- Evidence collection is read-only and bounded; partial sources produce explicit data gaps.
- Citations are verified against immutable evidence; prompt-injection content remains data.
- Executable actions are removed and every retained recommendation requires human approval.
- Runtime scales from zero to one; Cloud Run demo services scale to zero.
- The existing KRW 50,000 monthly budget alert remains unchanged.
- VPC, Model Armor, automatic alerts, remediation, sessions/memory, dashboards, and multi-project
  support remain post-MVP options.

Operational details are in [docs/operations/agent-runtime.md](docs/operations/agent-runtime.md),
[docs/operations/agent-orchestration.md](docs/operations/agent-orchestration.md), and
[docs/plans/current.md](docs/plans/current.md).
