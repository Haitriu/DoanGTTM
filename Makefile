.PHONY: setup dev test test-int lint fmt demo

setup:
	uv sync
	pre-commit install

dev:
	docker compose up -d
	uv run --directory apps/api uvicorn main:app --reload

test:
	uv run pytest tests/unit tests/property

test-int:
	uv run pytest tests/integration

test-golden:
	uv run pytest tests/golden

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy packages/core

fmt:
	uv run ruff format .
	uv run ruff check --fix .

demo:
	uv run --directory apps/cli voltrail plan --from "Hà Nội" --to "Đà Nẵng" --vehicle vf8-eco --soc 92
