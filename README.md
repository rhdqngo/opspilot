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

## Validation

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
uv build
```

## Infrastructure

The M1 bootstrap and dev foundation are applied, with separate state prefixes in the protected
GCS backend. M2 Cloud Run resources are defined behind `deploy_demo=false`; no image has been
pushed and no demo workload has been applied. A read-only plan with the gate disabled has zero
resource and output changes.
Real project, billing, GitHub, and state identifiers are supplied through environment variables,
ignored backend files, and GitHub repository variables.

```powershell
terraform fmt -check -recursive infra/terraform
terraform -chdir=infra/terraform/bootstrap init -backend=false
terraform -chdir=infra/terraform/bootstrap validate
terraform -chdir=infra/terraform/bootstrap test
terraform -chdir=infra/terraform/environments/dev init -backend=false
terraform -chdir=infra/terraform/environments/dev validate
terraform -chdir=infra/terraform/environments/dev test
```

See `docs/operations/demo-services.md` for the local workflow and separate Approval 2 boundary.

## Safety boundary

- Only synthetic ecommerce fixtures are included.
- Service names and time windows are validated against `config/services.yaml`.
- Logs are redacted before they become evidence.
- Reports can recommend an approval-gated action but R0 exposes no remediation endpoint.
- Google account, project, OAuth, and billing identifiers are never stored in the repository.
- Pull requests run static Terraform checks without cloud credentials.
- Pull requests build the Linux/amd64 image and exercise all three roles only on a local network.
- The live Terraform plan workflow is manual, uses WIF, and has no apply or state-write identity.
- The live plan is additionally gated by `TF_M2_IMAGE_READY=true`; that variable is not configured
  in Approval 1. Future image push and cloud apply remain local and separately approved.
