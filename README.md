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
- Gemini Enterprise through a thin managed Runtime and one persistent investigation API;
- three-service, 1-120 minute parsing, Cloud Tasks execution, Firestore report versions,
  Monitoring/Pub/Sub incident input, replay, and deterministic comparison;
- deterministic minimal Runtime packaging, Terraform, safety tests, and a non-executing cleanup
  plan;
- deployed, default-off M8 approval control plane for one verified SCN-008 payment rollback.

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

The M8 release runner verifies artifacts but cannot push images, apply Terraform, activate SCN-008,
or submit an approval. The known-good payment digest uses
`OPSPILOT_SCN008_KNOWN_GOOD_IMAGE_URI`; `TF_VAR_remediation_image_uri` remains exclusive to the
control and executor image. The image phase binds a clean full commit SHA to one Registry digest,
Linux/amd64, non-root execution, and both health boundaries without storing the Registry URI. The
Terraform verifier rejects delete/replacement, changes outside the M8 allowlist, public IAM, and an
unapproved image digest. It binds the reviewed binary-plan SHA and release-context hash through
post-apply and publication. Dev evidence includes approval, rollback, target traffic at 100%,
10/10 recovery, reset, IAM negative checks, and a final `No changes` plan.

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
`POST /api/v1/investigations` persists a `QUEUED` investigation and returns 202. The API also
provides incident and immutable report reads, latest JSON/Markdown, persisted replay, deterministic
version comparison, internal task execution, and minimal Monitoring/Pub/Sub open/close ingestion.
The fixture executor remains injectable for offline tests and demos; production uses Cloud Tasks
and Firestore.

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
from verified evidence, not from a model label. The graph remains fixture/evaluation-only.

## Managed Runtime

The deployed Runtime is a thin authenticated adapter. It accepts catalog-bounded read-only
investigations for `order-service`, `payment-service`, and `inventory-service` over Korean or
English relative windows from 1 to 120 minutes, then invokes the private persistent API. Missing
service means all three; missing time means 30 minutes. The API records these assumptions.

```powershell
uv run --extra agent opspilot agent runtime package --output .tmp/runtime
```

The deterministic archive uses an explicit production allowlist. It excludes direct evidence,
model, search, redaction, reporting, and scoring paths as well as CLI/API/demo code, fixtures,
tests, docs, Terraform, and corpus synchronization.
The Runtime exposes only `streaming_agent_run_with_events` through the official `AdkApp` wrapper.
For the single-turn MVP, Enterprise-supplied session IDs are handled by an in-process
`InMemorySessionService`; no Agent Platform Session is created or persisted. Accepted requests emit
a progress event before the API call and then the persisted Markdown report or a localized safe
configuration/transport failure. Privacy-safe logs carry only a random anonymous `run_id`, stage,
elapsed time, and outcome.

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

GitHub workflows remain manual-only. PR checks, Terraform checks, and the redacted read-only hosted
Terraform plan are part of the final MVP release record.

## Safety and cost boundary

- Synthetic data only; sensitive values are redacted before evidence reaches the model.
- Service, environment, time window, metrics, and Search filters are built from allowlists.
- Evidence collection is read-only and bounded; partial sources produce explicit data gaps.
- Citations are verified against immutable evidence; prompt-injection content remains data.
- Executable actions are removed and every retained recommendation requires human approval.
- Runtime scales from zero to one; Cloud Run demo services scale to zero.
- The existing KRW 50,000 monthly budget alert remains unchanged.
- VPC, Model Armor, managed sessions/memory, dashboards, BigQuery, feedback, and multi-project
  support remain post-MVP options.

Operational details are in [docs/operations/agent-runtime.md](docs/operations/agent-runtime.md),
[docs/operations/agent-orchestration.md](docs/operations/agent-orchestration.md), and
[docs/plans/current.md](docs/plans/current.md).
