.PHONY: help build up down logs shell clean env dev test audit

## ── Variables ───────────────────────────────────────────────────────────────
IMAGE  := simple-recipes
COMPOSE := docker compose

## ── Help ────────────────────────────────────────────────────────────────────
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

## ── Docker ──────────────────────────────────────────────────────────────────
env: ## Create .env from .env.example (only if .env doesn't exist)
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		python3 -c "import secrets; \
			data = open('.env').read(); \
			data = data.replace('change-me-with-a-long-random-string', secrets.token_hex(32)); \
			open('.env', 'w').write(data)"; \
		echo "✓ .env created with a random SECRET_KEY — review and adjust PORT if needed."; \
	else \
		echo ".env already exists, skipping."; \
	fi

build: env ## Build the Docker image
	$(COMPOSE) build

up: env ## Start the service in the background
	$(COMPOSE) up -d
	@echo "✓ Service started — open http://localhost:$$(grep '^PORT' .env | cut -d= -f2 || echo 8080)"

down: ## Stop and remove containers
	$(COMPOSE) down

logs: ## Follow container logs
	$(COMPOSE) logs -f

shell: ## Open a shell inside the running container
	$(COMPOSE) exec app /bin/bash

clean: ## Remove the built image
	$(COMPOSE) down --rmi local --volumes --remove-orphans

restart: down up ## Restart the service

## ── Local development (no Docker) ───────────────────────────────────────────
HTMX_SHA256 := 491955cd1810747d7d7b9ccb936400afb760e06d25d53e4572b64b6563b2784e
PICO_SHA256 := dd5fd5591afd81ee21dcc117ad85c014dc3f1f19dc2d7b7d101ea0acc29274c2

dev-assets: ## Download HTMX and Pico.css for local development (digest-checked)
	@mkdir -p backend/static/js backend/static/css
	@curl -fsSL -o backend/static/js/htmx.min.js \
		https://unpkg.com/htmx.org@2.0.3/dist/htmx.min.js
	@echo "$(HTMX_SHA256)  backend/static/js/htmx.min.js" | sha256sum -c -
	@curl -fsSL -o backend/static/css/pico.min.css \
		https://unpkg.com/@picocss/pico@2.0.6/css/pico.min.css
	@echo "$(PICO_SHA256)  backend/static/css/pico.min.css" | sha256sum -c -
	@echo "✓ Frontend assets downloaded and verified."

test: ## Run unit tests locally (requires Python 3.12+)
	@cd backend && \
		pip install -r requirements.txt pytest -q && \
		PYTHONPATH=. DATA_DIR=/tmp/simple-recipes-test \
		SECRET_KEY=test-secret-key-local-at-least-32-chars COOKIE_SECURE=false \
		pytest tests/ -v

dev: dev-assets ## Run locally without Docker (requires Python 3.12+)
	@cd backend && \
		pip install -r requirements.txt -q && \
		DATA_DIR=../data SECRET_KEY=dev-secret-key-not-for-production-32c \
		COOKIE_SECURE=false ENABLE_DOCS=true \
		uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

audit: ## Scan the pinned dependencies for known vulnerabilities
	@pip install pip-audit -q
	@cd backend && pip-audit -r requirements.txt --strict
