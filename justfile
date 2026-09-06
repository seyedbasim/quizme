# Common tasks. `brew install just` or use the raw commands.

default:
    @just --list

setup:
    uv sync --extra dev

test:
    uv run pytest

lint:
    uv run ruff check .
    uv run ruff format --check .

typecheck:
    uv run mypy quizme

check: lint typecheck test

web:
    uv run uvicorn quizme.web.app:app --reload

# Requires DATABASE_URL. Runs the forward-only migrations (AD-17).
migrate:
    uv run alembic upgrade head

new-migration message:
    uv run alembic revision -m "{{message}}"
