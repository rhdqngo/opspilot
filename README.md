# OpsPilot

Evidence-grounded incident commander foundation with deterministic local investigations and a
containerized synthetic ecommerce workload. Cloud deployment and remediation remain separately
approval-gated.

## Local setup

```powershell
uv sync --frozen
uv run opspilot replay --scenario SCN-001 --format markdown
uv run opspilot serve
```

The API is available at `http://127.0.0.1:8000`; use `/healthz`, `/readyz`, and `/docs` for
local verification.

## Synthetic demo workload

One non-root Linux image runs isolated order, payment, and inventory roles. The local Compose
network uses in-memory state and no Google Cloud credential.

```powershell
make demo-up
make demo-smoke
make demo-down
```

Without Make, build and run `opspilot-demo:local` with `docker build --platform linux/amd64`,
`docker compose up -d --no-build`, and `docker compose down --remove-orphans`. The bounded load
command is `uv run opspilot demo load --orders 10 --concurrency 2 --auth local`.

M3 adds a seven-scenario offline corpus and one bounded live-capable MVP scenario. Local Compose
enables request-scoped synthetic behavior only for the explicit scenario command:

```powershell
uv run opspilot replay --scenario SCN-007 --format markdown
uv run opspilot scenario run --scenario SCN-001 --auth local --format summary
```

SCN-001 always runs `5 baseline → 10 incident → 5 recovery` requests at concurrency two. Six
incident payments return the synthetic `DB_POOL_TIMEOUT`; all baseline and recovery requests must
be fulfilled. The bounded profile has also been reproduced three times against the private Cloud
Run workload. No persistent fault flag or management endpoint exists.

## Synthetic operational knowledge

M4 Approval 1 adds 13 versioned synthetic runbooks, RCA, architecture, ownership, and adversarial
documents plus ten deterministic retrieval queries. Local validation performs no cloud call:

```powershell
uv run opspilot knowledge validate --format summary
uv run opspilot knowledge smoke --backend local --env dev --format summary
```

`knowledge sync` defaults to plan mode. The zero-query `knowledge diagnose` command reports only
aggregate Agent Search readiness, while the fixed `KQ-001` `knowledge probe` requires an explicit
process-scoped gate. Project, bucket, data-store, engine, token, query, and GCS URI values are never
accepted as diagnostic CLI arguments or printed.

## Read-only evidence layer

M5 Approval 1 adds typed, bounded collectors behind a fixture/live adapter boundary. The default
smoke is local-only and performs no Google Cloud request:

```powershell
uv run opspilot evidence smoke --backend fixture --scenario SCN-001 --env dev --format summary
```

The live backend is disabled by default. It accepts no project, URL, token, resource name, raw
Logging filter, or Monitoring filter argument. Google Cloud IAM and live evidence acceptance are a
separate Approval 2.

## Bounded ADK orchestration

M6 Approval 1 adds Google ADK 2.5 as an optional dependency and keeps the default installation
lightweight. The offline fake model executes the same typed seven-node graph as the future Vertex
path without a network call or credential:

```powershell
uv sync --frozen --extra agent
uv run --extra agent opspilot agent run --backend fixture --scenario SCN-001 --model fake --format summary
uv run --extra agent opspilot agent eval --suite fixture --model fake --format summary
uv run --extra agent opspilot agent diagnose --account-alias Edu_687 --format summary
uv run --extra agent opspilot agent accept --suite m6-rca --model fake --format summary
uv run --extra agent opspilot agent accept --suite m6-safety --model fake --format summary
uv run --extra agent opspilot agent accept --suite m6-core --model fake --format summary
```

The graph performs bounded evidence preparation, RCA drafting, deterministic citation review and
scoring, and report composition. The two model nodes receive normalized evidence only, have no
tools, and cannot assign support scores or execute recommendations. The Vertex model path is
fail-closed unless `OPSPILOT_LIVE_MODEL_ENABLED=true`. Acceptance is split into fixed `m6-rca`
(SCN-001), `m6-safety` (SCN-006 and SCN-007), and `m6-core` suites with respective two, four, and
six-request ceilings. Every suite stops on first failure. The diagnostic performs no generation
request and emits only redacted readiness fields.

The first approved Vertex batch stopped safely after the reviewer response reached the client and
was not retried. Approval 3 replaces that advisory model reviewer with fixed citation rules while
preserving the seven-node trajectory. Its separately approved batch stopped after SCN-001 completed
two successful model calls but failed the final semantic acceptance predicate; SCN-006 and SCN-007
were not called. Approval 4 exposes each existing acceptance predicate through fixed safe fields
and failure codes. Its separately bounded SCN-001 checkpoint completed both calls and passed every
predicate except the fixed root-cause taxonomy: the model returned `CONFIG_DB_POOL_EXHAUSTION`
instead of `PAYMENT_DB_POOL_EXHAUSTION`. No retry or runtime change was made. M6 remains blocked and
M7 deployment has not started.

The three private Cloud Run services are deployed and remotely validated. The retired `z`-suffix
demo health path conflicted with a Cloud Run reserved path; the demo now uses `/health` and
`/ready`. The identifier-free operator diagnostic is:

```powershell
uv run opspilot route-check --account-alias Edu_687 --format summary
```

## Validation

```powershell
uv run ruff format --check .
uv run ruff check .
uv run --extra agent mypy src tests
uv run --extra agent pytest
uv build
```

## Infrastructure

The M1 bootstrap and dev foundation are applied, with separate state prefixes in the protected
GCS backend. M2 uses one immutable image across three applied private Cloud Run services. The
remote state contains 31 managed resources after the M5 IAM apply; operator and hosted read-only
plans are zero drift.
Real project, billing, GitHub, and state identifiers are supplied through environment variables,
ignored backend files, and GitHub repository variables.

M4 Terraform is default-off. Enabling it in a separately reviewed plan adds exactly one protected
knowledge bucket, one Agent Search data store, one metadata schema, and one Standard Search engine.
Approval 1 does not create those resources or upload a document.

M5 Terraform remains default-off in source. The approved live environment manages one investigator
custom role, its project binding, and one operator Token Creator binding scoped only to the
investigator service account. One live SCN-001 collection passed through short-lived
impersonation with no service-account key.

```powershell
terraform fmt -check -recursive infra/terraform
terraform -chdir=infra/terraform/bootstrap init -backend=false
terraform -chdir=infra/terraform/bootstrap validate
terraform -chdir=infra/terraform/bootstrap test
terraform -chdir=infra/terraform/environments/dev init -backend=false
terraform -chdir=infra/terraform/environments/dev validate
terraform -chdir=infra/terraform/environments/dev test
```

See `docs/operations/demo-services.md` for the workload runbook and
`docs/operations/cloud-run-mvp-recovery.md` for controlled endpoint recovery.

## Safety boundary

- Only synthetic ecommerce fixtures are included.
- Service names and time windows are validated against `config/services.yaml`.
- Logs are redacted before they become evidence.
- Reports can recommend an approval-gated action but R0 exposes no remediation endpoint.
- Google account, project, OAuth, and billing identifiers are never stored in the repository.
- Pull requests run static Terraform checks without cloud credentials.
- Pull requests build the Linux/amd64 image and exercise all three roles only on a local network.
- The live Terraform plan workflow is manual, uses WIF, and has no apply or state-write identity.
- The live plan is additionally gated by `TF_M2_IMAGE_READY=true` and remains manual/read-only.
- M3 scenario deployment additionally requires `TF_M3_IMAGE_READY=true`. The variable is enabled
  only after the reviewed three-service update and remains part of the manual read-only plan gate.
- M4 hosted plans additionally require `TF_M4_KNOWLEDGE_READY=true`; it remains unset until the
  separate Search apply, import, and live smoke approval completes.
- M5 hosted plans additionally require `TF_M5_LIVE_EVIDENCE_READY=true`; it is enabled after the
  investigator IAM apply and bounded live acceptance passed.
- M6 model calls are default-off. Offline CI uses the deterministic fake model, and the optional
  Vertex path requires a process-scoped gate plus a separate live-model approval.
