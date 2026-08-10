.PHONY: install run build test lint typecheck replay access-check demo-up demo-smoke demo-down image-build infra-fmt infra-validate infra-test infra-lint infra-plan

TERRAFORM ?= terraform
TFLINT_IMAGE ?= ghcr.io/terraform-linters/tflint:v0.64.0
DEMO_IMAGE ?= opspilot-demo:local

install:
	uv sync --frozen

run:
	uv run opspilot serve

build:
	uv build

test:
	uv run pytest

lint:
	uv run ruff format --check .
	uv run ruff check .

typecheck:
	uv run mypy src tests

replay:
	uv run opspilot replay --scenario SCN-001 --format markdown

access-check:
	uv run opspilot access-check --format summary

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
