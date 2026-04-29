.PHONY: help build up down logs shell clean env dev

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
dev-assets: ## Download HTMX and Pico.css for local development
	@mkdir -p backend/static/js backend/static/css
	@curl -fsSL -o backend/static/js/htmx.min.js \
		https://unpkg.com/htmx.org@2.0.3/dist/htmx.min.js
	@curl -fsSL -o backend/static/css/pico.min.css \
		https://unpkg.com/@picocss/pico@2.0.6/css/pico.min.css
	@echo "✓ Frontend assets downloaded."

dev: dev-assets ## Run locally without Docker (requires Python 3.12+)
	@cd backend && \
		pip install -r requirements.txt -q && \
		DATA_DIR=../data SECRET_KEY=dev-secret COOKIE_SECURE=false \
		uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
