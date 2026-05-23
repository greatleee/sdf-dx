.PHONY: install lint type test test-integration

install:
	uv pip install -e ".[dev]"

lint:
	ruff check .
	ruff format --check .
	lint-imports

type:
	mypy

test:
	pytest

test-integration:
	pytest --integration

ci: lint type test
