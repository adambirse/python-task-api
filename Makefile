.PHONY: install run test lint format typecheck migrate

install:  ## Create a dev install (run inside a virtualenv)
	pip install -e ".[dev]"

run:  ## Start the API with auto-reload
	uvicorn app.main:app --reload

test:
	pytest

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

typecheck:
	mypy app

migrate:  ## Apply database migrations
	alembic upgrade head
