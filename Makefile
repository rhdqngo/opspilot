.PHONY: install install-agent run build test lint typecheck replay scenario-replay-all scenario-run access-check knowledge-validate knowledge-sync knowledge-smoke evidence-smoke agent-run agent-eval agent-diagnose agent-accept agent-runtime-validate agent-runtime-smoke agent-runtime-probe agent-runtime-package demo-up demo-smoke demo-down image-build infra-fmt infra-validate infra-test infra-lint infra-plan

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

access-check:
	uv run opspilot access-check --format summary

knowledge-validate:
	uv run opspilot knowledge validate --format summary

knowledge-sync:
	uv run opspilot knowledge sync --env dev --mode plan --format summary

knowledge-smoke:
	uv run opspilot knowledge smoke --backend local --env dev --format summary

evidence-smoke:
	uv run opspilot evidence smoke --backend fixture --scenario SCN-001 --env dev --format summary

agent-run:
	uv run --extra agent opspilot agent run --backend fixture --scenario SCN-001 --model fake --format summary

agent-eval:
	uv run --extra agent opspilot agent eval --suite fixture --model fake --format summary

agent-diagnose:
	uv run --extra agent opspilot agent diagnose --account-alias Edu_687 --format summary

agent-accept:
	uv run --extra agent opspilot agent accept --suite m6-core --model fake --format summary

agent-runtime-validate:
	uv run --extra agent opspilot agent runtime validate --format summary

agent-runtime-smoke:
	uv run --extra agent opspilot agent runtime smoke --backend fixture --format summary

agent-runtime-probe:
	uv run --extra agent opspilot agent runtime probe --format summary

agent-runtime-package:
	uv run --extra agent opspilot agent runtime package --output .tmp/m7-runtime

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
