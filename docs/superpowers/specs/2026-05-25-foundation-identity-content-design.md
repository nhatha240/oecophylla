# Oecophylla — Foundation, Identity & Content (Phase 0+1) Design

**Status:** Draft, pending user review
**Date:** 2026-05-25
**Scope:** Phase 0 (infrastructure) + Phase 1 (identity & content) of the Oecophylla microservices social network. Subsequent phases (interactions/feed/recommendation, moderation/notifications, analytics) get their own spec → plan → implementation cycles.

---

## 1. Goals & non-goals

### 1.1 Goals
- Stand up a reproducible local stack (`docker compose up` from cold to healthy in ≤ 90s).
- Three independent Rust Axum services — `auth-service`, `user-service`, `content-service` — sharing a single Postgres 18 database via shared sqlx migrations, with a `crates/common` workspace crate for cross-cutting concerns.
- Single edge gateway (Envoy) for routing and per-IP rate limiting.
- Kafka in KRaft mode (no Zookeeper), with producers wired for `content.created` and `user.followed` events.
- SvelteKit (adapter-node, SSR) frontend ported from the existing "Apple Glass" HTML/JSX UI. Pages backed by Phase-1 services are wired live; pages whose backend lives in later phases render against mock data but do not 500.
- HttpOnly cookie auth with rotating refresh tokens.
- Smoke-level tests sufficient to prove the happy path and key failure modes on every commit.

### 1.2 Non-goals (deferred to later phases)
- Feed ranking, recommendation API, interaction events, Redis feed cache (Phase 2).
- NLP topic tagging, safety scoring, moderation queue, notifications, audit log (Phase 3).
- Analytics, evaluation scripts, full seed (500 users / 2000 posts / 50k interactions), OpenTelemetry collector (Phase 4).
- Media upload service (separate sub-project — likely MinIO).
- Production deployment (Kubernetes, TLS, managed PG/Redis/Kafka).

---

## 2. Architecture & topology

```
Browser
  │
  ▼
SvelteKit (Node SSR, :3000) ──── static assets
  │ fetch /api/v1/* (cookie forwarded via hooks.server.ts)
  ▼
Envoy gateway (:8080)
  ├─ /api/v1/auth/*    → auth-service    (:8001)
  ├─ /api/v1/users/*   → user-service    (:8002)
  └─ /api/v1/posts/*   → content-service (:8003)
                                │ rdkafka produce
                                ▼
                       Kafka (KRaft, :9092, controller :9093 internal)
                                ▲
                                │ (Phase 2 consumers)
        all 3 services ──read/write──►  Postgres 18 (:5432)
                              ──cache──►  Redis 7    (:6379)

Observability: prometheus (:9090), grafana (:3001)
```

Compose services (12 entries; 2 are one-shot init jobs): `postgres`, `redis`, `kafka`, `migrate` (one-shot), `init-topics` (one-shot), `envoy`, `auth-service`, `user-service`, `content-service`, `frontend`, `prometheus`, `grafana`. (Zookeeper intentionally omitted — see §10.10.)

### 2.1 Cargo workspace layout

```
backend/
├── Cargo.toml                 # [workspace]
├── crates/common/             # shared library (no binary)
├── services/auth-service/
├── services/user-service/
└── services/content-service/
```

### 2.2 Frontend layout

```
frontend/
├── svelte.config.js  (adapter-node)
├── src/
│   ├── app.html, app.css      # tokens + glass utilities (ported)
│   ├── hooks.server.ts        # cookie forward + refresh-on-401
│   ├── lib/{api.ts, stores/, components/, types.ts, mock/}
│   └── routes/                # see §6 file inventory
```

---

## 3. Components & responsibilities

### 3.1 `crates/common`

| Module | Responsibility |
|---|---|
| `error.rs` | `AppError` enum + `IntoResponse`; maps to error envelope `{ error: { code, message, details? } }`. |
| `config.rs` | `figment` loader; trait `ServiceConfig` per service; shared keys (DATABASE_URL, REDIS_URL, KAFKA_BROKERS, JWT_*, ARGON2_*). |
| `db.rs` | `pg_pool(url, max_conn) -> PgPool`. |
| `redis.rs` | `deadpool_redis::Pool` builder. |
| `kafka.rs` | `Producer` wrapper: `produce_json<T: Serialize>(topic, key, payload)`; logs on failure, never `unwrap`. Async `acks=all`, `enable.idempotence=true`. |
| `auth.rs` | JWT encode/decode (HS256, `jsonwebtoken`); `Claims { sub, role, exp, iat, jti }`; cookie builder. |
| `middleware/auth.rs` | Axum `from_fn` — extract `oec_access` cookie → verify → put `AuthUser { id, role }` in request extensions. `require_role(Role)` variant. |
| `middleware/rate_limit.rs` | Redis sliding window: `rate:{ip|user}:{minute}` INCR+EXPIRE. Applied **before** auth. |
| `middleware/trace.rs` | `TraceLayer` + JSON `tracing-subscriber`; request_id from header or generated. |
| `models.rs` | Shared types: `UserId(Uuid)`, `PostId(Uuid)`, `UserRole`, `PostStatus`, paging cursor. |
| `events.rs` | Payload structs for `content.created`, `user.followed`, envelope `{ event_id, event_type, event_version, occurred_at, producer, data }`. |
| `ids.rs` | `Uuid::now_v7()` wrapper for pre-mint cases (post id before insert for Kafka event). |
| `time.rs` | `now_utc()`, freshness decay helper (placeholder for Phase 2). |

### 3.2 `auth-service` (:8001)

Endpoints:
| Method | Path | Notes |
|---|---|---|
| POST | `/api/v1/auth/register` | body `{ username, email, password, display_name? }` → sets `oec_access` + `oec_refresh` cookies |
| POST | `/api/v1/auth/login` | body `{ email_or_username, password }` |
| POST | `/api/v1/auth/refresh` | reads `oec_refresh` cookie, rotates both cookies |
| DELETE | `/api/v1/auth/logout` | clears cookies + deletes refresh key |
| GET | `/api/v1/auth/me` | returns current `{ user }` for SvelteKit SSR |
| GET | `/health`, `/metrics` | liveness + Prometheus |

- DB: `users`. Password hashing: argon2id with configurable cost.
- Redis: `session:refresh:{sha256(token)}` → user_id, TTL 7d. Rotation deletes the old key (one-time use).
- Rate limit: 10/min/IP on `/register` and `/login`; 30/min/user on `/refresh`.
- No Kafka events in Phase 0+1.

### 3.3 `user-service` (:8002)

Endpoints:
| Method | Path | Auth |
|---|---|---|
| GET | `/api/v1/users/{id}` | optional |
| PUT | `/api/v1/users/{id}` | JWT, owner |
| POST | `/api/v1/users/{id}/follow` | JWT |
| DELETE | `/api/v1/users/{id}/follow` | JWT |
| GET | `/api/v1/users/{id}/followers` | optional, `?cursor=&limit=` |
| GET | `/api/v1/users/{id}/following` | optional, `?cursor=&limit=` |
| GET | `/api/v1/users?q=&limit=` | optional, ILIKE on `username` & `display_name` (pg_trgm GIN index) |

- DB: `users` (read + update editable fields), `follows`.
- Events: produce `user.followed` on successful POST `/follow`. Key = `followee_id`.
- Constraint: self-follow → 400 (also enforced by `CHECK (follower_id <> followee_id)`).
- Pagination: keyset on `(created_at DESC, follower_id)`.

### 3.4 `content-service` (:8003)

Endpoints:
| Method | Path | Auth |
|---|---|---|
| POST | `/api/v1/posts` | JWT (role `user` or `creator`) |
| GET | `/api/v1/posts/{id}` | optional |
| PUT | `/api/v1/posts/{id}` | JWT, owner |
| DELETE | `/api/v1/posts/{id}` | JWT, owner or `admin` |
| GET | `/api/v1/posts?author_id=&limit=&cursor=` | optional |
| POST | `/api/v1/posts/{id}/view` | optional, increments `view_count` (Phase-1 stub; Phase 2 moves to event) |

- Validation: `content` 1–4000 chars, `media_urls` ≤ 6 HTTPS URLs, `tags` ≤ 8.
- Status flow Phase 1: when env `AUTO_PUBLISH=true` (default), `POST /posts` inserts directly with `status='published'` and `safety_score=1.0` (no NLP worker yet). When `AUTO_PUBLISH=false` (Phase 3 onwards), inserts with `status='pending'` and Phase-3 workers promote it. The DB column default remains `'pending'` so the safer behaviour wins if the env is unset.
- Events: produce `content.created` after DB commit. Key = `post_id`. Pre-mint `post_id` via `Uuid::now_v7()` so the event payload matches the row.
- Media upload Phase 1: external URLs only. MinIO/S3 deferred.

### 3.5 Envoy gateway

`envoy.yaml` (static):
- Listener `:8080`.
- Route prefixes: `/api/v1/auth/` → cluster `auth`, `/api/v1/users/` → `user`, `/api/v1/posts/` → `content`.
- HTTP filters: `envoy.filters.http.local_ratelimit` (60/min unauthenticated; per-route override) → CORS filter → `envoy.filters.http.router`.
- Clusters: 3 `STRICT_DNS` clusters, internal service-name DNS, health check `/health` every 5s.
- JWT validation **not** done in Envoy — the service layer extracts the cookie and verifies it (chosen for simpler key rotation; the gateway only forwards cookies).

### 3.6 Frontend (SvelteKit, :3000)

| Svelte route | Source ref | Phase-1 backing |
|---|---|---|
| `/` (Feed) | `scripts/feed.jsx` | mock |
| `/login` | `scripts/auth.jsx` (Login pane) | auth-service |
| `/register` | `scripts/auth.jsx` (Register pane) | auth-service |
| `/profile/[id]` | `scripts/pages.jsx` profile | user-service + content-service (list posts) |
| `/post/new` | `scripts/pages.jsx` editor | content-service |
| `/post/[id]` | `scripts/pages.jsx` detail | content-service |
| `/admin` | `scripts/admin.jsx` | mock |
| `/m` (mobile shell) | `scripts/mobile.jsx` | mock |

`hooks.server.ts`:
- Forwards browser cookies on every proxied call to Envoy (`http://envoy:8080`).
- On a 401 from the access cookie, calls `/api/v1/auth/refresh` once; on success, retries the original request; on failure, clears cookies and redirects to `/login`.
- Adds `x-request-id` for correlation.

The browser only talks to SvelteKit (`localhost:3000`); SvelteKit proxies to Envoy inside the compose network. This keeps cookies same-origin in dev.

**Styling convention — Tailwind-first:**
- Default to inline Tailwind utility classes on markup. A new custom class earns its name only when the exact pattern repeats across 3+ components.
- Translate `styles/tokens.css` (colors, radii, shadows, spacing) into `tailwind.config.cjs` `theme.extend` so utilities are authoritative.
- The "liquid glass" surface (backdrop blur + translucent fill + soft border + inner highlight) genuinely repeats across Topbar, Sidebar, GlassCard, PostCard, Composer, MobileShell. Extract it as **either** a Tailwind `@layer components` class `.glass-surface` (via `@apply`) **or** a `GlassCard.svelte` wrapper — prefer the wrapper where structural slots are involved, prefer `@apply` for pure visual recipes applied to varied tags.
- Other named recipes worth pre-defining (each used 3+ times in the existing UI): `.glass-chip`, `.glass-pill`, `.glass-button-primary`, `.text-display-serif` (Lora italic), `.text-mono-meta` (JetBrains Mono).
- Do **not** wholesale port `styles/glass.css` into a single CSS file. Translate token values into Tailwind config + the handful of recipes above; everything else uses utilities directly.
- Per-component `<style>` blocks are reserved for keyframe animations and scoped one-off rules that Tailwind cannot express ergonomically.

---

## 4. Data model & migrations

Phase 0+1 ships migrations for **types, users, follows, posts** only. Tables `interactions`, `recommendations`, `reports`, `audit_logs`, `user_preference_vectors` belong to later phases and ship with their own migrations.

All PKs use `uuidv7()` (built into PostgreSQL 18). Time-ordered UUIDs keep the B-tree insert-friendly and make PK-based cursor pagination viable.

### 4.1 `20260525000001_init_enums.sql`

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TYPE user_role   AS ENUM ('user', 'creator', 'admin');
CREATE TYPE post_status AS ENUM ('pending', 'published', 'hidden', 'flagged');

CREATE FUNCTION set_updated_at() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END $$;
```

### 4.2 `20260525000002_users.sql`

```sql
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT uuidv7(),
    username      VARCHAR(50)  UNIQUE NOT NULL,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          user_role    NOT NULL DEFAULT 'user',
    display_name  VARCHAR(100),
    bio           TEXT,
    avatar_url    TEXT,
    topic_prefs   TEXT[]       NOT NULL DEFAULT '{}',
    is_active     BOOLEAN      NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- UNIQUE already indexes username/email — no redundant idx_users_username/email.
CREATE INDEX idx_users_search_trgm ON users
  USING GIN (username gin_trgm_ops, display_name gin_trgm_ops);

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

### 4.3 `20260525000003_follows.sql`

```sql
CREATE TABLE follows (
    follower_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    followee_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (follower_id, followee_id),
    CHECK (follower_id <> followee_id)
);

CREATE INDEX idx_follows_followee_created ON follows (followee_id, created_at DESC);
```

### 4.4 `20260525000004_posts.sql`

```sql
CREATE TABLE posts (
    id           UUID PRIMARY KEY DEFAULT uuidv7(),
    author_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content      TEXT    NOT NULL CHECK (length(content) BETWEEN 1 AND 4000),
    media_urls   TEXT[]  NOT NULL DEFAULT '{}',
    tags         TEXT[]  NOT NULL DEFAULT '{}',
    topics       TEXT[]  NOT NULL DEFAULT '{}',
    safety_score REAL    NOT NULL DEFAULT 1.0
                  CHECK (safety_score BETWEEN 0 AND 1),
    status       post_status NOT NULL DEFAULT 'pending',
    view_count   BIGINT  NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_posts_author_created   ON posts (author_id, created_at DESC);
CREATE INDEX idx_posts_published_created ON posts (created_at DESC) WHERE status = 'published';
CREATE INDEX idx_posts_topics_gin        ON posts USING GIN (topics);

CREATE TRIGGER trg_posts_updated_at BEFORE UPDATE ON posts
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

### 4.5 UUIDv7 implications on indexing

- PK is time-ordered, so PK-only cursor pagination (`WHERE id < :cursor ORDER BY id DESC`) is valid for tables where business semantics match insertion order.
- Composite `(created_at DESC, id)` indexes suggested in the old CLAUDE.md schema are dropped — the PK already provides that ordering.
- `(created_at DESC)` indexes remain where the query has a `WHERE` clause that does not include the PK (e.g. `WHERE status = 'published'`).

### 4.6 Kafka topics created upfront

A one-shot `init-topics` container runs `kafka-topics.sh --create --if-not-exists`:
- `oecophylla.content.created` — 1 partition, 1 replica (dev).
- `oecophylla.user.followed` — 1 partition, 1 replica.

Phase 2 will add `oecophylla.interactions` with higher partition count.

### 4.7 Seed Phase 1

`scripts/seed_phase1.py`:
- 50 users (3 admin, 7 creator, 40 user), shared dev password `Password!123` with a pre-computed argon2id hash baked in so the script stays fast.
- 100 posts (2/user), `status='published'`, 10 mock topics.
- 200 random follow edges, no self-loops.

---

## 5. Events, Redis keys, error envelope, security, observability

### 5.1 Kafka event envelope

```json
{
  "event_id": "<uuidv7>",
  "event_type": "content.created",
  "event_version": 1,
  "occurred_at": "2026-05-25T12:34:56.789Z",
  "producer": "content-service",
  "data": { ... }
}
```

- `content.created.data`: `{ post_id, author_id, content, tags, created_at }`; Kafka key = `post_id`.
- `user.followed.data`: `{ follower_id, followee_id, followed_at }`; Kafka key = `followee_id`.

Producer guarantees: `acks=all`, `enable.idempotence=true`, async send with callback. If Kafka is unreachable, log `tracing::error!` with `event_id` — never block the HTTP request. (DB is the source of truth; Phase 2 introduces an outbox if exactly-once becomes required.)

### 5.2 Redis keys (Phase 0+1 only)

| Key | Type | TTL | Service | Purpose |
|---|---|---|---|---|
| `rate:ip:{ip}:{minute}` | counter | 60s | all | IP-level rate limit |
| `rate:user:{user_id}:{minute}` | counter | 60s | all | per-user rate limit |
| `session:refresh:{sha256(token)}` | string (user_id) | 604800s | auth | refresh token whitelist |
| `user:meta:{user_id}` | hash | 300s | user | profile cache (display_name, avatar) — invalidated on PUT profile |

### 5.3 Error envelope

```json
{ "error": { "code": "VALIDATION_FAILED", "message": "username must be 3-30 chars", "details": { "field": "username" } } }
```

| `AppError` variant | HTTP | `code` |
|---|---|---|
| `Validation` | 400 | `VALIDATION_FAILED` |
| `Unauthorized` | 401 | `UNAUTHORIZED` |
| `Forbidden` | 403 | `FORBIDDEN` |
| `NotFound` | 404 | `NOT_FOUND` |
| `Conflict` | 409 | `CONFLICT` |
| `RateLimited` | 429 | `RATE_LIMITED` (with `Retry-After`) |
| `Internal` | 500 | `INTERNAL_ERROR` (no internal detail leaked) |

`tracing` logs every 5xx with `error.cause`; 4xx at debug level.

### 5.4 Security

- **argon2id** params: `m=19_456 KiB, t=2, p=1` (overridable via env so CI can lower for speed).
- **JWT access** HS256, 15-min TTL, claims `{ sub, role, exp, iat, jti }`.
- **Refresh** = opaque random 32 bytes, sha256 stored as Redis key. One-time use: rotated on `/refresh`, the old key deleted.
- **Cookies:** `oec_access` (`Path=/`, HttpOnly, Secure in prod, SameSite=Lax, 15 min); `oec_refresh` (`Path=/api/v1/auth`, HttpOnly, Secure, SameSite=Strict, 7 days).
- **CORS** at Envoy: dev allows `http://localhost:3000`, prod via env. `credentials=true`.
- **CSRF mitigation:** Lax cookies + a required header `x-requested-with: oec-web` enforced by Envoy on every non-`/auth/login`+`/auth/register` mutating request. Same-origin SvelteKit → Envoy → service chain means the realistic CSRF surface is small in Phase 1.
- `tracing` filters drop fields named `password`, `password_hash`, `token`.

### 5.5 Rate limits

| Endpoint | Limit |
|---|---|
| `POST /auth/register`, `POST /auth/login` | 10/min/IP |
| `POST /auth/refresh` | 30/min/user |
| `POST /posts` | 30/min/user |
| `POST /users/{id}/follow`, `DELETE` | 60/min/user |
| any other authenticated | 200/min/user |
| any other unauthenticated | 60/min/IP |

Two layers: Envoy `local_ratelimit` (per-route, per-IP, coarse) → service Redis sliding window (per-user, precise, applied after JWT extract). `429` returns `Retry-After`.

### 5.6 Observability

- Each Rust service exposes `/metrics` (`metrics-exporter-prometheus`).
- Prometheus scrapes every 15s: 3 services + Envoy admin (`:9901`).
- Grafana provisioned datasource + one starter dashboard `Oecophylla Overview` (HTTP RPS, p95 latency, error rate).
- Logs: structured JSON to stdout, collected via `docker compose logs`. OpenTelemetry collector deferred to Phase 4.

---

## 6. Testing strategy & Definition of Done

### 6.1 Test matrix (smoke-level)

| Layer | Scope | Tooling |
|---|---|---|
| `cargo check`, `cargo clippy -- -D warnings` | every crate | CI gate |
| `sqlx prepare` cache | per service | enables offline Docker builds |
| Smoke HTTP tests | `tests/smoke.rs` per service | `reqwest` against locally-running service |
| Frontend unit | `lib/api.ts`, `stores/auth.ts` | `vitest` |
| Frontend e2e | — | **deferred to Phase 4** |

Smoke tests use a per-run schema (`oec_test_<rand>`) so they do not collide with dev data. They assume `postgres`, `redis`, `kafka` are running locally (via `compose.dev.yaml`). No `testcontainers` — chosen for faster iteration.

### 6.2 Smoke test cases

**auth-service**: register happy path, duplicate email → 409, wrong password → 401 (no leak), refresh rotation invalidates old token, logout → subsequent refresh → 401.

**user-service**: public `GET /users/{id}`, non-owner `PUT` → 403, self-follow → 400, successful follow produces `user.followed` event consumable within 2s.

**content-service**: post happy path produces `content.created` event, empty content → 400, non-owner non-admin delete → 403, `GET /posts?author_id=` paginates `created_at DESC`.

**Frontend (vitest)**: `api.fetch` adds credentials + request-id; 401 triggers auto-refresh + retry; `register` flow populates the auth store.

### 6.3 Manual verify checklist per milestone

1. `docker compose up -d` cold start to healthy in ≤ 90s.
2. `http://localhost:3000/` renders the Apple Glass shell.
3. Register → auto-login → header shows display name.
4. Create a post → reload → it appears on the author's profile.
5. Follow another user → it appears in `following`.
6. `docker compose logs <service> | grep ERROR` is empty.
7. `docker compose exec kafka kafka-console-consumer.sh --bootstrap-server kafka:9092 --topic oecophylla.content.created --from-beginning --max-messages 1` returns the most recent event.

### 6.4 Definition of Done — Phase 0+1

Phase is complete when **all** of the following hold:
1. `docker compose up` from empty to healthy ≤ 90s, no manual intervention.
2. Migration job is idempotent (second run is a no-op).
3. `make test` passes (workspace `cargo test` + frontend `vitest run`).
4. Frontend `pnpm build` succeeds and `pnpm start` serves the app.
5. Pages backed by Phase-1 services work end-to-end against the real backend: `/login`, `/register`, `/post/new`, `/profile/[id]`, `/post/[id]`. Other pages (`/`, `/admin`, `/m`) render with mock data and do not 500.
6. Every endpoint returns the standard error envelope on bad input.
7. `cargo clippy -D warnings` clean, `cargo fmt --check` clean, `pnpm lint` clean.
8. Root `README.md` covers env vars, `docker compose up`, smoke test command, service URLs.
9. `scripts/seed_phase1.py` populates 50 users / 100 posts / 200 follows; the UI displays them.
10. Kafka topics `oecophylla.content.created` and `oecophylla.user.followed` exist and receive events from real user actions.

---

## 7. Folder/file inventory (end of Phase 0+1)

```
oecophylla/
├── README.md
├── .env.example
├── compose.yaml
├── compose.dev.yaml
├── Makefile
├── envoy/envoy.yaml
├── migrations/
│   ├── 20260525000001_init_enums.sql
│   ├── 20260525000002_users.sql
│   ├── 20260525000003_follows.sql
│   └── 20260525000004_posts.sql
├── backend/
│   ├── Cargo.toml                # [workspace]
│   ├── rust-toolchain.toml
│   ├── .sqlx/
│   ├── crates/common/{Cargo.toml, src/{lib,error,config,db,redis,kafka,auth,ids,time,events,models}.rs, src/middleware/{auth,rate_limit,trace}.rs}
│   └── services/{auth-service, user-service, content-service}/{Cargo.toml, Dockerfile (rust:1.83-trixie → debian:trixie-slim), src/{main,routes/,handlers/,services/,repositories/,models}.rs, tests/smoke.rs}
├── frontend/
│   ├── package.json
│   ├── svelte.config.js (adapter-node)
│   ├── vite.config.ts
│   ├── tailwind.config.cjs
│   ├── tsconfig.json
│   ├── Dockerfile                # node:22-trixie-slim build + runtime
│   ├── static/
│   └── src/{app.html, app.css, hooks.server.ts, lib/{api.ts, stores/, types.ts, components/, mock/}, routes/{+layout.svelte, +layout.server.ts, +page.svelte, login/, register/, logout/+server.ts, profile/[id]/, post/new/, post/[id]/, admin/, m/}}
├── infra/
│   ├── prometheus/prometheus.yml
│   ├── grafana/{provisioning/{datasources, dashboards}, dashboards/oecophylla-overview.json}
│   └── kafka/init-topics.sh
├── scripts/
│   ├── seed_phase1.py
│   ├── requirements.txt
│   └── Dockerfile                # python:3.13-trixie + uv
└── docs/superpowers/{specs/, plans/}
```

Existing files in the repo (`scripts/*.jsx`, `styles/*.css`, `tw/*`, `Oecophylla *.html`, `tweaks-panel.jsx`) stay at the root for reference during the SvelteKit port. After Phase 1 closes they move to `docs/legacy-ui/` (or are deleted).

### 7.1 Root `Makefile`

```make
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
	docker compose run --rm scripts python scripts/seed_phase1.py

clean:
	docker compose down -v
```

### 7.2 CI skeleton (`.github/workflows/ci.yml` — template only; not enabled in Phase 0+1)

```yaml
on: { push: { branches: [main] }, pull_request: {} }
jobs:
  backend:
    runs-on: ubuntu-24.04
    services:
      postgres: { image: postgres:18-trixie, env: { POSTGRES_PASSWORD: secret }, ports: ['5432:5432'] }
      redis:    { image: redis:7-trixie, ports: ['6379:6379'] }
      kafka:    { image: apache/kafka:4.0.0, ports: ['9092:9092'] }
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - run: cd backend && cargo fmt --check
      - run: cd backend && cargo clippy --workspace -- -D warnings
      - run: cd backend && cargo sqlx migrate run --source ../migrations
      - run: cd backend && cargo test --workspace
  frontend:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - run: cd frontend && pnpm install --frozen-lockfile
      - run: cd frontend && pnpm lint && pnpm vitest run && pnpm build
```

### 7.3 `.env.example`

```env
# DB
DATABASE_URL=postgres://oecophylla:secret@postgres:5432/oecophylla
POSTGRES_DB=oecophylla
POSTGRES_USER=oecophylla
POSTGRES_PASSWORD=secret

# Redis
REDIS_URL=redis://:redissecret@redis:6379
REDIS_PASSWORD=redissecret

# Kafka (KRaft single-node)
KAFKA_BROKERS=kafka:9092
KAFKA_CLUSTER_ID=MkU3OEVBNTcwNTJENDM2Qw

# Auth
JWT_SECRET=please-change-this-32-or-more-chars
JWT_ACCESS_TTL_SECONDS=900
JWT_REFRESH_TTL_SECONDS=604800
ARGON2_M_COST=19456
ARGON2_T_COST=2
ARGON2_P_COST=1

# Service internal URLs
AUTH_SERVICE_URL=http://auth-service:8001
USER_SERVICE_URL=http://user-service:8002
CONTENT_SERVICE_URL=http://content-service:8003
ENVOY_URL=http://envoy:8080

# Frontend
PUBLIC_API_BASE=/api/v1
ORIGIN=http://localhost:3000

# Rate limits
RATE_LIMIT_PUBLIC=60
RATE_LIMIT_AUTHED=200

# Grafana
GF_SECURITY_ADMIN_PASSWORD=admin
```

---

## 8. Risks & open questions

| Risk | Mitigation |
|---|---|
| Kafka KRaft container slow to start cold → compose healthcheck flakes. | Generous `start_period` (30s) on Kafka healthcheck; producers retry connect for 30s on boot. |
| UUIDv7 requires PG 18; older client tools may show different sort behaviour. | Pin `postgres:18-alpine`, document explicitly in README. |
| sqlx compile-time query verification fails in Docker if `.sqlx/` cache is stale. | `make sqlx-prepare` documented; CI runs `sqlx migrate run` before `cargo test`. |
| Port of Apple Glass UI to Svelte loses pixel parity. | Reference `.html` + `.css` files preserved at root; component-by-component port; visual diff during manual verify. |
| Cookie-based auth + SvelteKit SSR cookie forwarding has edge cases when the user logs in via a server action that 303-redirects. | Server action sets cookie via `cookies.set()` then `throw redirect(303, ...)`; covered in `login/+page.server.ts` smoke. |

Open: do we want a `MailHog`-equivalent container for future email flows (password reset)? Deferred — Phase 0+1 has no email.

---

## 9. Out-of-scope (will appear in later phase specs)

- Phase 2: `interaction-service`, `feed-service`, `recommendation-api` (Python FastAPI), `cache-invalidator`, `feature-store-worker`, full `interactions` + `recommendations` + `user_preference_vectors` tables, Redis feed cache, ranking formula, fallback trending feed.
- Phase 3: `moderation-service` + worker, `nlp-worker`, `notification-service`, `reports` + `audit_logs` tables, admin queue UI wired live.
- Phase 4: `analytics-service`, full seed (500/2000/50k/200/50), `scripts/evaluate.py` (Precision@K, Recall@K, CTR, diversity), OpenTelemetry collector, production deployment notes.

---

## 10. Decisions log

1. **Cargo workspace + shared crate.** Reduces boilerplate without merging the services into one binary.
2. **Shared Postgres database + shared `migrations/`.** Matches the original CLAUDE.md intent and keeps Phase-1 simple. Each service still owns its own pool.
3. **Kafka in Phase 0+1 (not deferred).** Producers wired now so Phase-2 consumers join a live stream rather than retro-fitting events.
4. **HttpOnly cookies for auth.** Stronger than `localStorage` against XSS; access in `oec_access`, refresh in `oec_refresh` (scoped to `/api/v1/auth`).
5. **SvelteKit `adapter-node` + SSR.** Server hooks proxy the API and handle cookie refresh in one place.
6. **Port the entire Apple Glass UI in Phase 1.** Pages without Phase-1 backends render against mock data.
7. **Smoke-level testing only.** TDD-style integration testing deferred to Phase 2+ where the logic is non-trivial.
8. **Envoy gateway, JWT verified in services.** Gateway handles routing, CORS, IP rate limit; services own auth so JWT secret rotation does not require Envoy reload.
9. **PostgreSQL 18 + `uuidv7()` for all primary keys.** Time-ordered UUIDs keep B-trees insert-friendly; no `pgcrypto` extension required.
10. **Kafka in KRaft mode, no Zookeeper.** `apache/kafka:4.0.0` image, single-node, controller + broker in the same process. Verified via Apache Kafka docs (context7, 2026-05-25).
11. **Tailwind-first styling.** Inline utilities by default; named classes only for genuinely repeated visual patterns (liquid glass surface, chips, pills, primary glass button, display serif, mono meta). Tokens migrate to `tailwind.config.cjs` rather than a hand-written CSS file.
12. **Debian Trixie base images.** Every long-running container is built `FROM debian:trixie-slim` (or a Debian-Trixie-based upstream image). Avoid Alpine/musl variants. One-shot init/deploy jobs (`migrate`, `init-topics`, `seed`, CI runners) may use stock upstream images for simplicity. Concrete pins: Rust runtime `debian:trixie-slim`, Rust builder `rust:1.83-trixie`, frontend runtime `node:22-trixie-slim`, Python seed `python:3.13-trixie` (or `:3.11-slim-trixie`), Postgres `postgres:18-trixie`, Redis `redis:7-trixie` (fall back to `redis:7-bookworm` if Trixie tag not yet published), Envoy `envoyproxy/envoy:v1.32-debian`, Kafka `apache/kafka:4.0.0` (Eclipse Temurin, already Debian-based).
