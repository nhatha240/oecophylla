.PHONY: up down logs ps test test-python test-phase-2b test-phase-3 fmt lint deny audit sqlx-prepare seed clean

up:
	docker compose -f compose.yaml -f compose.dev.yaml up -d --build

down:
	docker compose -f compose.yaml -f compose.dev.yaml down

logs:
	docker compose logs -f --tail=200

ps:
	docker compose ps

test:
	cd backend && cargo test --workspace --no-fail-fast
	cd frontend && pnpm vitest run

test-python:
	cd recommendation_api && pytest
	cd workers/feature_store_worker && pytest
	cd workers/nlp_worker && pytest

test-phase-2b:
	cd backend && cargo test --workspace --no-fail-fast
	cd frontend && pnpm run check && pnpm run build
	$(MAKE) test-python

test-phase-3:
	cd backend && cargo test --workspace --no-fail-fast
	cd frontend && pnpm run check && pnpm run build
	$(MAKE) test-python
	bash scripts/smoke_phase3.sh

fmt:
	cd backend && cargo fmt
	cd frontend && pnpm prettier --write .

lint:
	cd backend && cargo clippy --workspace -- -D warnings
	cd frontend && pnpm lint

deny:
	cd backend && cargo deny check

audit:
	cd backend && cargo audit

sqlx-prepare:
	cd backend && cargo sqlx prepare --workspace -- --all-targets

seed:
	docker compose --profile tools run --rm scripts seed_phase1.py

clean:
	docker compose down -v
