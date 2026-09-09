# Oecophylla — Product & Design Spec

> **On-demand reference. Not auto-loaded.** `CLAUDE.md` carries the current state and locked
> decisions; this file carries product intent and the detail you only need when touching a
> specific subsystem.
>
> **Authority rule:** where this document and the code disagree, the code wins, and this
> document is the bug. For schema, `migrations/` is authoritative. For API routing,
> `envoy/envoy.yaml` is authoritative. For env defaults, `compose.yaml` is authoritative.
> This file deliberately does **not** duplicate DDL — duplicated DDL is what rotted the
> previous version of these docs.

---

## 1. Product overview

Social networking platform with an intelligent news feed and multi-layer content moderation.
Microservices, event-driven over Kafka, with a separate Python module for ranking and a
separate offline pipeline for model training.

### Core design principles

- Every user action → structured Kafka event. Never a fire-and-forget write.
- Feed ranking is async. API latency must never block on ML inference.
- A fallback always exists: if recommendation-api is down or slow, serve the trending feed.
- Every sensitive admin action is audit-logged with actor + timestamp + reason.
- No silent failures. Every error is logged with structured context.
- Schema changes are additive and forward-only. Rollback is a new migration or a config flag.

---

## 2. Database

19 sqlx migrations in `migrations/`, applied by the one-shot `migrate` compose service.

### Table inventory (read the migration for columns)

| Table | Purpose | Introduced in |
|---|---|---|
| `users` | Accounts, roles, declared topic prefs | `..0002_users` |
| `follows` | Social graph edge (follower, followee) | `..0003_follows` |
| `posts` | Content, topics, safety_score, status, counters, search vector | `..0004_posts`, `..0005_posts_counters`, `..0012_search_discovery` |
| `interactions` | Like/save/hide/report etc., one row per (user, post, type) | `..0006_interactions` |
| `comments` | Threaded comments (`parent_id`) | `..0007_comments` |
| `reports` | Moderation report queue | `..0008_reports` |
| `user_preference_vectors` | v1 topic weight vector | `..0009_user_pref_vectors` |
| `user_preference_vectors_v2` | Time-decayed behavior + declared vector | `..0020_user_preference_vectors_v2` |
| `audit_logs` | Admin action trail | `..0010_audit_logs` |
| `notifications` | In-app notifications | `..0011_notifications` |
| `recommendation_impressions` | One row per served post, links to behavior via `impression_id` | `..0013_recommendation_telemetry` |
| `behavior_events` | Raw client behavior (visible/view/dwell) | `..0013_recommendation_telemetry` |
| `feature_event_receipts` | Idempotency receipts for the feature worker | `..0015`, `..0016` |
| `user_avatars` | Avatar blobs/metadata | `..0018_user_avatars` |
| `post_content_features` | Topics, keywords, multilingual embedding per encoder version | `..0019_post_content_features` |
| `post_content_encoder_versions` | Registered encoder versions | `..0019_post_content_features` |

Enums: `user_role`, `post_status`, `interaction_type`, `report_status`, `notification_kind`,
`audit_action`.

Functions: `prune_recommendation_telemetry(INTERVAL)` (retention, called by the Helm cron job),
`immutable_array_to_string` (search vector helper).

### Conventions

- Every PK is `uuidv7()` — Postgres 18 builtin. Never `gen_random_uuid()`.
- Telemetry retention: 180 days for `recommendation_impressions` and `behavior_events`.
- Account deletion currently deactivates the user; physical erasure and FK cascades are not invoked by that endpoint. See `docs/PROJECT_REVIEW_STATUS.md`.

---

## 3. API surface

Routing is defined in `envoy/envoy.yaml`; the browser talks to the SvelteKit server, which
proxies to Envoy. Handlers live in each service's `handlers.rs`.

### Path → service

| Prefix | Service |
|---|---|
| `/api/v1/auth/*` | auth-service :8001 |
| `/api/v1/users*` | user-service :8002 |
| `/api/v1/posts*`, `/api/v1/search` | content-service :8003 |
| `/api/v1/posts/{id}/interactions`, `/api/v1/posts/saved`, `/api/v1/interactions/*`, `/api/v1/comments/*` | interaction-service :8004 |
| `/api/v1/feed*` (incl. `/feed/trending/stream` SSE) | feed-service :8005 |
| `/admin/*` | moderation-service :8006 |
| `/api/v1/notifications*` (incl. `/notifications/stream` SSE) | notification-service :8007 |

### Internal (not exposed through the gateway)

| Endpoint | Service |
|---|---|
| `POST /recommend/feed/{user_id}` | recommendation-api :8090 |
| `POST /recommend/features/rebuild` | recommendation-api :8090 |
| `POST /recommend/evaluate` | recommendation-api :8090 |
| `GET /admin/dashboard` | analytics-service :8091 |

Every HTTP service also exposes `GET /health` and `GET /metrics`.

### Error envelope

All endpoints return errors as:

```json
{ "error": { "code": "...", "message": "..." } }
```

---

## 4. Kafka

Topics are created by the `init-topics` compose service. Retention 7 days.

| Topic | Producer | Consumers |
|---|---|---|
| `oecophylla.content.created` | content-service | nlp-worker |
| `oecophylla.content.updated` | content-service | nlp-worker (re-embed) |
| `oecophylla.interactions` | interaction-service | feature-store-worker, cache-invalidator |
| `oecophylla.user.followed` | user-service | notification-service |
| `oecophylla.moderation.action` | moderation-service | notification-service |

Consumer group IDs: `oecophylla.<domain>.<purpose>` — e.g. `oecophylla.feed.cache-invalidator`,
`oecophylla.feature-store.v2`, `oecophylla.nlp.v1`, `oecophylla.notification.v1`.

**Rules**

- All events are JSON.
- Producers do not block the request path on Kafka; send is fire-and-confirm.
- A failed produce is always logged. Events are never silently dropped.

---

## 5. Redis

| Key pattern | Type | Purpose |
|---|---|---|
| `feed:{user_id}` | List | Cached ordered feed, invalidated by cache-invalidator |
| `trending:24h` | Sorted set | Trending posts, feed fallback source |
| `pref:{user_id}` | Hash | Hot copy of the preference vector |
| `notif:unread_count:{user_id}` | String | Unread badge |
| `rate:{ip|user_id}:{minute}` | Counter | Sliding-window rate limit |
| `post:meta:{post_id}` | Hash | Post metadata cache |

TTLs come from env (`FEED_CACHE_TTL_SECONDS`, `USER_VECTOR_CACHE_TTL_SECONDS`); see `compose.yaml`.

---

## 6. Ranking

### Heuristic ranker (`heuristic-v1`, current production default)

```
score(user, post) =
    w1 * relevance(user_vector, post_topics)      # cosine similarity
  + w2 * freshness_decay(post.created_at)         # exponential, half-life ~6h
  + w3 * post.safety_score                        # [0,1] from nlp-worker
  - w4 * (1 - diversity_boost(post, selected))    # penalize topic clusters

Defaults: w1=0.5, w2=0.2, w3=0.1, w4=0.2
```

Implementation: `recommendation_api/app/ranking.py`. Live constants there win over this doc.

### Preference vector v2

Time-decayed behavior signal blended with declared interests:

```
PREFERENCE_HALF_LIFE_HOURS=720
PREFERENCE_BEHAVIOR_COEFFICIENT=0.75
PREFERENCE_DECLARED_COEFFICIENT=0.25
PREFERENCE_EVIDENCE_SATURATION=2.5
```

Written by `workers/feature_store_worker/app/features.py`, read by `recommendation_api/app/features.py`.

### Interaction weights

```
impression  → +0.1     like     → +1.5     save   → +2.5
view/read   → +0.5..+1.0 (dwell-scaled, capped 3 min)
comment     → +2.0     share    → +2.5
hide        → -2.0     report   → -5.0
```

Canonical label semantics — which of these count as positive, qualified_read, strong_negative —
live in `recommendation_label/__init__.py` (`engagement-label-v2`), **not** here. Telemetry, the
feature worker, the dataset builder and the evaluator all import that one module.

### ML ranker

Shadow only. `RANKER_MODE=heuristic` is the production default; `RANKER_MODE=model` loads the
artifact from `MODEL_ARTIFACT_PATH`. ML failure or timeout falls back to heuristic — non-negotiable.
Release gates: `docs/AI_ML_RELEASE_STATUS.md`.

---

## 7. Non-functional targets

| Metric | Target |
|---|---|
| `GET /feed` P95, cache hit | < 50 ms |
| `GET /feed` P95, cache miss | < 1500 ms |
| `POST /interactions` P95 | < 100 ms |
| Kafka consumer lag, normal | < 500 events |
| Feed cache hit rate | > 70 % |
| Recommendation fallback | Always available |

---

## 8. Service conventions

### Rust (Axum + SQLx + Tokio)

- Layered per service: `main.rs` (router/middleware) → `handlers.rs` (request/response only) →
  `repo.rs` (SQL only). Shared code goes in `backend/crates/common`.
- No `.unwrap()` / `.expect()` in handler or service layers. Use `?` with `AppError`.
- No blocking in async context — `tokio::task::spawn_blocking` for CPU-bound work.
- SQLx compile-time checked queries; `cargo sqlx prepare` after changing SQL (`make sqlx-prepare`).
- Middleware order: trace → rate limit → auth. Rate limiting runs **before** auth extraction so
  unauthenticated floods are denied early.
- Structured logging via `tracing`, JSON in production.
- Every admin action writes to `audit_logs` **in the same transaction** as the action.

### Python (FastAPI + asyncpg)

- Pydantic v2 for every request/response schema.
- Never load a full table into memory — cursor-based batch processing.
- `structlog` JSON output.
- Workers are idempotent: replaying an event must not double-count. See `feature_event_receipts`.
- `pytest.ini` needs `pythonpath = .` because tests import `from app.X import Y`.

### Frontend (SvelteKit)

- All API calls go through `frontend/src/lib/api.ts` — single fetch path with token refresh.
- Tailwind-first. Extract a named class only when a pattern repeats across 3+ components.
- Feed cards report a view via IntersectionObserver.

---

## 9. Non-negotiable invariants (from the MIND plan)

1. Request identity is `(user_id, request_id)` online, `H(salt:user_id:request_id)` offline.
   One identity belongs to exactly one temporal split.
2. Features and histories for an impression may use only information from before its serving time.
3. Raw user/post identities must never appear in training artifacts.
4. One versioned label contract for telemetry, features, dataset, and evaluation.
5. ML failure or timeout returns the heuristic feed.
6. MIND is a benchmark/schema reference. Production training must include Vietnamese,
   production-domain telemetry.
7. Production default stays heuristic until a temporal holdout **and** a live shadow gate pass.
8. `LEGACY_VIEW_COUNTER_ENABLED` and `BEHAVIOR_VIEW_COUNTER_ENABLED` must never both be true.

Full plan and task breakdown: `plans/oecophylla-mind-aligned-recommendation-completion.md`.
