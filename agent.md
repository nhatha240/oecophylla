[claude.md](claude.md)# Oecophylla — Social Network with News Recommendation

## Project Overview

Oecophylla is a social networking platform with intelligent news feed recommendation and multi-layer content moderation. Architecture is microservices-first, event-driven via Kafka, with a separate Python AI module for ranking.

**Core design principles:**
- Every user action → structured Kafka event (never fire-and-forget writes)
- Feed ranking is async; API latency must never block on ML inference
- Fallback always exists: if recommendation service is down, return trending feed from Redis
- All sensitive admin actions are audit-logged with actor + timestamp + reason
- No silent failures — every error must be logged with structured context

---

## ⚡ Current State (2026-05-26, post-2B ship)

> The rest of this document is the original product spec. The sections below describe what is actually shipped today vs. what is still planned. **Read this section before doing any work** — it overrides spec details that have drifted.

### Phases shipped

| Phase | Status | Git tag | Spec | Plan |
|---|---|---|---|---|
| Phase 0+1 (infra + auth/user/content + frontend) | ✅ Complete | `phase-0-1-complete` | `docs/superpowers/specs/2026-05-25-foundation-identity-content-design.md` | `docs/superpowers/plans/2026-05-25-foundation-identity-content-plan.md` |
| Phase 2A (interactions + comments + reports) | ✅ Complete | `phase-2a-complete` | `docs/superpowers/specs/2026-05-25-phase-2a-interactions-design.md` | `docs/superpowers/plans/2026-05-25-phase-2a-interactions-plan.md` |
| Phase 2B (feed + recommendation + workers) | ✅ Complete | `phase-2b-complete` | `docs/superpowers/specs/2026-05-26-phase-2b-feed-recommendation-design.md` | `docs/superpowers/plans/2026-05-26-phase-2b-feed-recommendation-plan.md` |
| Phase 3 (moderation + notifications + NLP) | 📝 Spec+plan in progress | — | `docs/superpowers/specs/2026-05-26-phase-3-moderation-notifications-nlp-design.md` | `docs/superpowers/plans/2026-05-26-phase-3-moderation-notifications-nlp-plan.md` |
| Phase 4 (analytics + evaluation + observability) | ⏳ Not started | — | — | — |

### What is actually in the repo today (running)

- **Backend** — Cargo workspace `backend/` with `crates/common` + 6 binaries: `auth-service` (:8001), `user-service` (:8002), `content-service` (:8003), `interaction-service` (:8004), `feed-service` (:8005), `cache-invalidator` (Kafka consumer, no HTTP).
- **Python services** outside the workspace: `recommendation-api` (FastAPI :8090) and `workers/feature_store_worker` (Kafka consumer).
- **Frontend** — SvelteKit (adapter-node, Tailwind) at `frontend/`. Routes shipped: `/`, `/login`, `/register`, `/logout`, `/profile/[id]`, `/post/new`, `/post/[id]`, `/admin` (mock), `/m` (mock). Live feed root pages via cursor + IntersectionObserver view tracker.
- **Infra** — `compose.yaml` with `postgres:18-trixie`, `redis:8-trixie`, `apache/kafka:4.0.0` (KRaft, no Zookeeper), `envoyproxy/envoy:v1.32-latest`, `prom/prometheus:v3.0.0`, `grafana/grafana:11.4.0`, plus the 6 Rust services + 2 Python services + frontend + 2 one-shot jobs (`migrate`, `init-topics`). `compose.dev.yaml` exposes backend ports.
- **Migrations** — 9 sqlx migrations applied: enums, users, follows, posts, posts_counters, interactions, comments, reports, user_preference_vectors.
- **Kafka topics** — `oecophylla.content.created`, `oecophylla.user.followed`, `oecophylla.interactions`. Consumers wired: `feature-store-worker` (updates `user_preference_vectors`) and `cache-invalidator` (clears `feed:{user_id}` on interaction).

### Locked technical decisions (must respect in any future work)

These decisions are encoded in `/Users/nhathaminh/.claude/projects/-Users-nhathaminh-oecophylla/memory/` — auto-load each session. Summary:

| Decision | Detail |
|---|---|
| API gateway | **Envoy v1.32**, not Nginx (CLAUDE.md mentions Nginx — outdated) |
| Postgres | **18** with built-in `uuidv7()` for every PK (NOT `gen_random_uuid()`). Volume mount at `/var/lib/postgresql` (parent), NOT legacy `/data` subpath |
| Kafka | **KRaft mode** single-node `apache/kafka:4.0.0` — no Zookeeper container |
| Redis | `redis:8-trixie` (no Trixie variant of Redis 7 exists on Docker Hub) |
| Base images | `debian:trixie-slim` for all long-running containers; one-shot jobs may use stock |
| Rust toolchain | **1.85.0** (NOT 1.83) — required for `edition=2024` manifests in 2026 dep ecosystem |
| Rust Docker builder | `rust:1.85` (Debian bookworm-based, no `1.85-trixie` tag exists) → runtime `debian:trixie-slim`. Builder needs `apt-get install cmake pkg-config libssl-dev ca-certificates` for rdkafka |
| `jsonwebtoken` | `default-features = false` — only HS256, avoids pulling time/simple_asn1 chain requiring Rust 1.88 |
| Frontend styling | **Tailwind-first** — inline utilities; extract a named class only when pattern repeats across 3+ components (e.g. `.glass-surface`, `.glass-chip`, `.glass-pill`, `.glass-button-primary`, `.text-display-serif`, `.text-mono-meta`) |
| Smoke test username | Use UUIDv7 **random suffix `&u[22..]`**, NOT timestamp prefix `&u[..10]` (prefix collides in fast loops) |
| Kafka from host | macOS host cannot resolve `kafka:9092` — run smoke tests inside compose network OR use `docker compose exec kafka kafka-console-consumer.sh ...` |
| Auth cookies | `oec_access` (Path=/, 15m, SameSite=Lax) + `oec_refresh` (Path=/api/v1/auth, 7d, SameSite=Strict). HttpOnly always. argon2id password hashing |
| Workflow | Independent tasks dispatched in parallel via single message with multiple `Agent` tool calls. "Let run" / "ngủ" mode = skip approval gates, dispatch end-to-end |

### Known follow-ups (still open)

- **Counter drift recompute job** — periodic SQL `UPDATE posts SET like_count = (SELECT count(*) ...)` to heal drift from out-of-band deletes.
- **Toast component** replacing `alert()` rollbacks in `PostActionBar`.
- **ESLint config** for frontend so `pnpm lint` passes (currently no `eslint.config.js`).
- **Pre-bake `sqlx-cli`** in a custom migrate image (currently first boot installs from source ~6-8 min).
- **Host-accessible Kafka listener** (second listener on `:29092` advertised as `localhost:29092`) so smoke tests can run from host without compose network.
- **Tag push for earlier phases** — `phase-0-1-complete` and `phase-2a-complete` exist locally but were never pushed to origin.

### Phase 2B closeout notes

- `feature-store-worker` requires `cramjam>=2.8` (not the pip `lz4` package) so aiokafka 0.12 can decode the LZ4-compressed batches Kafka 4.0 produces. Without it, the worker dies on first fetch and `user_preference_vectors` silently stays empty.
- Python service tests require `pythonpath = .` in `pytest.ini` because tests import the package as `from app.X import Y`. Without that line `make test-python` fails with `ModuleNotFoundError`.
- After bringing the stack up with `docker compose up -d --build`, restart envoy (`docker compose restart envoy`) if envoy was already running before new clusters were added — compose does not detect bind-mount config changes.

### How to start a new session efficiently

1. Memory files at `/Users/nhathaminh/.claude/projects/-Users-nhathaminh-oecophylla/memory/` auto-load — locked decisions arrive for free.
2. This `CLAUDE.md` auto-loads — current state arrives for free.
3. To work on Phase 3: read its spec + plan in `docs/superpowers/{specs,plans}/2026-05-26-phase-3-*`.
4. To work on a specific bug or small change: skim the relevant spec section + `docs/superpowers/plans/` for the most recent plan touching that area.
5. **Do not** re-decide locked items from memory. Override only with explicit user instruction.

---

## Monorepo Structure

```
oecophylla/
├── services/
│   ├── api-gateway/          # Nginx config + optional Rust proxy
│   ├── auth-service/         # Rust — JWT, register, login, refresh
│   ├── user-service/         # Rust — profiles, follow/unfollow
│   ├── content-service/      # Rust — posts CRUD, media upload, topics
│   ├── interaction-service/  # Rust — like, comment, share, save, hide, report
│   ├── feed-service/         # Rust — aggregates feed, Redis cache, calls recommender
│   ├── moderation-service/   # Rust — rule-based checks, report queue, audit log
│   ├── notification-service/ # Rust — in-app notifications
│   ├── recommendation-api/   # Python FastAPI — ranking, feature store, evaluate
│   └── analytics-service/   # Python — dashboard metrics, Prometheus export
├── workers/
│   ├── feature-store-worker/ # Python — consumes interactions, updates preference vectors
│   ├── nlp-worker/          # Python — topic tagging, safety_score on content.created
│   ├── moderation-worker/   # Rust/Python — rule-based scan on content.created
│   └── cache-invalidator/   # Rust — invalidates Redis feed cache on interactions
├── frontend/                # SvelteKit + TypeScript + TailwindCSS
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   ├── nginx/
│   ├── prometheus/
│   └── grafana/
├── migrations/              # sqlx migrations (shared schema)
└── scripts/
    ├── seed.py              # Generate mock data: 500 users, 2000 posts, 50k interactions
    └── evaluate.py          # Offline Precision@K, Recall@K, diversity evaluation
```

---

## Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| Frontend | SvelteKit, TypeScript, TailwindCSS | SSR/CSR flexible, small bundle |
| Backend services | Rust, Axum, SQLx, Tokio | Memory-safe, zero-cost async, high throughput |
| AI / Recommender | Python 3.11, FastAPI, Pydantic v2 | Rich ML ecosystem, fast iteration |
| Workers | Python (ML workers), Rust (infra workers) | Match workload type |
| Database | PostgreSQL 15 | Relational integrity, JSONB for metadata |
| Cache | Redis 7 | Feed cache, sessions, rate limit, sorted sets |
| Messaging | Apache Kafka 3 | Replay, partitioned parallelism, consumer groups |
| Container | Docker, Docker Compose | Local reproducibility |
| Observability | Prometheus, Grafana, OpenTelemetry | Metrics + tracing |

---

## Service Ports (Docker Compose)

| Service | Internal Port | Notes |
|---|---|---|
| frontend | 3000 | SvelteKit dev server |
| api-gateway (Nginx) | 8080 | Single entry point for all clients |
| auth-service | 8001 | |
| user-service | 8002 | |
| content-service | 8003 | |
| interaction-service | 8004 | |
| feed-service | 8005 | Calls recommendation-api internally |
| moderation-service | 8006 | |
| notification-service | 8007 | |
| recommendation-api | 8090 | FastAPI, internal only |
| analytics-service | 8091 | FastAPI, admin only |
| postgres | 5432 | |
| redis | 6379 | |
| kafka | 9092 | |
| zookeeper | 2181 | Kafka dependency |
| prometheus | 9090 | |
| grafana | 3001 | |

---

## Environment Variables (.env template)

```env
# Database
DATABASE_URL=postgres://oecophylla:secret@postgres:5432/oecophylla
POSTGRES_DB=oecophylla
POSTGRES_USER=oecophylla
POSTGRES_PASSWORD=secret

# Redis
REDIS_URL=redis://:redissecret@redis:6379
REDIS_PASSWORD=redissecret

# Kafka
KAFKA_BROKERS=kafka:9092

# Auth
JWT_SECRET=change-me-in-production-min-32-chars
JWT_ACCESS_TTL_SECONDS=900        # 15 minutes
JWT_REFRESH_TTL_SECONDS=604800    # 7 days

# Services
PUBLIC_API_URL=http://localhost:8080
RECOMMENDATION_SERVICE_URL=http://recommendation-api:8090
ANALYTICS_SERVICE_URL=http://analytics-service:8091

# Rate limiting
RATE_LIMIT_PUBLIC=60              # req/min unauthenticated
RATE_LIMIT_AUTHED=200             # req/min authenticated

# Recommendation
FEED_CACHE_TTL_SECONDS=600        # 10 minutes
USER_VECTOR_CACHE_TTL_SECONDS=1800 # 30 minutes
FEED_CANDIDATE_POOL_SIZE=300
FEED_RESULT_SIZE=50
DIVERSITY_WEIGHT=0.3

# Grafana
GF_SECURITY_ADMIN_PASSWORD=admin
```

---

## Database Schema (PostgreSQL + sqlx migrations)

### users
```sql
CREATE TYPE user_role AS ENUM ('user', 'creator', 'admin');

CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username      VARCHAR(50)  UNIQUE NOT NULL,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          user_role    NOT NULL DEFAULT 'user',
    display_name  VARCHAR(100),
    bio           TEXT,
    avatar_url    TEXT,
    topic_prefs   TEXT[]       DEFAULT '{}',  -- user-declared interests
    is_active     BOOLEAN      NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email    ON users(email);
CREATE INDEX idx_users_username ON users(username);
```

### follows
```sql
CREATE TABLE follows (
    follower_id  UUID REFERENCES users(id) ON DELETE CASCADE,
    followee_id  UUID REFERENCES users(id) ON DELETE CASCADE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (follower_id, followee_id)
);

CREATE INDEX idx_follows_followee ON follows(followee_id);
```

### posts
```sql
CREATE TYPE post_status AS ENUM ('pending', 'published', 'hidden', 'flagged');

CREATE TABLE posts (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    author_id    UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    content      TEXT    NOT NULL,
    media_urls   TEXT[]  DEFAULT '{}',
    tags         TEXT[]  DEFAULT '{}',
    topics       TEXT[]  DEFAULT '{}',  -- set by NLP worker
    safety_score FLOAT   NOT NULL DEFAULT 1.0,  -- [0,1], set by NLP worker
    status       post_status NOT NULL DEFAULT 'pending',
    view_count   BIGINT  NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Feed queries: posts by followed users sorted by time
CREATE INDEX idx_posts_author_created  ON posts(author_id, created_at DESC);
-- Feed queries: only published posts
CREATE INDEX idx_posts_status_created  ON posts(status, created_at DESC) WHERE status = 'published';
-- Topic-based retrieval
CREATE INDEX idx_posts_topics          ON posts USING GIN(topics);
```

### interactions
```sql
CREATE TYPE interaction_type AS ENUM ('view', 'like', 'comment', 'share', 'save', 'hide', 'report');

CREATE TABLE interactions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    post_id      UUID REFERENCES posts(id) ON DELETE CASCADE NOT NULL,
    type         interaction_type NOT NULL,
    weight       FLOAT NOT NULL,   -- normalized signal weight per Bảng 2.2
    metadata     JSONB,            -- e.g. {"dwell_ms": 12400} for view, {"text": "..."} for comment
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, post_id, type)  -- one interaction per type per user per post
);

CREATE INDEX idx_interactions_user_post ON interactions(user_id, post_id);
CREATE INDEX idx_interactions_post      ON interactions(post_id);
CREATE INDEX idx_interactions_user_time ON interactions(user_id, created_at DESC);
```

### recommendations (impression log)
```sql
CREATE TABLE recommendations (
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    post_id    UUID REFERENCES posts(id) ON DELETE CASCADE,
    score      FLOAT    NOT NULL,
    source     VARCHAR(50) NOT NULL,  -- 'follow' | 'topic' | 'trending' | 'similarity' | 'fallback'
    served_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    clicked_at TIMESTAMPTZ,           -- set on first view interaction after serving
    PRIMARY KEY (user_id, post_id, served_at)
);

CREATE INDEX idx_recs_user_served ON recommendations(user_id, served_at DESC);
```

### reports
```sql
CREATE TYPE report_status AS ENUM ('pending', 'resolved_hidden', 'resolved_ok', 'resolved_warned');

CREATE TABLE reports (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reporter_id UUID REFERENCES users(id) ON DELETE SET NULL,
    post_id     UUID REFERENCES posts(id) ON DELETE CASCADE NOT NULL,
    reason      VARCHAR(100) NOT NULL,
    detail      TEXT,
    status      report_status NOT NULL DEFAULT 'pending',
    resolved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    resolved_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reports_post   ON reports(post_id);
CREATE INDEX idx_reports_status ON reports(status) WHERE status = 'pending';
```

### audit_logs
```sql
CREATE TABLE audit_logs (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id   UUID REFERENCES users(id) ON DELETE SET NULL,
    action     VARCHAR(100) NOT NULL,  -- e.g. 'POST_HIDDEN', 'USER_BANNED', 'RULE_UPDATED'
    target_id  UUID,                   -- generic target (post_id, user_id, etc.)
    target_type VARCHAR(50),
    reason     TEXT,
    metadata   JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_actor  ON audit_logs(actor_id);
CREATE INDEX idx_audit_target ON audit_logs(target_id);
```

### user_preference_vectors (feature store — hot copy in Redis, cold in PG)
```sql
CREATE TABLE user_preference_vectors (
    user_id      UUID REFERENCES users(id) ON DELETE CASCADE PRIMARY KEY,
    topic_weights JSONB NOT NULL DEFAULT '{}',  -- {"tech": 0.45, "sports": 0.12, ...}
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## Kafka Topics

| Topic | Producer | Consumers | Payload fields |
|---|---|---|---|
| `content.created` | content-service | moderation-worker, nlp-worker | `post_id, author_id, content, tags, created_at` |
| `content.published` | content-service (after moderation) | feed-service worker, notification-service | `post_id, author_id, topics, safety_score` |
| `content.flagged` | moderation-worker | moderation-service (queue), audit-logger | `post_id, reason, severity, flagged_at` |
| `interactions` | interaction-service | feature-store-worker, cache-invalidator | `user_id, post_id, type, weight, metadata, timestamp` |
| `user.followed` | user-service | feed-service worker, notification-service | `follower_id, followee_id, timestamp` |
| `notifications.send` | multiple producers | notification-service | `user_id, type, payload` |

**Rules:**
- All events are JSON, schema documented per topic
- Producers must not block on Kafka send — use fire-and-confirm with async ack
- Consumer group IDs follow pattern: `oecophylla.<service-name>.<purpose>`
- Retention: 7 days for all topics

---

## Redis Key Patterns

| Key pattern | Type | TTL | Description |
|---|---|---|---|
| `feed:{user_id}` | List | 600s | Ordered list of post_ids for user's feed |
| `trending:24h` | Sorted Set | 300s | Posts scored by interaction weight in last 24h |
| `session:refresh:{token_hash}` | String | 604800s | Refresh token validity |
| `rate:{ip}:{minute}` | Counter | 60s | Sliding window rate limiter |
| `rate:{user_id}:{minute}` | Counter | 60s | Per-user rate limiter |
| `pref:{user_id}` | Hash | 1800s | User topic preference vector |
| `post:meta:{post_id}` | Hash | 300s | Post metadata cache (title, author, topics) |

---

## API Endpoints (all under `/api/v1/`)

### Auth
```
POST   /auth/register          → { access_token, refresh_token, user }
POST   /auth/login             → { access_token, refresh_token, user }
POST   /auth/refresh           → { access_token }
DELETE /auth/logout            → 204  (invalidates refresh token)
```

### Users
```
GET    /users/{id}             → UserProfile
PUT    /users/{id}             → UserProfile          [JWT: owner]
POST   /users/{id}/follow      → 201                  [JWT]
DELETE /users/{id}/follow      → 204                  [JWT]
GET    /users/{id}/followers   → Page<UserProfile>
GET    /users/{id}/following   → Page<UserProfile>
```

### Posts + Feed
```
GET    /feed                   → Page<PostWithScore>   [JWT]  ?cursor=&limit=20
POST   /posts                  → Post                  [JWT: creator]
GET    /posts/{id}             → Post                  [JWT/Public]
PUT    /posts/{id}             → Post                  [JWT: owner]
DELETE /posts/{id}             → 204                   [JWT: owner|admin]
POST   /posts/{id}/interactions → Interaction          [JWT]
  body: { type: "like"|"comment"|"share"|"save"|"hide"|"report", metadata?: {} }
GET    /search                 → Page<Post|User>        [JWT]  ?q=&type=
```

### Admin
```
GET    /admin/reports          → Page<Report>           [JWT: admin]  ?status=pending
PUT    /admin/reports/{id}     → Report                 [JWT: admin]
  body: { action: "hide"|"warn"|"restore", reason: string }
GET    /admin/users            → Page<UserProfile>      [JWT: admin]
PUT    /admin/users/{id}/status → UserProfile           [JWT: admin]
  body: { is_active: bool, reason: string }
GET    /admin/metrics          → DashboardMetrics       [JWT: admin]
GET    /admin/audit-log        → Page<AuditLog>         [JWT: admin]
```

### Recommendation (internal — not exposed via API Gateway to public)
```
GET    /recommend/feed/{user_id}?limit=50&diversity_weight=0.3 → [{ post_id, score, source }]
POST   /recommend/features/rebuild                              → { status, duration_ms }
POST   /recommend/evaluate                                      → { precision_at_k, recall_at_k, ctr, diversity }
```

---

## Ranking Formula

```
score(user, post) =
    w1 * relevance(user_vector, post_topics)    # cosine similarity
  + w2 * freshness_decay(post.created_at)       # exponential decay, half-life ~6h
  + w3 * post.safety_score                      # [0,1] from NLP worker
  - w4 * (1 - diversity_boost(post, already_selected))  # penalize same topic clusters

Defaults: w1=0.5, w2=0.2, w3=0.1, w4=0.2
diversity_weight overridable per request
```

### Interaction weights (feature store)
```
impression  → +0.1
view/read   → +0.5 to +1.0 (scaled by dwell_time, capped at 3 min)
like        → +1.5
comment     → +2.0
share       → +2.5
save        → +2.5
hide        → -2.0
report      → -5.0
```

---

## Rust Service Conventions

- Framework: **Axum** (preferred) or Actix-web
- DB: **SQLx** with compile-time checked queries, connection pool via `sqlx::PgPool`
- Errors: define `AppError` enum implementing `IntoResponse`; never `.unwrap()` in handlers
- Kafka: use `rdkafka` crate; producer sends are fire-and-confirm (don't block request)
- Redis: use `deadpool-redis` for async pool
- Middleware stack per service: `TraceLayer` → `AuthLayer` (JWT validation) → `RateLimitLayer` → handler
- Structured logging: `tracing` crate with JSON formatter in production
- Each service exports `/health` (liveness) and `/metrics` (Prometheus) endpoints

### Layered architecture per Rust service
```
src/
├── main.rs           # App setup, router, middleware chain
├── config.rs         # Env var loading via envy/figment
├── error.rs          # AppError + IntoResponse impl
├── middleware/
│   ├── auth.rs       # JWT extraction → UserId in request extensions
│   └── rate_limit.rs # Redis sliding window
├── routes/           # Axum routers grouped by domain
├── handlers/         # Request/response translation only
├── services/         # Business logic, permission checks, event publishing
├── repositories/     # SQLx queries, no business logic
├── models/           # Shared domain types (Post, User, Interaction...)
└── events/           # Kafka producer wrappers + event payload types
```

---

## Python Service Conventions (recommendation-api, workers)

- Use **FastAPI** with Pydantic v2 models for all request/response schemas
- Use **asyncpg** for PostgreSQL, **aioredis** for Redis
- Workers use **confluent-kafka** Python client
- All feature vectors stored as JSON in Redis (`pref:{user_id}`) and PostgreSQL (`user_preference_vectors`)
- Never load full interaction table into memory — use cursor-based batch processing
- Log with `structlog` (JSON output)

### recommendation-api structure
```
recommendation_api/
├── main.py
├── config.py
├── routers/
│   ├── feed.py       # GET /feed/{user_id}
│   ├── features.py   # POST /features/rebuild
│   └── evaluate.py   # POST /evaluate
├── services/
│   ├── retrieval.py  # Candidate sources: follow, topic, trending, similarity
│   ├── ranker.py     # Scoring formula, diversity reranking
│   └── feature_store.py  # Read/write preference vectors
└── models.py
```

---

## Frontend Conventions (SvelteKit)

- All API calls go through `src/lib/api.ts` — single fetch wrapper with auto token refresh
- Auth state in a Svelte store (`src/lib/stores/auth.ts`)
- Routes:
  - `/` — news feed (infinite scroll, `?cursor=`)
  - `/login`, `/register`
  - `/post/new` — create post (markdown preview, image upload)
  - `/post/[id]` — post detail + comments
  - `/profile/[id]` — user profile
  - `/admin` — admin dashboard (reports queue, metrics, audit log) — guarded by role check
- Feed post card must call `POST /posts/{id}/interactions` with `type: "view"` when post enters viewport (IntersectionObserver)

---

## Docker Compose Key Rules

- Every Rust service uses **multi-stage build**: `rust:1.78-slim` for build → `debian:bookworm-slim` for runtime
- Every Python service uses `python:3.11-slim` with `uv` for fast dep install
- All services depend on `postgres`, `redis`, `kafka` with `healthcheck` conditions
- `migrations/` volume mounted into a one-shot `migrate` service that runs on startup
- Named volumes for `postgres_data`, `redis_data`
- `.env` file is the single source of truth — never hardcode credentials in compose file

---

## NFRs & Performance Targets

| Metric | Target |
|---|---|
| GET /feed (cache hit) P95 | < 50ms |
| GET /feed (cache miss) P95 | < 1500ms |
| POST /interactions P95 | < 100ms |
| Kafka event lag (normal) | < 500 events |
| Feed cache hit rate | > 70% |
| Recommendation fallback | Always available (trending feed from Redis) |

---

## Coding Rules (enforced)

1. **No `.unwrap()` or `.expect()` in any handler or service layer** — use `?` operator with `AppError`
2. **No synchronous blocking in async context** — use `tokio::task::spawn_blocking` for CPU-bound work
3. **Every Kafka produce must log on failure** — never silently drop events
4. **Rate limiting must be applied before auth extraction** — deny unauthenticated flood attacks early
5. **Audit log every admin action** — insert to `audit_logs` in the same DB transaction as the action
6. **Redis cache invalidation on interaction** — cache-invalidator worker must process `interactions` topic before feed TTL expires
7. **Feed fallback is non-negotiable** — if `recommendation-api` returns 5xx or times out (>500ms), Feed Service returns trending feed, never 500 to client
8. **All endpoints return consistent error envelope**: `{ "error": { "code": "...", "message": "..." } }`

---

## Mock Data Seed (scripts/seed.py)

Generate for local dev:
- 500 users (mix of `user`, `creator`, `admin` roles)
- 2,000 posts across 10 topics: `tech`, `science`, `sports`, `politics`, `entertainment`, `health`, `business`, `culture`, `education`, `environment`
- 50,000 interactions with realistic distribution (most users: mostly views, few likes)
- 200 follows (social graph)
- 50 reports (mix of pending/resolved)

Run: `docker compose run --rm scripts python scripts/seed.py`

---

## Evaluation (scripts/evaluate.py)

Offline metrics on seeded data:
- **Precision@K**: fraction of top-K recommended posts the user actually interacted positively with
- **Recall@K**: fraction of all positively interacted posts that appear in top-K
- **CTR simulation**: clicks / impressions on held-out test set
- **Diversity**: average pairwise topic dissimilarity within a feed

Run: `docker compose run --rm scripts python scripts/evaluate.py --k 10`
