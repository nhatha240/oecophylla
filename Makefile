.PHONY: up down logs ps test fmt lint sqlx-prepare seed clean

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

fmt:
	cd backend && cargo fmt
	cd frontend && pnpm prettier --write .

lint:
	cd backend && cargo clippy --workspace -- -D warnings
	cd frontend && pnpm lint

sqlx-prepare:
	cd backend && cargo sqlx prepare --workspace -- --all-targets

seed:
	docker compose --profile tools run --rm scripts seed_phase1.py

clean:
	docker compose down -v
