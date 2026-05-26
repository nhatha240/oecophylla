# Phase 2B: Feed, Recommendation & Workers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship live personalized feed for Oecophylla: Rust `feed-service`, internal Python `recommendation-api`, Python `feature-store-worker`, Rust `cache-invalidator`, Redis feed/preference/trending caches, and frontend `/` infinite scroll with bulk interaction-state hydration.

**Architecture:** Envoy routes authenticated browser traffic to Rust services, with `feed-service` owning JWT auth, Redis feed cache, cursor slicing, post hydration, and recommendation fallback. Python `recommendation-api` remains internal-only and owns candidate retrieval, scoring, diversity rerank, feature rebuild, and MVP evaluation. Kafka consumers keep preference/trending state hot and invalidate per-user feed cache after interactions.

**Tech Stack:** Rust 1.85, Axum, SQLx, deadpool-redis, rdkafka, Python 3.13, FastAPI, asyncpg, redis-py, aiokafka, Postgres 18, Redis, Kafka KRaft, Envoy, Prometheus, SvelteKit, Tailwind.

---

**Companion spec:** `docs/superpowers/specs/2026-05-26-phase-2b-feed-recommendation-design.md`.

**Working directory:** `/Users/nhathaminh/oecophylla`.

**Baseline:** repo on `main`, expected tags `phase-0-1-complete` and `phase-2a-complete`.

**Key decisions from spec:** one full 2B scope; candidate pool 300; feed-service timeout to recommendation-api = 500ms; fallback feed always available; bulk `/me` in interaction-service; topic keyword fallback in content-service; cursor infinite scroll; micro-batch feature worker every 5s/100 events.

---

## Execution protocol

- Execute tasks in order unless the controller explicitly splits a task into smaller subtasks before dispatch.
- Use a fresh implementation subagent per task.
- After each task, run spec-compliance review first and code-quality review second.
- Do not dispatch multiple implementation subagents in parallel because the repo has shared workspace, compose, frontend, and Cargo files.
- Do not edit unrelated dirty files. Current dirty paths include `frontend/src/routes/+layout.svelte`, `frontend/src/routes/+page.svelte`, `frontend/src/lib/apple-glass/`, `.claude/`, and older Phase 2A docs unless a task explicitly names them.
- Every implementation task must end with a focused verification command and a commit unless verification is blocked by missing services or dependency downloads. If blocked, record the exact command and error in the task handoff.

---

## File structure map

New Rust service files:
- `backend/services/feed-service/Cargo.toml` declares the feed-service package and dependencies.
- `backend/services/feed-service/src/main.rs` wires tracing, config, DB, Redis, HTTP client, routes, auth, rate limit, health, and metrics.
- `backend/services/feed-service/src/state.rs` owns app config and shared state.
- `backend/services/feed-service/src/types.rs` owns request/response/cache structs.
- `backend/services/feed-service/src/repo.rs` owns feed hydration and fallback SQL.
- `backend/services/feed-service/src/cache.rs` owns Redis feed/trending helpers.
- `backend/services/feed-service/src/recommendation.rs` owns the internal recommendation HTTP client.
- `backend/services/feed-service/src/handlers.rs` owns `/api/v1/feed`.
- `backend/services/feed-service/tests/smoke.rs` owns feed smoke coverage.

New Rust worker files:
- `backend/services/cache-invalidator/Cargo.toml` declares the worker package and dependencies.
- `backend/services/cache-invalidator/src/main.rs` wires tracing, env config, Redis, Kafka, and shutdown.
- `backend/services/cache-invalidator/src/consumer.rs` owns Kafka event parsing, Redis `DEL feed:{user_id}`, and offset commits.

Existing Rust service touchpoints:
- `backend/crates/common/src/middleware/rate_limit.rs` adds reusable user/IP rate-limit policy support.
- `backend/services/interaction-service/src/{main.rs,handlers.rs,repo.rs}` adds bulk `/me` and route limits.
- `backend/services/content-service/src/{handlers.rs,repo.rs,topics.rs}` adds deterministic topic inference.

New Python services:
- `recommendation_api/app/{main.py,settings.py,schemas.py,db.py,features.py,ranking.py,evaluate.py}` implement recommendation API.
- `workers/feature_store_worker/app/{main.py,settings.py,features.py}` implements Kafka preference/trending worker.

Frontend touchpoints:
- `frontend/src/lib/types.ts` adds feed and interaction-state types.
- `frontend/src/lib/api.ts` adds feed and batch interaction helpers.
- `frontend/src/routes/+page.server.ts` loads initial feed and batch state server-side.
- `frontend/src/routes/+page.svelte` replaces the current mock app root with the live feed surface.
- `frontend/src/lib/components/FeedList.svelte` renders feed posts.
- `frontend/src/lib/components/InfiniteSentinel.svelte` owns cursor pagination sentinel.
- `frontend/src/lib/actions/viewTracker.ts` sends once-per-session view events.

Infrastructure touchpoints:
- `compose.yaml`, `compose.dev.yaml`, `envoy/envoy.yaml`, `infra/kafka/init-topics.sh`, and `infra/prometheus/prometheus.yml` wire runtime services, routes, topics, and scrape config.

---

## Milestone overview

| M | Tasks | Outcome |
|---|---|---|
| M1 | 1–3 | DB migration + Rust workspace scaffolds |
| M2 | 4–6 | interaction/content touchpoints and rate limits |
| M3 | 7–10 | feed-service implemented + tested |
| M4 | 11–14 | recommendation-api implemented + tested |
| M5 | 15–17 | feature-store-worker + cache-invalidator |
| M6 | 18–21 | compose/envoy/prometheus/frontend live feed |
| M7 | 22–24 | integration smoke, docs, final verification |

Parallelism opportunities:
- Tasks 2 and 3 can run after Task 1 if they coordinate `backend/Cargo.toml` sequentially first.
- Tasks 4 and 5 touch different services and can run in parallel.
- Tasks 7–10 (`feed-service`) can run in parallel with Tasks 11–14 (`recommendation-api`) after Task 1 and compose env keys exist.
- Tasks 15 (`feature-store-worker`) and 16 (`cache-invalidator`) can run in parallel after Task 1.
- Frontend Task 19 depends on Task 4 and Task 7 API contracts, but can start with mocks once contracts are committed.

---

## Task 1: Migration 9 for user preference vectors

**Files:**
- Create: `migrations/20260525000009_user_pref_vectors.sql`

- [ ] Write migration:

```sql
CREATE TABLE user_preference_vectors (
    user_id       UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    topic_weights JSONB NOT NULL DEFAULT '{}',
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_user_pref_vectors_updated_at
    ON user_preference_vectors (updated_at DESC);

CREATE TRIGGER trg_user_pref_vectors_updated_at BEFORE UPDATE ON user_preference_vectors
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

- [ ] Verify:

```bash
cd /Users/nhathaminh/oecophylla
docker compose up migrate
docker compose exec postgres psql -U oecophylla -d oecophylla -c "\d user_preference_vectors"
```

Expected: table exists; `user_id` PK; `topic_weights jsonb`; trigger present.

---

## Task 2: Add Rust workspace members

**Files:**
- Modify: `backend/Cargo.toml`
- Create: `backend/services/feed-service/Cargo.toml`
- Create: `backend/services/feed-service/src/main.rs`
- Create: `backend/services/cache-invalidator/Cargo.toml`
- Create: `backend/services/cache-invalidator/src/main.rs`

- [ ] Add workspace members:

```toml
members = [
    "crates/common",
    "services/auth-service",
    "services/user-service",
    "services/content-service",
    "services/interaction-service",
    "services/feed-service",
    "services/cache-invalidator",
]
```

- [ ] `feed-service/Cargo.toml`:

```toml
[package]
name = "feed-service"
version = "0.1.0"
edition.workspace = true
rust-version.workspace = true

[dependencies]
anyhow.workspace = true
axum.workspace = true
chrono.workspace = true
common.workspace = true
deadpool-redis.workspace = true
reqwest.workspace = true
serde.workspace = true
serde_json.workspace = true
sqlx.workspace = true
tokio.workspace = true
tracing.workspace = true
uuid.workspace = true

[dev-dependencies]
reqwest.workspace = true
serde_json.workspace = true
```

- [ ] `cache-invalidator/Cargo.toml`:

```toml
[package]
name = "cache-invalidator"
version = "0.1.0"
edition.workspace = true
rust-version.workspace = true

[dependencies]
anyhow.workspace = true
common.workspace = true
deadpool-redis.workspace = true
rdkafka.workspace = true
serde.workspace = true
serde_json.workspace = true
tokio.workspace = true
tracing.workspace = true
uuid.workspace = true
```

- [ ] Add health stubs:

```rust
use axum::{routing::get, Router};
use std::net::SocketAddr;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    common::middleware::trace::init_tracing("feed-service");
    let app = Router::new().route("/health", get(|| async { "ok" }));
    let addr: SocketAddr = std::env::var("FEED_BIND")
        .unwrap_or_else(|_| "0.0.0.0:8005".into())
        .parse()?;
    let listener = tokio::net::TcpListener::bind(addr).await?;
    tracing::info!(?addr, "feed-service listening");
    axum::serve(listener, app).await?;
    Ok(())
}
```

For `cache-invalidator`, use a loop stub that logs startup and waits on Ctrl-C.

- [ ] Verify:

```bash
cd /Users/nhathaminh/oecophylla/backend
cargo check --workspace
```

---

## Task 3: Dockerfiles for new Rust binaries

**Files:**
- Create: `backend/services/feed-service/Dockerfile`
- Create: `backend/services/cache-invalidator/Dockerfile`

- [ ] Use the existing Rust service Dockerfile pattern with these constraints:

```dockerfile
FROM rust:1.85 AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake pkg-config libssl-dev ca-certificates && rm -rf /var/lib/apt/lists/*
COPY backend ./backend
WORKDIR /app/backend
RUN cargo build --release -p feed-service

FROM debian:trixie-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates libssl3 libpq5 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/backend/target/release/feed-service /usr/local/bin/feed-service
EXPOSE 8005
CMD ["feed-service"]
```

For `cache-invalidator`, replace binary name and omit `EXPOSE`.

---

## Task 4: interaction-service bulk `/me` endpoint

**Files:**
- Modify: `backend/services/interaction-service/src/handlers.rs`
- Modify: `backend/services/interaction-service/src/repo.rs`
- Modify: `backend/services/interaction-service/src/main.rs`
- Modify/add: `backend/services/interaction-service/tests/smoke.rs`
- Modify: `envoy/envoy.yaml`

- [ ] Add request/response types:

```rust
#[derive(serde::Deserialize)]
pub struct BatchMeRequest {
    pub post_ids: Vec<uuid::Uuid>,
}

#[derive(serde::Serialize)]
pub struct MyInteractionState {
    pub liked: bool,
    pub saved: bool,
    pub shared: bool,
    pub hidden: bool,
    pub reported_pending: bool,
}

#[derive(serde::Serialize)]
pub struct BatchMeResponse {
    pub items: std::collections::HashMap<uuid::Uuid, MyInteractionState>,
}
```

- [ ] Add repo query:

```sql
SELECT
  p.id AS post_id,
  COALESCE(bool_or(i.type = 'like'), false) AS liked,
  COALESCE(bool_or(i.type = 'save'), false) AS saved,
  COALESCE(bool_or(i.type = 'share'), false) AS shared,
  COALESCE(bool_or(i.type = 'hide'), false) AS hidden,
  EXISTS (
    SELECT 1 FROM reports r
    WHERE r.reporter_id = $1 AND r.post_id = p.id AND r.status = 'pending'
  ) AS reported_pending
FROM unnest($2::uuid[]) AS p(id)
LEFT JOIN interactions i ON i.user_id = $1 AND i.post_id = p.id
GROUP BY p.id;
```

- [ ] Handler validation:
  - `post_ids.len()` must be `1..=100`.
  - Return standard `VALIDATION_FAILED` on invalid length.
  - Requires auth.

- [ ] Route:

```rust
.route("/api/v1/interactions/me/batch", post(handlers::batch_me))
```

- [ ] Envoy route before the broad posts/content routes:

```yaml
- match: { prefix: "/api/v1/interactions/me/batch" }
  route:  { cluster: interaction_cluster }
```

- [ ] Smoke test:
  - Create user + post, like/save/report.
  - POST batch with that post and another post.
  - Assert correct booleans.
  - POST 101 IDs returns 400.

---

## Task 5: content-service keyword topic fallback

**Files:**
- Modify: `backend/services/content-service/src/handlers.rs`
- Modify: `backend/services/content-service/src/repo.rs`
- Add: `backend/services/content-service/src/topics.rs`
- Modify/add: `backend/services/content-service/tests/smoke.rs`

- [ ] Add helper:

```rust
pub fn infer_topics(content: &str, tags: &[String], explicit: &[String]) -> Vec<String> {
    if !explicit.is_empty() {
        return explicit.to_vec();
    }
    let lower = content.to_lowercase();
    let mut topics = Vec::new();
    let rules = [
        ("ai", ["ai", "trí tuệ nhân tạo", "mô hình", "llm", "machine learning"].as_slice()),
        ("tech", ["công nghệ", "phần mềm", "dữ liệu", "bảo mật", "điện toán"].as_slice()),
        ("econ", ["kinh tế", "lãi suất", "chứng khoán", "doanh nghiệp", "ngân hàng"].as_slice()),
        ("edu", ["giáo dục", "học sinh", "trường", "kỹ năng", "edtech"].as_slice()),
        ("life", ["đời sống", "đô thị", "văn hoá", "du lịch", "ẩm thực"].as_slice()),
        ("health", ["y tế", "sức khỏe", "vacxin", "dinh dưỡng"].as_slice()),
        ("soc", ["chính sách", "xã hội", "chính trị", "cộng đồng"].as_slice()),
        ("code", ["lập trình", "rust", "svelte", "backend", "frontend"].as_slice()),
    ];
    for (topic, keywords) in rules {
        if keywords.iter().any(|kw| lower.contains(kw)) {
            topics.push(topic.to_string());
        }
    }
    if topics.is_empty() && !tags.is_empty() {
        topics.extend(tags.iter().take(3).cloned());
    }
    if topics.is_empty() {
        topics.push("general".to_string());
    }
    topics.sort();
    topics.dedup();
    topics
}
```

- [ ] Use on create/update only if request topics empty.
- [ ] Smoke test: content containing `AI` gets `topics @> ARRAY['ai']`.

---

## Task 6: Mount per-route rate limits

**Files:**
- Modify: `backend/crates/common/src/middleware/rate_limit.rs`
- Modify: `backend/services/interaction-service/src/main.rs`
- Modify: `backend/services/feed-service/src/main.rs` after Task 7

- [ ] Replace the single public-IP-only policy with a reusable policy that supports named buckets and authenticated users when `AuthUser` is present:

```rust
#[derive(Clone)]
pub struct RateLimitPolicy {
    pub key_prefix: &'static str,
    pub max_per_minute: u32,
}

#[derive(Clone)]
pub struct RateLimitState {
    pub redis: deadpool_redis::Pool,
    pub policy: RateLimitPolicy,
}
```

- [ ] Apply:
  - interaction toggles: `120/min/user`
  - report: `10/min/user`
  - comments: `20/min/user`
  - `/me`, bulk `/me`: `200/min/user`
  - feed: `120/min/user`

- [ ] Add one smoke assertion where repeated small-limit route returns 429 under a test-only env override.
- [ ] Verify:

```bash
cd /Users/nhathaminh/oecophylla/backend
cargo test -p interaction-service --test smoke -- --nocapture
```

Expected: smoke tests pass and the rate-limit assertion observes HTTP 429 under the test-only low limit.

---

## Task 7: feed-service state/config/types

**Files:**
- Create: `backend/services/feed-service/src/state.rs`
- Create: `backend/services/feed-service/src/types.rs`
- Modify: `backend/services/feed-service/src/main.rs`

- [ ] Config env:

```env
FEED_BIND=0.0.0.0:8005
DATABASE_URL=postgres://...
REDIS_URL=redis://...
JWT_SECRET=...
RECOMMENDATION_SERVICE_URL=http://recommendation-api:8090
FEED_CACHE_TTL_SECONDS=600
FEED_RECOMMENDATION_TIMEOUT_MS=500
FEED_RESULT_SIZE=50
```

- [ ] Types:

```rust
#[derive(serde::Serialize, sqlx::FromRow)]
pub struct FeedPostRow {
    pub id: uuid::Uuid,
    pub author_id: uuid::Uuid,
    pub username: String,
    pub display_name: Option<String>,
    pub avatar_url: Option<String>,
    pub content: String,
    pub media_urls: Vec<String>,
    pub tags: Vec<String>,
    pub topics: Vec<String>,
    pub safety_score: f32,
    pub like_count: i32,
    pub comment_count: i32,
    pub save_count: i32,
    pub share_count: i32,
    pub view_count: i64,
    pub created_at: chrono::DateTime<chrono::Utc>,
}

#[derive(serde::Serialize, serde::Deserialize)]
pub struct CachedFeed {
    pub generated_at: chrono::DateTime<chrono::Utc>,
    pub source: String,
    pub items: Vec<uuid::Uuid>,
}
```

- [ ] Main wires DB, Redis, reqwest client, auth middleware, `/api/v1/feed`, `/health`, `/metrics`.

---

## Task 8: feed-service repo and cache

**Files:**
- Create: `backend/services/feed-service/src/repo.rs`
- Create: `backend/services/feed-service/src/cache.rs`

- [ ] Repo queries:

```sql
-- hydrate ordered post IDs, preserving input order
SELECT p.id, p.author_id, u.username, u.display_name, u.avatar_url,
       p.content, p.media_urls, p.tags, p.topics, p.safety_score,
       p.like_count, p.comment_count, p.save_count, p.share_count,
       p.view_count, p.created_at
FROM unnest($1::uuid[]) WITH ORDINALITY AS ids(id, ord)
JOIN posts p ON p.id = ids.id
JOIN users u ON u.id = p.author_id
WHERE p.status = 'published'
ORDER BY ids.ord;

-- recent fallback
SELECT ...
FROM posts p JOIN users u ON u.id = p.author_id
WHERE p.status = 'published'
ORDER BY p.created_at DESC
LIMIT $1;
```

- [ ] Cache helpers:

```rust
pub async fn get_cached_feed(redis: &deadpool_redis::Pool, user_id: uuid::Uuid) -> anyhow::Result<Option<CachedFeed>>;
pub async fn set_cached_feed(redis: &deadpool_redis::Pool, user_id: uuid::Uuid, feed: &CachedFeed, ttl_seconds: usize) -> anyhow::Result<()>;
pub async fn trending_ids(redis: &deadpool_redis::Pool, limit: usize) -> anyhow::Result<Vec<uuid::Uuid>>;
```

- [ ] Cache key constants:

```rust
pub fn feed_key(user_id: uuid::Uuid) -> String { format!("feed:{user_id}") }
pub const TRENDING_24H_KEY: &str = "trending:24h";
```

---

## Task 9: feed-service recommendation client and fallback

**Files:**
- Create: `backend/services/feed-service/src/recommendation.rs`
- Modify: `backend/services/feed-service/src/handlers.rs`

- [ ] Request/response:

```rust
#[derive(serde::Serialize)]
pub struct RecommendFeedRequest {
    pub limit: usize,
    pub candidate_pool: usize,
    pub exclude_post_ids: Vec<uuid::Uuid>,
}

#[derive(serde::Deserialize)]
pub struct RecommendationItem {
    pub post_id: uuid::Uuid,
    pub score: f32,
    pub source: String,
    pub reason: String,
}
```

- [ ] Client:

```rust
pub async fn recommend_feed(
    client: &reqwest::Client,
    base_url: &str,
    user_id: uuid::Uuid,
    req: RecommendFeedRequest,
    timeout_ms: u64,
) -> Result<Vec<RecommendationItem>, anyhow::Error> {
    let url = format!("{base_url}/recommend/feed/{user_id}");
    let res = tokio::time::timeout(
        std::time::Duration::from_millis(timeout_ms),
        client.post(url).json(&req).send(),
    ).await??;
    if !res.status().is_success() {
        anyhow::bail!("recommendation-api returned {}", res.status());
    }
    Ok(res.json::<serde_json::Value>().await?["items"]
        .as_array()
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .map(serde_json::from_value)
        .collect::<Result<Vec<_>, _>>()?)
}
```

- [ ] Handler fallback order:
  1. Cache.
  2. Recommendation API.
  3. Redis trending.
  4. Recent published from Postgres.

---

## Task 10: feed-service smoke tests

**Files:**
- Create: `backend/services/feed-service/tests/smoke.rs`

- [ ] Tests:
  - unauthenticated feed returns 401.
  - seeded user receives feed items.
  - recommendation-api timeout env (`RECOMMENDATION_SERVICE_URL=http://10.255.255.1:8090`) returns fallback.
  - second request returns `source: "cache"`.
  - cursor pages do not overlap.

- [ ] Use random username suffix from UUID:

```rust
let u = uuid::Uuid::now_v7().to_string();
let username = format!("u{}", &u[22..]);
```

- [ ] Run tests inside compose network when Kafka/Redis service DNS is required.

---

## Task 11: recommendation-api scaffold

**Files:**
- Create: `recommendation_api/requirements.txt`
- Create: `recommendation_api/Dockerfile`
- Create: `recommendation_api/app/main.py`
- Create: `recommendation_api/app/settings.py`
- Create: `recommendation_api/app/schemas.py`
- Create: `recommendation_api/tests/test_health.py`

- [ ] `requirements.txt`:

```txt
fastapi==0.115.*
uvicorn[standard]==0.34.*
pydantic==2.*
pydantic-settings==2.*
asyncpg==0.30.*
redis==5.*
httpx==0.28.*
pytest==8.*
pytest-asyncio==0.25.*
```

- [ ] Dockerfile:

```dockerfile
FROM python:3.13-trixie AS runtime
WORKDIR /app
COPY recommendation_api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY recommendation_api/app ./app
EXPOSE 8090
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]
```

- [ ] Minimal FastAPI:

```python
from fastapi import FastAPI

app = FastAPI(title="Oecophylla Recommendation API")

@app.get("/health")
async def health():
    return {"ok": True}
```

- [ ] Verify:

```bash
cd /Users/nhathaminh/oecophylla
python -m pytest recommendation_api/tests
```

If local Python deps are unavailable, run via Docker in Task 20.

---

## Task 12: recommendation retrieval and ranking

**Files:**
- Create: `recommendation_api/app/db.py`
- Create: `recommendation_api/app/features.py`
- Create: `recommendation_api/app/ranking.py`
- Modify: `recommendation_api/app/main.py`
- Add: `recommendation_api/tests/test_ranking.py`

- [ ] Ranking function:

```python
from math import exp
from datetime import datetime, timezone

def freshness_decay(created_at: datetime, half_life_hours: float = 36.0) -> float:
    age_hours = max(0.0, (datetime.now(timezone.utc) - created_at).total_seconds() / 3600.0)
    return exp(-age_hours / half_life_hours)

def relevance(user_vec: dict[str, float], post_topics: list[str]) -> float:
    if not user_vec or not post_topics:
        return 0.0
    total = sum(abs(v) for v in user_vec.values()) or 1.0
    return sum(max(user_vec.get(t, 0.0), 0.0) for t in post_topics) / total

def score_post(user_vec, post, weights=(0.5, 0.2, 0.1, 0.2), diversity_boost=1.0):
    w1, w2, w3, w4 = weights
    return (
        w1 * relevance(user_vec, post["topics"])
        + w2 * freshness_decay(post["created_at"])
        + w3 * float(post["safety_score"])
        - w4 * (1.0 - diversity_boost)
    )
```

- [ ] Candidate SQL functions:
  - recent followed-author posts.
  - topic overlap posts.
  - recent published posts.
  - metadata for Redis trending IDs.

- [ ] `/recommend/feed/{user_id}`:
  - load `pref:{user_id}` from Redis; fallback PG `user_preference_vectors`; fallback `users.topic_prefs`.
  - gather up to `candidate_pool=300`.
  - score + diversity rerank.
  - return top `limit`.

---

## Task 13: recommendation diversity rerank

**Files:**
- Modify: `recommendation_api/app/ranking.py`
- Add: `recommendation_api/tests/test_diversity.py`

- [ ] Implement:

```python
def diversity_rerank(items: list[dict], limit: int) -> list[dict]:
    selected: list[dict] = []
    remaining = sorted(items, key=lambda x: x["score"], reverse=True)
    while remaining and len(selected) < limit:
        def adjusted(item):
            penalty = 0.0
            if selected and item.get("author_id") == selected[-1].get("author_id"):
                penalty += 0.08
            if selected and item.get("primary_topic") == selected[-1].get("primary_topic"):
                penalty += 0.05
            seen_topics = {x.get("primary_topic") for x in selected}
            if item.get("primary_topic") in seen_topics and len(seen_topics) < 3:
                penalty += 0.04
            return item["score"] - penalty
        best = max(remaining, key=adjusted)
        remaining.remove(best)
        selected.append(best)
    return selected
```

- [ ] Test: 10 high-score same-topic items + 3 alternatives should place at least 2 topics in top 5 when alternatives exist.

---

## Task 14: recommendation rebuild and evaluate endpoints

**Files:**
- Create: `recommendation_api/app/evaluate.py`
- Modify: `recommendation_api/app/main.py`
- Add: `recommendation_api/tests/test_evaluate.py`

- [ ] `/recommend/features/rebuild`:
  - If `user_id` provided, recompute that user from `interactions JOIN posts`.
  - Else recompute all users with interactions.
  - Upsert `user_preference_vectors`.
  - Write Redis `pref:{user_id}` TTL 1800.

- [ ] `/recommend/evaluate` MVP:

```json
{
  "precision_at_k": 0.0,
  "ctr_simulation": 0.0,
  "diversity": 0.0,
  "fallback_rate": 0.0
}
```

Compute:
- `precision_at_k`: fraction of top K with topics overlapping positive user vector.
- `ctr_simulation`: average normalized score of top K.
- `diversity`: unique primary topics / K.
- `fallback_rate`: `0.0` in API-local evaluation unless recommendation generation fails.

---

## Task 15: feature-store-worker

**Files:**
- Create: `workers/feature_store_worker/requirements.txt`
- Create: `workers/feature_store_worker/Dockerfile`
- Create: `workers/feature_store_worker/app/main.py`
- Create: `workers/feature_store_worker/app/settings.py`
- Create: `workers/feature_store_worker/app/features.py`
- Add: `workers/feature_store_worker/tests/test_features.py`

- [ ] `requirements.txt`:

```txt
asyncpg==0.30.*
redis==5.*
aiokafka==0.12.*
pydantic==2.*
pydantic-settings==2.*
pytest==8.*
pytest-asyncio==0.25.*
```

- [ ] Dockerfile:

```dockerfile
FROM python:3.13-trixie
WORKDIR /app
COPY workers/feature_store_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY workers/feature_store_worker/app ./app
CMD ["python", "-m", "app.main"]
```

- [ ] Micro-batch rules:
  - poll `oecophylla.interactions`
  - group events by `user_id`
  - flush every 5 seconds or 100 events
  - upsert PG JSONB
  - write Redis `pref:{user_id}` TTL 1800
  - update `trending:24h` sorted set TTL 300

- [ ] Feature function:

```python
WEIGHTS = {
    "liked": 1.5, "unliked": -1.5,
    "saved": 2.5, "unsaved": -2.5,
    "shared": 2.5, "unshared": -2.5,
    "hidden": -2.0,
    "reported": -5.0,
    "commented": 1.0,
    "comment_replied": 0.7,
}

def apply_topic_delta(vec: dict[str, float], topics: list[str], event_type: str) -> dict[str, float]:
    if not topics:
        topics = ["general"]
    delta = WEIGHTS.get(event_type, 0.0) / len(topics)
    out = dict(vec)
    for topic in topics:
        out[topic] = round(out.get(topic, 0.0) + delta, 4)
    return out
```

---

## Task 16: cache-invalidator consumer

**Files:**
- Create: `backend/services/cache-invalidator/src/main.rs`
- Create: `backend/services/cache-invalidator/src/consumer.rs`

- [ ] Consumer config:

```rust
ClientConfig::new()
    .set("bootstrap.servers", brokers)
    .set("group.id", "oecophylla.feed.cache-invalidator.v1")
    .set("enable.auto.commit", "false")
    .set("auto.offset.reset", "earliest")
```

- [ ] For each event:
  - parse envelope.
  - extract `user_id`, `reporter_id`, or `commenter_id`.
  - `DEL feed:{user_id}`.
  - commit message offset after successful DEL.

- [ ] Log and skip malformed events; do not panic.

---

## Task 17: Kafka topics/init updates

**Files:**
- Modify: `infra/kafka/init-topics.sh`
- Modify: `compose.yaml`

- [ ] Ensure topics:

```bash
oecophylla.content.created
oecophylla.user.followed
oecophylla.interactions
```

`oecophylla.interactions` already exists from Phase 2A; keep `--if-not-exists`.

- [ ] No Zookeeper. Keep `apache/kafka:4.0.0` KRaft.
- [ ] Verify:

```bash
cd /Users/nhathaminh/oecophylla
docker compose up kafka-init
```

Expected: topic creation logs show `oecophylla.interactions` exists or is created without failing.

---

## Task 18: Compose, Envoy, Prometheus wiring

**Files:**
- Modify: `compose.yaml`
- Modify: `compose.dev.yaml`
- Modify: `envoy/envoy.yaml`
- Modify: `infra/prometheus/prometheus.yml`

- [ ] Add services:
  - `feed-service`
  - `recommendation-api`
  - `feature-store-worker`
  - `cache-invalidator`

- [ ] Feed env:

```yaml
RECOMMENDATION_SERVICE_URL: http://recommendation-api:8090
FEED_CACHE_TTL_SECONDS: 600
FEED_RECOMMENDATION_TIMEOUT_MS: 500
FEED_RESULT_SIZE: 50
FEED_CANDIDATE_POOL_SIZE: 300
```

- [ ] Envoy route order:
  - `/api/v1/interactions/me/batch` → interaction-service
  - `/api/v1/feed` → feed-service
  - existing interaction post regex → interaction-service
  - broad `/api/v1/posts` → content-service

- [ ] Prometheus scrape:
  - `feed-service:8005/metrics`
  - recommendation-api metrics can be deferred unless implemented; healthcheck still required.
- [ ] Do not add `.env.example`; this repo currently has no tracked `.env.example`.
- [ ] Verify:

```bash
cd /Users/nhathaminh/oecophylla
docker compose config >/tmp/oecophylla-compose-phase2b.yaml
```

Expected: compose config renders successfully and includes `feed-service`, `recommendation-api`, `feature-store-worker`, and `cache-invalidator`.

---

## Task 19: Frontend types and API helpers

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] Add types:

```ts
export interface FeedRank {
  score: number;
  source: 'follow' | 'topic' | 'trending' | 'similarity' | 'fallback';
  reason: string;
}

export interface FeedPost extends Post {
  author: Pick<User, 'id' | 'username' | 'display_name' | 'avatar_url'>;
  topics: string[];
  safety_score: number;
  rank: FeedRank;
}

export interface FeedResponse {
  items: FeedPost[];
  next_cursor: string | null;
  source: 'cache' | 'personalized' | 'fallback';
  generated_at: string;
}

export interface BatchMeResponse {
  items: Record<string, MyInteractions>;
}
```

- [ ] API helpers:

```ts
export async function getFeed(fetcher: typeof fetch, cursor?: string, limit = 20) {
  const qs = new URLSearchParams({ limit: String(limit) });
  if (cursor) qs.set('cursor', cursor);
  return apiFetch<FeedResponse>(fetcher, `/feed?${qs}`);
}

export async function getMyInteractionsBatch(fetcher: typeof fetch, postIds: string[]) {
  return apiFetch<BatchMeResponse>(fetcher, '/interactions/me/batch', {
    method: 'POST',
    body: JSON.stringify({ post_ids: postIds }),
  });
}
```

---

## Task 20: Frontend live root feed

**Files:**
- Create: `frontend/src/routes/+page.server.ts`
- Modify: `frontend/src/routes/+page.svelte`
- Create: `frontend/src/lib/components/InfiniteSentinel.svelte`
- Create: `frontend/src/lib/components/FeedList.svelte`
- Modify: `frontend/src/lib/components/PostCard.svelte`
- Modify: `frontend/src/lib/components/PostActionBar.svelte`

- [ ] `+page.server.ts`:

```ts
import { getFeed, getMyInteractionsBatch } from '$lib/api';

export async function load({ fetch }) {
  const feed = await getFeed(fetch, undefined, 20);
  const postIds = feed.items.map((p) => p.id);
  const me = postIds.length ? await getMyInteractionsBatch(fetch, postIds).catch(() => ({ items: {} })) : { items: {} };
  return { feed, me: me.items };
}
```

- [ ] Infinite sentinel component:

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  export let disabled = false;
  export let onVisible: () => void;
  let el: HTMLDivElement;
  onMount(() => {
    const io = new IntersectionObserver((entries) => {
      if (!disabled && entries.some((e) => e.isIntersecting)) onVisible();
    }, { rootMargin: '400px' });
    io.observe(el);
    return () => io.disconnect();
  });
</script>
<div bind:this={el} aria-hidden="true" class="h-8"></div>
```

- [ ] `+page.svelte`:
  - render initial `data.feed.items`.
  - maintain `items`, `meByPost`, `cursor`, `loading`.
  - on sentinel visible, fetch next page once.
  - merge batch `/me`.
  - replace the current `<AppleGlassApp />` root render with the live feed layout.
- [ ] `FeedList.svelte`:
  - accept `items: FeedPost[]` and `meByPost: Record<string, MyInteractions>`.
  - render each item through the existing `PostCard` and pass hydrated action state to `PostActionBar`.
- [ ] Verify:

```bash
cd /Users/nhathaminh/oecophylla/frontend
pnpm run check
```

Expected: Svelte type-check succeeds without duplicate loading or prop errors.

---

## Task 21: Frontend view tracking

**Files:**
- Create: `frontend/src/lib/actions/viewTracker.ts`
- Use in post card/feed list component.

- [ ] Action:

```ts
export function viewTracker(node: HTMLElement, postId: string) {
  let timer: ReturnType<typeof setTimeout> | null = null;
  let sent = false;
  const io = new IntersectionObserver((entries) => {
    const visible = entries.some((e) => e.isIntersecting && e.intersectionRatio >= 0.5);
    if (visible && !sent && !timer) {
      timer = setTimeout(async () => {
        sent = true;
        await fetch(`/api/v1/posts/${postId}/view`, { method: 'POST', headers: { 'x-requested-with': 'oec-web' } }).catch(() => {});
      }, 800);
    }
    if (!visible && timer) {
      clearTimeout(timer);
      timer = null;
    }
  }, { threshold: [0.5] });
  io.observe(node);
  return { destroy() { if (timer) clearTimeout(timer); io.disconnect(); } };
}
```

- [ ] Ensure one view per post per page session.

---

## Task 22: Python and Rust test commands in Makefile/README

**Files:**
- Modify: `Makefile`
- Modify: `README.md`

- [ ] Add targets:

```make
test-python:
	cd recommendation_api && pytest
	cd workers/feature_store_worker && pytest

test-phase-2b:
	cd backend && cargo test --workspace --no-fail-fast
	cd frontend && pnpm run check && pnpm run build
	$(MAKE) test-python
```

- [ ] README documents:
  - new services and ports.
  - `GET /api/v1/feed`.
  - how to verify fallback: stop recommendation-api and call feed.
  - Kafka smoke must run in compose network / `docker exec`.

---

## Task 23: Integration smoke script

**Files:**
- Create: `scripts/smoke_phase2b.sh`

- [ ] Script outline:

```bash
#!/usr/bin/env bash
set -euo pipefail

curl -fsS http://localhost:8080/api/v1/feed >/tmp/feed_unauth.json && {
  echo "expected unauth feed to fail"; exit 1;
} || true

echo "Use existing auth smoke or create a dev user, then:"
echo "1. login"
echo "2. GET /api/v1/feed"
echo "3. stop recommendation-api"
echo "4. GET /api/v1/feed returns source=fallback"
echo "5. like post, verify feed:{user_id} is deleted"
```

Prefer a Rust smoke test for actual auth/session orchestration if existing patterns are already in service tests.

---

## Task 24: Final verification and tag

- [ ] Run:

```bash
cd /Users/nhathaminh/oecophylla
docker compose up -d --build
docker compose ps
docker compose up migrate
cd backend && cargo test --workspace --no-fail-fast
cd ../frontend && pnpm run check && pnpm run build
cd ../recommendation_api && pytest
cd ../workers/feature_store_worker && pytest
```

- [ ] Manual checks:
  - `http://localhost:3000/` renders live feed.
  - Scroll loads next page.
  - Like/save state hydrates after reload.
  - `docker compose stop recommendation-api`; feed still returns fallback.
  - Produce interaction; `feed:{user_id}` disappears.
  - `SELECT * FROM user_preference_vectors LIMIT 5;` shows updated weights.

- [ ] Tag:

```bash
git tag phase-2b-complete
```

Only tag after all DoD items pass.

---

## Execution notes for subagents

- Do not edit unrelated dirty files. Current repo may have unrelated local changes.
- Use `rg`/`rg --files` for discovery.
- Use `apply_patch` for manual edits.
- Avoid destructive commands.
- Kafka host caveat: host macOS cannot resolve `kafka:9092`; Kafka-dependent smoke runs inside compose or via `docker exec`.
- Test usernames must use UUIDv7 random suffix (`&uuid[22..]`) to avoid tight-loop collisions.
- Keep frontend Tailwind-first; do not introduce large custom CSS.
- Recommendation API and worker live outside Cargo workspace.
- Long-running container runtime base must be `debian:trixie-slim` or Trixie-based upstream.
