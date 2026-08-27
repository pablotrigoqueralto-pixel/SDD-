.PHONY: install dev lint format typecheck test test-unit test-integration migrate migration seed openapi e2e-seed

install:
	uv sync --all-extras

dev:
	uv run uvicorn app.asgi:app --reload --port 8000

lint:
	uv run ruff check . && uv run ruff format --check .

format:
	uv run ruff check --fix . && uv run ruff format .

typecheck:
	uv run mypy app tests

test:
	uv run pytest --cov=app --cov-report=term-missing

test-unit:
	uv run pytest tests/unit

test-integration:
	uv run pytest tests/integration -m integration

migrate:
	uv run alembic upgrade head

# usage: make migration m="add_lost_reason_to_opportunities"
migration:
	uv run alembic revision --autogenerate -m "$(m)"

seed:
	uv run python -m app.infrastructure.db.seed

openapi:
	uv run python -m app.tooling.export_openapi ../ai-specs/specs/api-spec.yml

e2e-seed:
	uv run python -m app.tooling.e2e_seed
