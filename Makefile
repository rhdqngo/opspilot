.PHONY: install run build test lint typecheck replay access-check infra-fmt infra-validate infra-test infra-lint infra-plan

TERRAFORM ?= terraform
TFLINT_IMAGE ?= ghcr.io/terraform-linters/tflint:v0.64.0

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
