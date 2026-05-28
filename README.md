# Oecophylla

Social network with intelligent news feed recommendation and multi-layer content moderation.
Phases 0–4 shipped — see `CLAUDE.md` "Current State" for what is live and what is still open.
Original foundation spec: `docs/superpowers/specs/2026-05-25-foundation-identity-content-design.md`.

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
| moderation-service | http://moderation-service:8006 | http://localhost:8006 |
| notification-service | http://notification-service:8007 | http://localhost:8007 |
| recommendation-api | http://recommendation-api:8090 | http://localhost:8090 |
| feature-store-worker | (worker — Kafka consumer) | — |
| nlp-worker | (worker — Kafka consumer) | — |
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

## Phase 3 — moderation, notifications, NLP

- **moderation-service** (:8006, admin-only) — `/admin/reports`, `/admin/reports/:id/resolve`
  (`dismiss` / `hide_post` / `warn_author` / `ban_author`), `/admin/audit-logs`. Each resolve
  runs the report transition + `audit_logs` insert in one transaction, then publishes
  `oecophylla.moderation.action`.
- **notification-service** (:8007) — `/api/v1/notifications` (list, mark-read, read-all,
  unread-count) plus the live SSE stream `/api/v1/notifications/stream`. Consumes
  `interactions`, `user.followed`, and `moderation.action`.
- **nlp-worker** — consumes `oecophylla.content.created`, infers topics from EN+VI keyword
  maps, and writes `posts.topics` asynchronously (idempotent: skips posts that already have
  topics). Topic inference was removed from the content-service hot path.

### SSE caveat (single replica)

`notification-service` keeps SSE fan-out state in-process
(`Mutex<HashMap<UserId, Vec<broadcast::Sender>>>`), so it ships **single-replica**
(`deploy.replicas: 1`). A notification produced for a user only reaches the replica that user
is connected to. Envoy routes the stream with `timeout: 0s` / `idle_timeout: 3600s` and the
handler emits a heartbeat every 25s. Phase 4 moves fan-out to Redis pub/sub for horizontal scale.

Kafka topics still are not reachable from the macOS host — inspect `oecophylla.moderation.action`
from inside the network:

```bash
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 --topic oecophylla.moderation.action --from-beginning --max-messages 5
```

## Smoke tests

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d postgres redis kafka migrate init-topics
cd backend && cargo run -p auth-service & cargo run -p user-service & cargo run -p content-service &
sleep 5
make test
```

Full Phase 3 integration smoke (requires the whole stack up):

```bash
docker compose -f compose.yaml -f compose.dev.yaml up -d --build
bash scripts/smoke_phase3.sh
```

## Layout

```
backend/                 Cargo workspace — 8 Rust services + common crate
backend/crates/common/   Shared auth, config, Kafka, Redis, metrics, middleware
backend/services/        auth, user, content, interaction, feed, moderation, notification, cache-invalidator
frontend/                SvelteKit (adapter-node) + Tailwind
workers/                 Python — feature-store-worker, nlp-worker
recommendation-api/      Python FastAPI — ranking, feature store
analytics-service/       Python FastAPI — dashboard metrics + Prometheus export
envoy/                   Envoy v1.32 API gateway config
infra/                   Prometheus + Grafana provisioning
migrations/              11 sqlx migrations (shared schema)
scripts/                 Seed, evaluate, smoke tests
docs/superpowers/        Design specs + implementation plans per phase
```

## Current state (Phases 0–4 complete)

Phases 0 through 4 are shipped. See `CLAUDE.md` "Current State" for the authoritative
list of what runs in production and what is still open.

**Shipped and running:**

- Auth, profiles, follow graph, post CRUD — fully wired end-to-end.
- Feed — real recommendation via `recommendation-api` with fallback ladder
  (cache → personalized → Redis trending → recent published). Supports
  `?mode=following` for followed-users feed.
- Interactions — like, comment, share, save, hide, report. Cursor-based
  comment threads with SSE live updates.
- Moderation — admin report queue, resolve actions (dismiss/hide/warn/ban),
  audit log. All admin actions go through `moderation-service` with
  transactional audit logging.
- Notifications — in-app list, mark-read, unread-count, SSE live stream.
  Consumes `interactions`, `user.followed`, and `moderation.action` topics.
- NLP — async topic tagging + safety scoring via `nlp-worker` on
  `content.created` events.
- Observability — Prometheus metrics on all 7 HTTP services, Grafana dashboard
  with 10 panels (RPS, P95 latency, error rate, cache hit rate, interactions,
  moderation, notifications, NLP).
- Analytics — `analytics-service` aggregates dashboard metrics + Prometheus export.
- Search — full-text post search via `content-service` with `ts_rank`.

**Still mock / not yet finished:**

- `/m` route — mobile preview page, renders placeholder UI.
- Settings page — password change and account deletion are placeholder, no
  backend wiring.
- E2E tests — none exist yet. Unit/integration coverage varies by service.
- Counter drift recompute job — periodic SQL heal for `like_count` etc. not yet
  implemented.
- Toast component — `PostActionBar` still uses `alert()` for rollback feedback.
