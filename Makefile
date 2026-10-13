# CloudCostLens developer tasks.
PY ?= python3.13
VENV ?= .venv
BIN := $(VENV)/bin
PNPM ?= pnpm

.PHONY: help venv install install-web lint format test test-integration typecheck \
        web-dev web-build web-typecheck web-lint web-test migrate revision \
        up down logs api worker seed bootstrap-owner clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

venv: ## Create the local Python virtual environment
	$(PY) -m venv $(VENV)

install: venv ## Install Python runtime + dev dependencies
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements-dev.txt

install-web: ## Install web dependencies with pnpm
	$(PNPM) install

lint: ## Run ruff lint
	$(BIN)/ruff check .

format: ## Auto-format with ruff
	$(BIN)/ruff format .
	$(BIN)/ruff check --fix .

test: ## Run unit tests (integration excluded)
	$(BIN)/pytest -q

test-integration: ## Run integration tests (requires PostgreSQL)
	$(BIN)/pytest -q -m integration

typecheck: ## Python import/compile sanity check
	$(BIN)/python -m compileall -q core workers apps/api

web-dev: ## Start the Next.js dev server
	$(PNPM) --dir apps/web dev

web-build: ## Production build of the web app
	$(PNPM) --dir apps/web build

web-typecheck: ## TypeScript type check
	$(PNPM) --dir apps/web typecheck

web-lint: ## ESLint for the web app
	$(PNPM) --dir apps/web lint

web-test: ## Vitest for the web app
	$(PNPM) --dir apps/web test

migrate: ## Apply database migrations
	$(BIN)/alembic upgrade head

revision: ## Autogenerate a migration (make revision m="message")
	$(BIN)/alembic revision --autogenerate -m "$(m)"

api: ## Run the API locally
	$(BIN)/uvicorn apps.api.main:app --reload --port 8000

worker: ## Run a worker locally (make worker w=discovery)
	$(BIN)/python -m workers.cli $(w)

seed: ## Seed demo data (requires --confirm)
	$(BIN)/python scripts/seed_demo.py --confirm

bootstrap-owner: ## Create the first owner account (interactive)
	$(BIN)/python scripts/bootstrap_owner.py

up: ## Start the full stack with Docker Compose
	docker compose up --build -d

down: ## Stop the stack
	docker compose down

logs: ## Tail stack logs
	docker compose logs -f --tail=100

clean: ## Remove caches and build artifacts
	rm -rf $(VENV) .pytest_cache .ruff_cache apps/web/.next apps/web/node_modules
