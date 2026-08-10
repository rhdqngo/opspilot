.PHONY: install run build test lint typecheck replay access-check

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
