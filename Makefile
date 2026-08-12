.PHONY: install install-agent run build test lint typecheck replay scenario-replay-all scenario-run scenario-remediation-plan scenario-remediation-abort-plan remediation-eval m8-release-preflight m8-release-post-apply m8-release-e2e m8-release-publish knowledge-validate knowledge-sync knowledge-smoke evidence-smoke agent-run agent-eval agent-eval-portfolio agent-runtime-package cleanup-plan portfolio-release-check portfolio-release-publish portfolio-demo demo-up demo-smoke demo-down image-build infra-fmt infra-validate infra-test infra-lint infra-plan

TERRAFORM ?= terraform
TFLINT_IMAGE ?= ghcr.io/terraform-linters/tflint:v0.64.0
DEMO_IMAGE ?= opspilot-demo:local

install:
	uv sync --frozen

install-agent:
	uv sync --frozen --extra agent

run:
	uv run opspilot serve

build:
	uv build

test:
	uv run --extra agent pytest

lint:
	uv run ruff format --check .
	uv run ruff check .

typecheck:
	uv run --extra agent mypy src tests

replay:
	uv run opspilot replay --scenario SCN-001 --format markdown

scenario-replay-all:
	@for id in 001 002 003 004 005 006 007; do uv run opspilot replay --scenario SCN-$$id --format json > /dev/null || exit 1; done

scenario-run:
	uv run opspilot scenario run --scenario SCN-001 --auth local --format summary

scenario-remediation-plan:
	uv run --extra agent opspilot scenario prepare --scenario SCN-008 --mode plan --auth gcloud

scenario-remediation-abort-plan:
	uv run --extra agent opspilot scenario abort --scenario SCN-008 --mode plan --auth gcloud

remediation-eval:
	uv run opspilot remediation eval --suite remediation --format summary

m8-release-preflight:
	uv run python scripts/m8_release.py preflight --output .tmp/m8-release

m8-release-post-apply:
	uv run python scripts/m8_release.py verify --phase post-apply --output .tmp/m8-release

m8-release-e2e:
	uv run python scripts/m8_release.py verify --phase e2e --output .tmp/m8-release

m8-release-publish:
	uv run python scripts/m8_release.py publish --output .tmp/m8-release

knowledge-validate:
	uv run opspilot knowledge validate --format summary

knowledge-sync:
	uv run opspilot knowledge sync --env dev --mode plan --format summary

knowledge-smoke:
	uv run opspilot knowledge smoke --format summary

evidence-smoke:
	uv run opspilot evidence smoke --scenario SCN-001 --env dev --format summary

agent-run:
	uv run --extra agent opspilot agent run --scenario SCN-001 --format summary

agent-eval:
	uv run --extra agent opspilot agent eval --suite core --format summary

agent-eval-portfolio:
	uv run --extra agent opspilot agent eval --suite portfolio --format summary --output .tmp/evaluation

agent-runtime-package:
	uv run --extra agent opspilot agent runtime package --output .tmp/m7-runtime

cleanup-plan:
	uv run opspilot cleanup plan --format summary

portfolio-release-check:
	uv run python scripts/portfolio_release.py check --output .tmp/portfolio-release

portfolio-release-publish:
	uv run python scripts/portfolio_release.py check --include-infra --publish --output .tmp/portfolio-release

portfolio-demo:
	uv run python scripts/portfolio_demo.py

image-build:
	docker build --platform linux/amd64 -t $(DEMO_IMAGE) .

demo-up: image-build
	docker compose up -d --no-build

demo-smoke:
	docker compose exec -T -e OPSPILOT_ORDER_URL=http://127.0.0.1:8080 order opspilot demo load --orders 10 --concurrency 2 --auth local

demo-down:
	docker compose down --remove-orphans

infra-fmt:
	$(TERRAFORM) fmt -check -recursive infra/terraform

infra-validate:
	$(TERRAFORM) -chdir=infra/terraform/bootstrap init -backend=false -input=false
	$(TERRAFORM) -chdir=infra/terraform/bootstrap validate
	$(TERRAFORM) -chdir=infra/terraform/environments/dev init -backend=false -input=false
	$(TERRAFORM) -chdir=infra/terraform/environments/dev validate

infra-test:
	$(TERRAFORM) -chdir=infra/terraform/bootstrap test
	$(TERRAFORM) -chdir=infra/terraform/environments/dev test

infra-lint:
	docker run --rm -v "$(CURDIR):/data" -w /data $(TFLINT_IMAGE) --recursive --config=/data/.tflint.hcl

infra-plan:
	@echo "Use docs/operations/bootstrap.md. This target never applies infrastructure."
