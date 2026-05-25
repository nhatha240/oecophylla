.DEFAULT_GOAL := help
SHELL := /bin/bash
COMPOSE := docker compose
APP := app
DB := db
BASE_URL ?= http://localhost:3000

.PHONY: help up down restart clean logs logs-db ps build check fmt clippy shell psql migrate-add smoke

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Targets:\n"} /^[a-zA-Z_-]+:.*##/ { printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

up: ## Build + start stack (db + app), follow app logs
	$(COMPOSE) up --build

up-d: ## Build + start stack in background
	$(COMPOSE) up --build -d

down: ## Stop and remove containers (keep volumes)
	$(COMPOSE) down

clean: ## Stop containers AND wipe volumes (pgdata + caches)
	$(COMPOSE) down -v

restart: ## Restart the app container only
	$(COMPOSE) restart $(APP)

ps: ## Show container status
	$(COMPOSE) ps

logs: ## Tail app logs
	$(COMPOSE) logs -f $(APP)

logs-db: ## Tail db logs
	$(COMPOSE) logs -f $(DB)

shell: ## Open a bash shell inside the app container
	$(COMPOSE) exec $(APP) bash

psql: ## Open psql against the running db
	$(COMPOSE) exec $(DB) psql -U app -d app

migrate-add: ## Create a new migration: make migrate-add NAME=add_users
	@if [ -z "$(NAME)" ]; then echo "Usage: make migrate-add NAME=<migration_name>"; exit 1; fi
	$(COMPOSE) exec $(APP) sqlx migrate add $(NAME)

build: ## Cargo build on host (no DB required)
	cargo build

check: ## Cargo check on host
	cargo check

fmt: ## Format code
	cargo fmt

clippy: ## Lint with clippy
	cargo clippy --all-targets -- -D warnings

smoke: ## Run full CRUD smoke test against running stack
	@set -e; \
	echo "=== HEALTH ==="; \
	curl -sS -w "\nHTTP %{http_code}\n" $(BASE_URL)/health; \
	echo "=== POST /items ==="; \
	RESP=$$(curl -sS -X POST $(BASE_URL)/items -H 'Content-Type: application/json' -d '{"name":"smoke","description":"hi"}'); \
	echo "$$RESP"; \
	ID=$$(echo "$$RESP" | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['id'])"); \
	echo "ITEM_ID=$$ID"; \
	echo "=== GET /items ==="; \
	curl -sS -w "\nHTTP %{http_code}\n" $(BASE_URL)/items; \
	echo "=== GET /items/$$ID ==="; \
	curl -sS -w "\nHTTP %{http_code}\n" $(BASE_URL)/items/$$ID; \
	echo "=== PUT /items/$$ID ==="; \
	curl -sS -w "\nHTTP %{http_code}\n" -X PUT $(BASE_URL)/items/$$ID -H 'Content-Type: application/json' -d '{"name":"smoke-2","description":null}'; \
	echo "=== DELETE /items/$$ID ==="; \
	curl -sS -w "HTTP %{http_code}\n" -X DELETE $(BASE_URL)/items/$$ID; \
	echo "=== GET deleted (expect 404) ==="; \
	curl -sS -w "\nHTTP %{http_code}\n" $(BASE_URL)/items/$$ID
