# Oecophylla — Phase 2B: Feed, Recommendation & Workers Design

**Status:** Draft, ready for implementation planning
**Date:** 2026-05-26
**Scope:** Phase 2B — live personalized feed, recommendation API, preference feature store, feed cache invalidation, and frontend infinite-scroll feed. Builds on tags `phase-0-1-complete` and `phase-2a-complete`.

---

## 1. Goals & non-goals

### 1.1 Goals
- Add `feed-service` (Rust, :8005) with `GET /api/v1/feed?cursor=&limit=20`.
- Add internal-only `recommendation-api` (Python FastAPI, :8090) for candidate retrieval, ranking, diversity rerank, feature rebuild, and lightweight evaluation.
- Add `feature-store-worker` (Python) consuming `oecophylla.interactions` and maintaining `user_preference_vectors` in Postgres plus Redis hot cache.
- Add `cache-invalidator` (Rust) consuming `oecophylla.interactions` and deleting `feed:{user_id}` on user interaction.
- Wire frontend `/` from mock feed to real backend with cursor infinite scroll, bulk `/me` hydration, and IntersectionObserver view tracking.
- Preserve the Phase 0+1/2A guarantees: Envoy gateway, JWT verified in services, Kafka KRaft, Postgres 18 `uuidv7()`, Redis fallback, Trixie runtime images, Tailwind-first frontend.

### 1.2 Non-goals
- Full NLP worker and production topic tagging model. Phase 2B ships a deterministic keyword fallback only.
- Full offline analytics platform. `/recommend/evaluate` ships as a small deterministic MVP; Phase 4 owns serious evaluation pipelines.
- Exactly-once Kafka processing. Workers are idempotent enough for local/dev and tolerate replay.
- Multi-device realtime feed updates, notification fanout, admin moderation queue, or audit log expansion.
- Exposing `recommendation-api` through Envoy. It remains internal-only.

---

## 2. Brainstorm decisions

The requested brainstorm questions are resolved as follows for this spec:

| Question | Decision |
|---|---|
| Scope split | One Phase 2B spec covering all 5 components. Reason: feed-service without recommendation + worker is a misleading partial system; fallback keeps execution safe. |
| Bulk `/me` endpoint | Add to `interaction-service`: `POST /api/v1/interactions/me/batch`. Recommendation response stays ranking-focused. |
| Candidate pool | `FEED_CANDIDATE_POOL_SIZE=300`, default from `CLAUDE.md`. |
| Cold start | Hybrid: followed authors first, then declared `users.topic_prefs`, then trending. If no follows/topics, trending-only. |
| Feature worker update mode | Micro-batch every 5 seconds or 100 events, whichever comes first. This reduces DB churn while staying near-realtime. |
| Topic tagging before Phase 3 | Add simple keyword extraction in `content-service` on insert/update when `topics` would otherwise be empty; seed scripts may also backfill. |
| Recommendation API auth | Internal network trust in compose for Phase 2B. No JWT signed service-to-service yet. |
| Evaluation endpoint | Implement MVP in 2B: Precision@K proxy, CTR simulation, topic diversity, fallback rate. Phase 4 extends it. |
| Infinite scroll | Cursor-based, id/served-order cursor, never offset. |
| Rate limits | Mount Redis sliding-window middleware for both `interaction-service` routes from 2A and new `feed-service` routes. |

---

## 3. Architecture & topology delta

```
Browser
  │
  ▼
SvelteKit frontend (:3000)
  │  fetch /api/v1/feed, /api/v1/interactions/me/batch, /api/v1/posts/:id/view
  ▼
Envoy (:8080)
  ├─ /api/v1/auth/*                     → auth-service        (:8001)
  ├─ /api/v1/users/*                    → user-service        (:8002)
  ├─ /api/v1/posts/*                    → content-service     (:8003)
  ├─ /api/v1/posts/:id/(like|...)       → interaction-service (:8004)
  ├─ /api/v1/interactions/me/batch      → interaction-service (:8004) ★ NEW
  └─ /api/v1/feed                       → feed-service        (:8005) ★ NEW
                                                │
                                                │ HTTP, 500ms timeout
                                                ▼
                                     recommendation-api (:8090) ★ NEW
                                     internal only; not routed by Envoy

Kafka KRaft topic: oecophylla.interactions
  ├─ feature-store-worker       group oecophylla.feature-store.preferences.v1 ★ NEW
  └─ cache-invalidator          group oecophylla.feed.cache-invalidator.v1    ★ NEW

Postgres 18:
  ├─ posts / users / follows / interactions / reports / comments
  └─ user_preference_vectors ★ NEW

Redis 8/7:
  ├─ feed:{user_id}
  ├─ pref:{user_id}
  ├─ trending:24h
  └─ post:meta:{post_id}
```

### 3.1 Component responsibilities

| Component | Responsibility |
|---|---|
| `feed-service` | Authenticated feed API, cache read/write, recommendation timeout, fallback assembly, post hydration from Postgres/Redis. |
| `recommendation-api` | Candidate retrieval, scoring, diversity rerank, evaluation MVP. No user-facing auth. |
| `feature-store-worker` | Consume interactions, update per-user topic vector, maintain `pref:{user_id}` hot cache, update `trending:24h`. |
| `cache-invalidator` | Consume interactions and delete `feed:{user_id}` after user actions. |
| Frontend `/` | Live feed, cursor infinite scroll, bulk interaction-state hydration, view tracking. |

---

## 4. Data model delta

### 4.1 Migration 9: `20260525000009_user_pref_vectors.sql`

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

`topic_weights` shape:

```json
{
  "ai": 4.25,
  "tech": 2.50,
  "econ": 0.80
}
```

### 4.2 Optional impression log

Do **not** create the full `recommendations` table in Phase 2B unless the implementation finds it necessary for `/recommend/evaluate`. The MVP evaluation can compute from existing interactions and transient feed results. The Phase 4 analytics spec owns durable impression logs.

### 4.3 Content topics quick fix

`content-service` adds deterministic topic inference when creating/updating a post and request `topics` is empty:

| Topic | Keywords |
|---|---|
| `ai` | ai, trí tuệ nhân tạo, mô hình, llm, machine learning |
| `tech` | công nghệ, phần mềm, dữ liệu, bảo mật, điện toán |
| `econ` | kinh tế, lãi suất, chứng khoán, doanh nghiệp, ngân hàng |
| `edu` | giáo dục, học sinh, trường, kỹ năng, edtech |
| `life` | đời sống, đô thị, văn hoá, du lịch, ẩm thực |
| `health` | y tế, sức khỏe, vacxin, dinh dưỡng |
| `soc` | chính sách, xã hội, chính trị, cộng đồng |
| `code` | lập trình, rust, svelte, backend, frontend |

If no keyword matches, use `tags` as topics if present; otherwise `topics = ARRAY['general']`.

---

## 5. Redis keys

| Key | Type | TTL | Writer | Purpose |
|---|---:|---:|---|---|
| `feed:{user_id}` | Redis list or JSON string | 600s | feed-service | Cached ordered post IDs and cursor metadata for the user. |
| `pref:{user_id}` | hash | 1800s | feature-store-worker | Hot topic weights; also read by recommendation-api. |
| `trending:24h` | sorted set | 300s | feature-store-worker | Post IDs scored by weighted interactions in the last 24h. |
| `post:meta:{post_id}` | hash | 300s | feed-service / recommendation-api | Cached author_id, topics, safety_score, counters, created_at. |

`feed:{user_id}` value format should be implementation-simple:

```json
{
  "generated_at": "2026-05-26T10:00:00Z",
  "source": "personalized|fallback",
  "items": ["post_uuid_1", "post_uuid_2"]
}
```

If using a Redis list instead, store only post IDs and keep `feed_meta:{user_id}` for source/generated_at. JSON string is preferred for Phase 2B simplicity.

---

## 6. Service endpoints

### 6.1 `feed-service` (:8005)

All `/api/v1/feed` endpoints require `oec_access` cookie auth. JWT validation happens in the service, not Envoy.

| Method | Path | Query | Response |
|---|---|---|---|
| GET | `/api/v1/feed` | `cursor?: string`, `limit?: 1..50` | `{ items: FeedPost[], next_cursor: string|null, source: "cache"|"personalized"|"fallback", generated_at }` |
| GET | `/health` | | `"ok"` |
| GET | `/metrics` | | Prometheus metrics |

`FeedPost` extends content-service `Post` with author metadata and rank metadata:

```json
{
  "id": "uuid",
  "author": { "id": "uuid", "username": "u", "display_name": "Name", "avatar_url": null },
  "content": "...",
  "media_urls": [],
  "tags": [],
  "topics": ["ai"],
  "safety_score": 1.0,
  "like_count": 12,
  "comment_count": 3,
  "save_count": 4,
  "share_count": 1,
  "view_count": 100,
  "created_at": "...",
  "rank": { "score": 0.82, "source": "topic", "reason": "Vì bạn quan tâm AI" }
}
```

Feed algorithm:
1. Validate auth and rate limit (`120/min/user`).
2. If `cursor` points into a valid `feed:{user_id}` cache, slice cached IDs and hydrate posts.
3. If no usable cache, call `POST {RECOMMENDATION_SERVICE_URL}/recommend/feed/{user_id}` with timeout 500ms.
4. On timeout/5xx/network error, assemble fallback from Redis `trending:24h`; if Redis empty, query recent published posts from Postgres.
5. Cache generated post IDs in `feed:{user_id}` TTL 600s.
6. Return `limit` items and opaque cursor. Cursor format is base64url JSON: `{ "offset": 20, "feed_generated_at": "..." }`.

### 6.2 `recommendation-api` (:8090, internal-only)

| Method | Path | Body/query | Response |
|---|---|---|---|
| POST | `/recommend/feed/{user_id}` | `{ "limit": 50, "candidate_pool": 300, "exclude_post_ids": [] }` | `{ "items": [{ "post_id", "score", "source", "reason" }], "features": { ... } }` |
| POST | `/recommend/features/rebuild` | `{ "user_id"?: uuid }` | `{ "rebuilt_users": n, "duration_ms": n }` |
| POST | `/recommend/evaluate` | `{ "sample_user_ids"?: [], "k": 10 }` | `{ "precision_at_k": n, "ctr_simulation": n, "diversity": n, "fallback_rate": n }` |
| GET | `/health` | | `{ "ok": true }` |

Ranking formula:

```text
score = w1·relevance(user_vec, post_topics)
      + w2·freshness_decay(created_at)
      + w3·safety_score
      - w4·(1 - diversity_boost)
```

Defaults:
- `w1=0.5`
- `w2=0.2`
- `w3=0.1`
- `w4=0.2`

Candidate sources:
- Follow retrieval: recent published posts from followed authors.
- Topic retrieval: recent posts whose `topics && top_user_topics`.
- Trending retrieval: `trending:24h` post IDs, then metadata hydration.
- Similarity retrieval: posts sharing at least one topic with recently liked/saved/shared posts. Phase 2B uses topic overlap, not embeddings.

Diversity rerank:
- Owned by recommendation-api.
- Penalize adjacent same-author and same-primary-topic items.
- Ensure the top 20 has at least 3 primary topics where possible.

### 6.3 `interaction-service` touchpoint

Add:

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/api/v1/interactions/me/batch` | `{ "post_ids": ["uuid", "..."] }` | `{ "items": { "post_id": { "liked": true, "saved": false, "shared": false, "hidden": false, "reported_pending": false } } }` |

Limit: `post_ids` length 1..100. Requires auth. Rate limit `200/min/user`.

### 6.4 `content-service` touchpoint

Add keyword topic inference to post create/update only when `topics` is empty. Existing API response should continue returning `topics`. No new content endpoint required.

---

## 7. Kafka consumer groups

| Consumer | Topic | Group ID | Offset policy |
|---|---|---|---|
| `feature-store-worker` | `oecophylla.interactions` | `oecophylla.feature-store.preferences.v1` | `earliest` on first boot, commit after batch write succeeds. |
| `cache-invalidator` | `oecophylla.interactions` | `oecophylla.feed.cache-invalidator.v1` | `latest` acceptable for dev, but use committed offsets; commit after Redis DEL. |

### 7.1 Event handling

Feature weights:

| Event | Topic vector impact |
|---|---:|
| `liked` | +1.5 |
| `saved` | +2.5 |
| `shared` | +2.5 |
| `hidden` | -2.0 |
| `reported` | -5.0 |
| `commented` | +1.0 |
| `comment_replied` | +0.7 |
| `unliked`, `unsaved`, `unshared` | negative inverse of original positive weight |

The worker must load post topics. Prefer `post:meta:{post_id}` from Redis, then Postgres fallback.

Trending score update:
- Increment `trending:24h` by positive weights for like/save/share/comment.
- Decrement for hide/report.
- TTL 300s.
- Phase 2B accepts approximate 24h window; Phase 4 can replace with bucketed time decay.

---

## 8. Frontend changes

### 8.1 `/` feed live

Replace mock-backed root feed with live `GET /api/v1/feed`.

Flow:
1. Initial SSR load fetches `/api/v1/feed?limit=20` through SvelteKit server.
2. Page renders initial `FeedPost[]`.
3. Client uses `IntersectionObserver` sentinel to request next cursor.
4. After every feed page load, call `POST /api/v1/interactions/me/batch` for loaded post IDs.
5. Post cards pass `me` state into `PostActionBar`.
6. If feed request fails but route can render stale data, show an inline retry row; do not blank the whole feed.

### 8.2 View tracking

IntersectionObserver marks a post viewed when:
- at least 50% visible,
- visible for at least 800ms,
- not already tracked in this session.

For Phase 2B, call existing `POST /api/v1/posts/{id}/view`. If later `view` becomes an `interaction_type`, this frontend logic can stay unchanged and the backend endpoint can emit the event.

### 8.3 Tailwind-first constraint

New feed UI should use inline Tailwind utility classes. Extract only repeated recipes (`glass-surface`, `glass-chip`, action buttons) when the exact pattern appears 3+ times. Do not add a large bespoke CSS file.

---

## 9. Rate limits & security

### 9.1 Feed-service rate limits

| Endpoint | Limit |
|---|---:|
| `GET /api/v1/feed` | 120/min/user |
| `/health`, `/metrics` | no auth, infra-only |

### 9.2 Interaction-service backfill

Mount the Phase 2A rate limits that were specified but not yet mounted:
- POST/DELETE like/save/share/hide: 120/min/user
- report: 10/min/user
- comments: 20/min/user
- comments/me reads and bulk `/me`: 200/min/user

### 9.3 Recommendation API auth

Internal-only. No Envoy route. Compose DNS only. Trust the compose network for Phase 2B; later production can add mTLS or signed internal JWT.

---

## 10. Observability & NFRs

### 10.1 Metrics

`feed-service`:
- `feed_requests_total{source}`
- `feed_recommendation_timeout_total`
- `feed_cache_hit_total`
- `feed_cache_miss_total`
- `feed_latency_ms`
- `feed_fallback_total`

`recommendation-api`:
- `recommendation_requests_total`
- `recommendation_latency_ms`
- `recommendation_candidate_count`
- `recommendation_diversity_score`

Workers:
- `feature_events_processed_total`
- `feature_batches_committed_total`
- `feature_batch_latency_ms`
- `cache_invalidations_total`
- `worker_kafka_errors_total`

### 10.2 Non-functional requirements

- **Fallback feed always available:** recommendation timeout, API down, Redis miss, or Python crash must still return recent published posts.
- **Feed p95 target:** local dev p95 under 250ms on cache hit, under 700ms on cache miss with recommendation-api healthy.
- **Recommendation timeout:** hard 500ms in feed-service.
- **Idempotent consumers:** replaying the same interaction batch should not explode preferences. Some additive drift is acceptable in dev, but rebuild endpoint must restore deterministic vectors from DB.

---

## 11. Testing & Definition of Done

### 11.1 Backend smoke tests

`feed-service` smoke:
1. Cache miss calls recommendation-api and returns personalized source.
2. Recommendation timeout returns fallback source under 700ms.
3. Second request with same user hits `feed:{user_id}` cache.
4. Cursor request returns non-overlapping next page.
5. Unauthenticated request returns 401 standard envelope.

`interaction-service` smoke:
1. `POST /api/v1/interactions/me/batch` returns correct booleans after like/save/report.
2. Length >100 returns 400.
3. Rate limit middleware is active.

`cache-invalidator` smoke:
1. Seed `feed:{user_id}`, publish/produce interaction event, worker deletes key.

### 11.2 Python tests

`recommendation-api`:
- Unit test ranking formula with fixed user vector/post topics.
- Unit test diversity rerank avoids repeated author/topic when alternatives exist.
- Endpoint test `/recommend/feed/{user_id}` with seeded DB.
- Endpoint test `/recommend/evaluate` returns all metric keys.

`feature-store-worker`:
- Unit test weight application from event payload.
- Integration test consumes a sample Kafka event inside compose network and upserts PG + Redis.
- Rebuild test recomputes vectors from `interactions`.

### 11.3 Frontend tests

- `svelte-check` clean.
- Vitest or component-level test for infinite-scroll fetch gating (no duplicate cursor request while loading).
- Manual browser verify: feed loads, action bar state hydrates, scrolling fetches next page, view endpoint fires once per visible post.

### 11.4 DoD

Phase 2B is done when:
1. `docker compose up -d --build` brings up `feed-service`, `recommendation-api`, `feature-store-worker`, and `cache-invalidator`.
2. Migration 9 applies idempotently.
3. Kafka consumer groups appear with committed offsets.
4. `GET /api/v1/feed` works via Envoy and returns live posts.
5. Recommendation outage still returns fallback feed.
6. `feed:{user_id}` cache hit rate is observable and second request hits cache.
7. Interacting with a post deletes `feed:{user_id}` through cache-invalidator.
8. Feature worker updates `user_preference_vectors` and `pref:{user_id}`.
9. Frontend `/` uses live feed and infinite scroll.
10. `cargo test --workspace`, Python tests, `pnpm run check`, and `pnpm run build` pass.

---

## 12. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Python service adds orchestration complexity. | Keep it internal-only, simple requirements, healthcheck, and robust feed fallback. |
| `topics` quality is weak before Phase 3 NLP. | Deterministic keyword fallback + seed backfill; spec calls it temporary. |
| Feature vectors drift from replay/additive updates. | `/recommend/features/rebuild` recomputes from DB interactions; worker commits after DB write. |
| Redis `trending:24h` is approximate. | Accept for Phase 2B; Phase 4 can implement bucketed time windows. |
| Feed cache invalidation only deletes interacting user's feed. | Good first-order behavior. Invalidation of followers/author audiences deferred until scale requires it. |
| Recommendation API lacks auth. | Internal-only and not routed by Envoy. Production hardening later. |
| Host macOS cannot resolve `kafka:9092`. | Smoke tests that need Kafka run inside compose network or via `docker exec`. |

---

## 13. Folder/file inventory

Expected new paths:

```text
backend/services/feed-service/
backend/services/cache-invalidator/
recommendation_api/
workers/feature_store_worker/
migrations/20260525000009_user_pref_vectors.sql
frontend/src/routes/+page.server.ts
frontend/src/routes/+page.svelte
frontend/src/lib/components/FeedList.svelte
frontend/src/lib/components/InfiniteSentinel.svelte
```

Expected modified paths:

```text
backend/Cargo.toml
backend/crates/common/src/middleware/rate_limit.rs
backend/services/interaction-service/src/*
backend/services/content-service/src/*
compose.yaml
compose.dev.yaml
envoy/envoy.yaml
infra/kafka/init-topics.sh
infra/prometheus/prometheus.yml
frontend/src/lib/api.ts
frontend/src/lib/types.ts
```

---

## 14. Decisions log

1. **One Phase 2B spec for all five components.** Keeps the feed system coherent and still executable in milestones.
2. **`feed-service` owns user-facing feed API; recommendation-api owns ranking.** Rust handles auth/cache/fallback; Python handles recommendation logic.
3. **Fallback feed always available.** This is a hard NFR; recent published posts are the last resort.
4. **Candidate pool default 300.** Matches original `CLAUDE.md` env.
5. **Diversity rerank in recommendation-api.** Keeps feed-service thin and avoids ranking logic duplication.
6. **Bulk `/me` in interaction-service.** Interaction state belongs with interactions; recommendation results should remain stateless.
7. **Micro-batch feature-store-worker.** 5s/100-event batches balance DB load and freshness.
8. **Keyword topic inference in content-service until Phase 3 NLP.** Ranking needs non-empty topics now.
9. **Internal trust for recommendation-api.** No Envoy route and no service JWT in Phase 2B.
10. **Cursor-based infinite scroll.** Offset is rejected because feed order can change and cache slices are easier with cursor metadata.
11. **Mount per-route rate limits now.** Phase 2A specified them; Phase 2B is the natural hardening point.
12. **Trixie runtime, Rust 1.85 builder, Python 3.13 Trixie.** Follows project memory.
