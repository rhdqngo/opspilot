# OpsPilot

**Evidence-grounded AI Incident Commander for Google Cloud**

OpsPilot is a portfolio-first, production-minded incident commander for a synthetic ecommerce
environment. It collects bounded read-only evidence, verifies every cited claim against typed
evidence, and keeps that investigation plane read-only. A separate, default-off M8 control plane
can execute one exact payment revision rollback only after an authenticated approval.

Current verified surfaces:

- three private, scale-to-zero Cloud Run demo roles and one live reproducible SCN-001 incident;
- seven canonical fixture investigations and a versioned 40-case portfolio release gate;
- bounded Logging, Monitoring, revision, and Agent Search evidence;
- Gemini Enterprise through a fixed single-turn `payment-service`/30-minute managed Runtime;
- deterministic Runtime packaging, Terraform, safety tests, and a non-executing cleanup plan.
- default-off M8 approval control plane for one SCN-008 payment revision rollback; it is implemented
  and locally tested but not deployed or authorized for cloud execution.

<!-- BEGIN GENERATED:PORTFOLIO_METRICS -->
Latest published verification: **143/144 pytest**; core **7/7**; portfolio **40/40**.
RCA top-1/top-3, required-tool recall, citation coverage, and evidence-ID validity: **1.000/1.000/1.000/1.000/1.000**; fixture P50/P95 **12/14 ms**.
The generated [Markdown evidence](docs/portfolio/results/portfolio-release-v1.md) and [JSON evidence](docs/portfolio/results/portfolio-release-v1.json) are the source of record.
<!-- END GENERATED:PORTFOLIO_METRICS -->

M8 remains separate from the read-only Runtime. See the
[remediation operating contract](docs/operations/remediation.md), or inspect its non-executing plan
and 12-case local gate:

```powershell
uv run --extra agent opspilot scenario prepare --scenario SCN-008 --mode plan --auth gcloud
uv run --extra agent opspilot scenario abort --scenario SCN-008 --mode plan --auth gcloud
uv run opspilot remediation eval --suite remediation --format summary
uv run python scripts/m8_release.py preflight --output .tmp/m8-release
uv run python scripts/m8_release.py verify --phase image --output .tmp/m8-release
uv run python scripts/m8_release.py verify --phase terraform-plan --output .tmp/m8-release
```

The M8 release runner is read-only: it cannot push images, apply Terraform, activate SCN-008, or
submit an approval. The known-good payment digest uses
`OPSPILOT_SCN008_KNOWN_GOOD_IMAGE_URI`; `TF_VAR_remediation_image_uri` remains exclusive to the
control and executor image. The image phase binds a clean full commit SHA to one Registry digest,
Linux/amd64, non-root execution, and both health boundaries without storing the Registry URI. The
Terraform verifier accepts exactly the 21 additive M8 resource addresses, the two reviewed state
moves, zero update/delete/replacement, and an unchanged reviewed binary plan. No M8 cloud evidence
has been published yet.

[Architecture](docs/portfolio/architecture.md) ·
[Evaluation](docs/portfolio/evaluation.md) ·
[Demo](docs/portfolio/demo.md) ·
[Threat model](docs/security/threat-model.md) ·
[Cost](docs/cost-model.md) ·
[Requirements](docs/requirements-traceability.md)

## Portfolio release evidence

```powershell
uv run python scripts/portfolio_release.py check --output .tmp/portfolio-release
uv run python scripts/portfolio_release.py check --include-infra --publish `
  --output .tmp/portfolio-release
```

The first command writes local evidence only. The second publishes a sanitized, tracked result only
when every release check passes. It never deploys, applies Terraform, or calls Gemini Enterprise.

## Local setup

```powershell
uv sync --frozen --extra agent
uv run opspilot replay --scenario SCN-001 --format markdown
uv run opspilot serve
```

The investigation API keeps `/healthz` and `/readyz`. The demo services use `/health` and `/ready`.
The local investigation API is explicitly fixture-only: it accepts `payment-service`/SCN-001 and
returns 422 for other service or incident scopes. Status responses expose `execution_mode=fixture`
and `scenario_id=SCN-001`.

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
uv run --extra agent opspilot agent eval --suite core --format summary
uv run --extra agent opspilot agent eval --suite portfolio --format summary `
  --output .tmp/evaluation
```

The fixture graph performs evidence preparation, two model calls, deterministic citation review
and scoring, report composition, and final validation. Each model node has a 30-second timeout; the
graph has a 75-second deadline. Models receive no tools. Product root-cause taxonomy is derived
from verified evidence, not from a model label. The deployed Runtime uses the smaller live hybrid
described below rather than this graph.

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
For the single-turn MVP, Enterprise-supplied session IDs are handled by an in-process
`InMemorySessionService`; no Agent Platform Session is created or persisted. Multi-turn continuity
and managed Sessions remain post-MVP. Accepted requests emit a bounded-evidence progress event
before work and a final report or safe error event within the internal 18-second investigation
deadline.
Privacy-safe structured logs carry a random anonymous `run_id`, source status/error codes, and
reasoning outcome without question text, user/session identity, project ID, or raw exceptions.

## Portfolio cleanup plan

```powershell
uv run opspilot cleanup plan --format summary
```

This command only renders the reviewed deletion order. It cannot execute Terraform or delete cloud
resources, and every destructive step remains separately approved.

## Reproducible portfolio demo

With dependencies and the local image prepared, the bounded demo runs Compose, SCN-001, evidence,
the agent report, the portfolio gate, and the cleanup plan before stopping Compose in a `finally`
path:

```powershell
uv run python scripts/portfolio_demo.py
uv run python scripts/portfolio_demo.py --dry-run
uv run python scripts/portfolio_demo.py --build-image
```

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
