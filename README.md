# OpsPilot

Evidence-grounded local skeleton for an enterprise incident commander. R0 runs entirely
against deterministic synthetic fixtures and cannot perform cloud writes or remediation.

## Local setup

```powershell
uv sync --frozen
uv run opspilot replay --scenario SCN-001 --format markdown
uv run opspilot serve
```

The API is available at `http://127.0.0.1:8000`; use `/healthz`, `/readyz`, and `/docs` for
local verification.

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
GCS backend. The dev foundation contains only API management, an empty Docker repository, an
unprivileged investigator identity, an email notification channel, and the protected KRW budget.
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

See `docs/operations/bootstrap.md` for the approval-gated state migration and apply sequence.

## Safety boundary

- Only synthetic ecommerce fixtures are included.
- Service names and time windows are validated against `config/services.yaml`.
- Logs are redacted before they become evidence.
- Reports can recommend an approval-gated action but R0 exposes no remediation endpoint.
- Google account, project, OAuth, and billing identifiers are never stored in the repository.
- Pull requests run static Terraform checks without cloud credentials.
- The live Terraform plan workflow is manual, uses WIF, and has no apply or state-write identity.
- Hosted plans read the dev remote state with `-lock=false`; the WIF identity cannot apply or write
  state. Future cloud applies remain local and separately approved.
