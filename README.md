# Oecophylla

Social network with intelligent news feed recommendation and multi-layer content moderation.
Phase 0+1 (foundation + identity + content) — see `docs/superpowers/specs/2026-05-25-foundation-identity-content-design.md`.

## Quick start

```bash
cp .env.example .env
make up
make seed   # optional — 50 users / 100 posts / 200 follows
```

Browse:
- Frontend: http://localhost:3000
- Envoy API gateway: http://localhost:8080
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001 (admin / password from `.env`)

## Service URLs (dev override exposes raw ports)

| Service | Internal | Host-exposed via `compose.dev.yaml` |
|---|---|---|
| auth-service | http://auth-service:8001 | http://localhost:8001 |
| user-service | http://user-service:8002 | http://localhost:8002 |
| content-service | http://content-service:8003 | http://localhost:8003 |
| interaction-service | http://interaction-service:8004 | http://localhost:8004 |
| feed-service | http://feed-service:8005 | http://localhost:8005 |
| recommendation-api | http://recommendation-api:8090 | http://localhost:8090 |
| feature-store-worker | (worker — Kafka consumer) | — |
| cache-invalidator | (worker — Kafka consumer) | — |
| postgres | postgres:5432 | localhost:5432 |
| redis | redis:6379 | localhost:6379 |
| kafka | kafka:9092 | localhost:9092 |

`GET /api/v1/feed?cursor=&limit=` (auth required) returns the personalized feed.
The `source` field is `cache` (Redis hit), `personalized` (recommendation-api),
or `fallback` (Redis trending or recent published).

To verify the fallback ladder:

```bash
docker compose stop recommendation-api
curl -i --cookie cookies.txt http://localhost:8080/api/v1/feed?limit=5
# expect HTTP 200 and `"source":"fallback"` in the body
docker compose start recommendation-api
```

Kafka smoke (consumer / producer) must run inside the compose network because
the `kafka` service hostname is not resolvable from macOS hosts:

```bash
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 --topic oecophylla.interactions --from-beginning --max-messages 10
```

## Smoke tests

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d postgres redis kafka migrate init-topics
cd backend && cargo run -p auth-service & cargo run -p user-service & cargo run -p content-service &
sleep 5
make test
```

## Layout

```
backend/  Cargo workspace — auth, user, content services + common crate
frontend/ SvelteKit (adapter-node) + Tailwind, Apple Glass UI port
envoy/    Gateway config
infra/    Prometheus + Grafana provisioning, Kafka init script
migrations/  sqlx migrations (shared schema)
scripts/  Seed + utility Python
docs/superpowers/{specs,plans}/  Design docs + implementation plans
```

## What is in Phase 0+1 and what is not

Phase 0+1 ships: PG 18 + Redis 7 + Kafka 4 KRaft + Envoy + 3 Rust services + SvelteKit
frontend. Auth, profile, follow, post-create and post-detail are wired end-to-end.
Feed, admin, and mobile pages render with mock data. Recommendation, interactions,
moderation, notifications, analytics belong to Phase 2-4.
