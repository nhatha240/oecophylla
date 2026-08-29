.PHONY: up down logs ps test test-python test-phase-2b test-phase-3 test-ai-pipeline smoke-ai-telemetry evaluate-ai train-ai prune-ai-telemetry fmt lint deny audit sqlx-prepare seed clean

AI_DATASET ?= artifacts/datasets/dataset.parquet
AI_ARTIFACT ?= artifacts/models/current
AI_REPORT ?= artifacts/models/current/comparison

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

test-ai-pipeline:
	cd ai_pipeline && uv run --with-requirements requirements.txt pytest -q

smoke-ai-telemetry:
	bash scripts/smoke_ai_telemetry.sh

train-ai:
	uv run --with-requirements ai_pipeline/requirements.txt python -m ai_pipeline.train --dataset "$(AI_DATASET)" --output "$(AI_ARTIFACT)"

evaluate-ai:
	uv run --with-requirements ai_pipeline/requirements.txt python -m ai_pipeline.evaluate --dataset "$(AI_DATASET)" --artifact "$(AI_ARTIFACT)" --output "$(AI_REPORT)"

prune-ai-telemetry:
	docker compose exec -T postgres psql -U "$${POSTGRES_USER:-oecophylla}" -d "$${POSTGRES_DB:-oecophylla}" -v ON_ERROR_STOP=1 -c "SELECT * FROM prune_recommendation_telemetry(INTERVAL '$${TELEMETRY_RETENTION_DAYS:-180} days');"

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
