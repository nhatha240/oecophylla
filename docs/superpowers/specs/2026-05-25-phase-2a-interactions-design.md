# Oecophylla — Phase 2A: Interactions & Comments Design

**Status:** Draft, executed autonomously (user asleep)
**Date:** 2026-05-25
**Scope:** Phase 2A — `interaction-service` (Rust) + frontend like/save/share/hide/report buttons + comments thread (1-level reply) + `oecophylla.interactions` Kafka topic. Phase 2B (feed-service, recommendation-api Python, feature-store-worker, cache-invalidator, infinite-scroll feed) is the next sub-project.

---

## 1. Goals & non-goals

### 1.1 Goals
- Add a 4th Rust service `interaction-service` (:8004) to the existing workspace.
- Ship a `comments` table with 1-level reply (`parent_comment_id`) and a `reports` table (admin queue deferred to Phase 3).
- Extend `posts` with 4 denormalized counters (`like_count`, `comment_count`, `save_count`, `share_count`) maintained inside the same transaction as the interaction insert/delete.
- Emit a single `oecophylla.interactions` Kafka topic carrying 8 distinct event types (`liked`, `unliked`, `saved`, `unsaved`, `shared`, `unshared`, `hidden`, `reported`, `commented`, `comment_replied`).
- Wire `PostCard` and `/post/[id]` in the frontend to use the new endpoints — buttons reflect my interaction state, counters update on click.
- Smoke tests cover idempotent like, nested-reply rejection, duplicate-pending report.

### 1.2 Non-goals (deferred)
- Phase 2B: feed-service, recommendation-api, feature-store-worker, cache-invalidator, infinite-scroll feed, Redis feed cache.
- Phase 3: admin moderation queue UI, nlp-worker safety scoring, notifications.
- Comment editing, full nested threads, `@mentions`, comment reactions.
- `interactions` row of `type='view'` (Phase 2A only bumps `posts.view_count`; feature store in 2B will turn views into proper rows).

---

## 2. Architecture delta

```
                          frontend (:3000)
                                │
                                ▼
                          Envoy (:8080)
   /api/v1/auth/*                                     → auth-service    (:8001)
   /api/v1/users/*                                    → user-service    (:8002)
   /api/v1/posts/:id                                  → content-service (:8003)
   /api/v1/posts/:id/(like|save|share|hide|report     → interaction-svc (:8004) ★ NEW
                       |comments)
   /api/v1/posts/:id/me
   /api/v1/comments/*                                 → interaction-svc (:8004)
                                │
                                ▼
                       Kafka KRaft :9092
                       topic: oecophylla.interactions  ★ NEW
                       (no consumer in 2A)
        all 4 services ─read/write─►  Postgres 18 :5432
                       ─cache────►   Redis 7 :6379
```

### 2.1 Envoy reroute ordering
The new route prefixes (`/api/v1/posts/:id/like` etc.) **must** be evaluated before the broad `/api/v1/posts` content-service route. In Envoy's static config, list interaction routes first inside the virtual_host. Wildcard sub-path support uses Envoy `safe_regex` if simple prefix is insufficient; otherwise enumerate the 6 sub-paths explicitly:
- `prefix: /api/v1/posts/` is too greedy — would swallow `/api/v1/posts/:id` itself.
- Use `safe_regex: { regex: '^/api/v1/posts/[^/]+/(like|save|share|hide|report|comments(?:/.*)?|me)/?$' }` → interaction_cluster.
- Fall-through `prefix: /api/v1/posts` → content_cluster.

### 2.2 Cargo workspace addition
`backend/services/interaction-service/` mirrors the auth/user/content service layout: `Cargo.toml`, `Dockerfile`, `src/{main,state,handlers,repo,validation}.rs`, `tests/smoke.rs`. Reuses `crates/common`.

### 2.3 Compose addition
A new `interaction-service` block in `compose.yaml` (same shape as `user-service`). `compose.dev.yaml` exposes `8004:8004`.

---

## 3. Data model

Four new migrations on top of Phase 0+1. Numeric prefix continues the 2026-05-25 series.

### 3.1 `20260525000005_posts_counters.sql`
```sql
ALTER TABLE posts
    ADD COLUMN like_count    INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN comment_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN save_count    INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN share_count   INTEGER NOT NULL DEFAULT 0;

CREATE INDEX idx_posts_published_engagement ON posts
    ((like_count + comment_count * 2 + share_count) DESC, created_at DESC)
    WHERE status = 'published';
```

### 3.2 `20260525000006_interactions.sql`
```sql
CREATE TYPE interaction_type AS ENUM ('like', 'save', 'share', 'hide', 'report');

CREATE TABLE interactions (
    id           UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    post_id      UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    type         interaction_type NOT NULL,
    weight       REAL NOT NULL,
    metadata     JSONB NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_interactions_unique_single ON interactions (user_id, post_id, type);
CREATE INDEX        idx_interactions_post_type     ON interactions (post_id, type);
CREATE INDEX        idx_interactions_user_time     ON interactions (user_id, created_at DESC);
```

> `view` and `comment` are not in `interaction_type`. View → `posts.view_count` only (Phase 2A); comment → its own table (next migration).

### 3.3 `20260525000007_comments.sql`
```sql
CREATE TABLE comments (
    id                 UUID PRIMARY KEY DEFAULT uuidv7(),
    post_id            UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    author_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_comment_id  UUID REFERENCES comments(id) ON DELETE CASCADE,
    content            TEXT NOT NULL CHECK (length(content) BETWEEN 1 AND 2000),
    is_deleted         BOOLEAN NOT NULL DEFAULT false,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (parent_comment_id IS NULL OR parent_comment_id <> id)
);

CREATE INDEX idx_comments_post_created ON comments (post_id, created_at ASC) WHERE is_deleted = false;
CREATE INDEX idx_comments_parent       ON comments (parent_comment_id, created_at ASC)
                                       WHERE parent_comment_id IS NOT NULL AND is_deleted = false;
CREATE INDEX idx_comments_author       ON comments (author_id, created_at DESC);

CREATE TRIGGER trg_comments_updated_at BEFORE UPDATE ON comments
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

> 1-level threading is enforced in **application code**, not the DB. interaction-service rejects insert when the named parent already has `parent_comment_id IS NOT NULL`.

### 3.4 `20260525000008_reports.sql`
```sql
CREATE TYPE report_status AS ENUM ('pending', 'resolved_hidden', 'resolved_ok', 'resolved_warned');

CREATE TABLE reports (
    id           UUID PRIMARY KEY DEFAULT uuidv7(),
    reporter_id  UUID REFERENCES users(id) ON DELETE SET NULL,
    post_id      UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    reason       VARCHAR(50) NOT NULL,
    detail       TEXT,
    status       report_status NOT NULL DEFAULT 'pending',
    resolved_by  UUID REFERENCES users(id) ON DELETE SET NULL,
    resolved_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reports_post            ON reports (post_id);
CREATE INDEX idx_reports_pending_created ON reports (created_at DESC) WHERE status = 'pending';
CREATE UNIQUE INDEX idx_reports_one_pending_per_user_post
    ON reports (reporter_id, post_id) WHERE status = 'pending';
```

### 3.5 Interaction weights (per spec §ranking, used as defaults)

| type | weight |
|---|---|
| like | +1.5 |
| save | +2.5 |
| share | +2.5 |
| hide | -2.0 |
| report | -5.0 |

Configurable via env `INTERACTION_WEIGHT_<TYPE>` for Phase 2B tuning. Interaction-service uses these as the `weight` column value at INSERT time.

---

## 4. interaction-service endpoints

All endpoints require `oec_access` cookie auth unless noted.

### 4.1 Toggle interactions (single-shot)

| Method | Path | Notes |
|---|---|---|
| POST   | `/api/v1/posts/:id/like` | INSERT ON CONFLICT DO NOTHING; if inserted: `posts.like_count++`, emit `liked`. 201 on insert, 200 on duplicate. |
| DELETE | `/api/v1/posts/:id/like` | DELETE; if deleted: `posts.like_count--`, emit `unliked`. 204. |
| POST   | `/api/v1/posts/:id/save` | counter: `save_count`; events: `saved` / `unsaved` |
| DELETE | `/api/v1/posts/:id/save` |  |
| POST   | `/api/v1/posts/:id/share` | counter: `share_count`; events: `shared` / `unshared` |
| DELETE | `/api/v1/posts/:id/share` |  |
| POST   | `/api/v1/posts/:id/hide` | no counter; events: `hidden`. (No unhide event in 2A.) |
| DELETE | `/api/v1/posts/:id/hide` | DELETE only, no event. |

The insert and counter UPDATE happen in **one transaction**; the Kafka emit is fire-and-log after commit. If Kafka fails, the row stays — DB is the source of truth.

### 4.2 Reports

| Method | Path | Body |
|---|---|---|
| POST | `/api/v1/posts/:id/report` | `{ reason: "spam"\|"misinformation"\|"harassment"\|"nsfw"\|"other", detail?: string }` |

Same transaction inserts:
- a row in `reports` (status `pending`)
- a row in `interactions` (type `report`, weight `-5.0`, metadata: `{ "report_id": <uuid>, "reason": "..." }`)

UNIQUE partial index on `reports (reporter_id, post_id) WHERE status='pending'` → second pending report returns 409.

After commit, emit Kafka `reported`.

### 4.3 Comments

| Method | Path | Auth | Body / Query |
|---|---|---|---|
| GET   | `/api/v1/posts/:id/comments` | optional | `?limit=20&cursor=<comment_id>`. Returns top-level comments ASC by `created_at` with up to 5 inline replies each. Each comment payload: `{ id, author_id, author_username, author_display_name, content, is_deleted, created_at, replies: [...], has_more_replies: bool, reply_count: int }`. When `is_deleted=true` the `content` field is replaced with the placeholder `"[đã xóa]"`. |
| POST  | `/api/v1/posts/:id/comments` | required | `{ content, parent_comment_id? }`. Server validates `content` length 1..=2000, and if `parent_comment_id` is set, looks up the parent — if parent itself has `parent_comment_id IS NOT NULL`, returns 400 with `code: VALIDATION_FAILED`. Same transaction: INSERT comment, if top-level → `posts.comment_count++`. After commit, emit Kafka `commented` or `comment_replied`. |
| GET   | `/api/v1/comments/:id/replies` | optional | `?limit=20&cursor`. Returns replies under a top-level comment. |
| DELETE| `/api/v1/comments/:id` | owner or admin | Soft-delete (`is_deleted=true`). Same transaction: if top-level → `posts.comment_count--`. 204. No Kafka event. |

### 4.4 My interactions on a post

| Method | Path | Returns |
|---|---|---|
| GET | `/api/v1/posts/:id/me` | `{ liked, saved, shared, hidden, reported_pending }` (all booleans) |

Implementation: 1 SQL query against `interactions` + `reports`:
```sql
SELECT
  bool_or(type = 'like')   AS liked,
  bool_or(type = 'save')   AS saved,
  bool_or(type = 'share')  AS shared,
  bool_or(type = 'hide')   AS hidden,
  EXISTS (SELECT 1 FROM reports WHERE reporter_id=$1 AND post_id=$2 AND status='pending') AS reported_pending
FROM interactions WHERE user_id=$1 AND post_id=$2;
```

### 4.5 Rate limits

| Endpoint | Limit |
|---|---|
| POST/DELETE `/like|save|share|hide` | 120/min/user |
| POST `/report` | 10/min/user |
| POST `/comments` | 20/min/user |
| GET `/comments`, `/me` | 200/min/user |

Reuses the Redis sliding-window middleware from `crates/common`.

---

## 5. Kafka events

Single topic `oecophylla.interactions`. Envelope same as Phase 0+1 (`event_id`, `event_type`, `event_version=1`, `occurred_at`, `producer: "interaction-service"`, `data`). Kafka **key = post_id** so all interaction events for a given post serialize in order.

| `event_type` | `data` shape |
|---|---|
| `liked` / `unliked`     | `{ user_id, post_id, post_author_id, weight }` |
| `saved` / `unsaved`     | same |
| `shared` / `unshared`   | same |
| `hidden`                | same (no unhidden event) |
| `reported`              | `{ reporter_id, post_id, post_author_id, reason, report_id }` |
| `commented`             | `{ commenter_id, post_id, post_author_id, comment_id, content_preview }` (preview = first 200 chars of content) |
| `comment_replied`       | `{ commenter_id, post_id, post_author_id, comment_id, parent_comment_id, content_preview }` |

`post_author_id` is denormalized into the event so downstream Phase-2B consumers don't need to JOIN. interaction-service loads it via `SELECT author_id FROM posts WHERE id=$1` (one extra read; cached in Redis `post:author:{id}` with 5-min TTL to save round trips on hot posts).

---

## 6. Frontend changes

### 6.1 New types in `frontend/src/lib/types.ts`
```ts
export type ReportReason = 'spam' | 'misinformation' | 'harassment' | 'nsfw' | 'other';

export interface Comment {
  id: string;
  post_id: string;
  author_id: string;
  author_username: string;
  author_display_name: string | null;
  parent_comment_id: string | null;
  content: string;
  is_deleted: boolean;
  created_at: string;
  replies?: Comment[];
  reply_count?: number;
  has_more_replies?: boolean;
}

export interface MyInteractions {
  liked: boolean;
  saved: boolean;
  shared: boolean;
  hidden: boolean;
  reported_pending: boolean;
}

// Extend Post (counter fields):
export interface Post {
  // ... existing fields
  like_count: number;
  comment_count: number;
  save_count: number;
  share_count: number;
}
```

### 6.2 New components

| Component | Purpose |
|---|---|
| `PostActionBar.svelte` | Renders the row of action buttons (heart/bookmark/share/comment) + counters under a PostCard. Receives `post: Post`, `me: MyInteractions \| null`. Emits events via callbacks. |
| `CommentItem.svelte` | Renders one comment with author chip + timestamp + content (or "[đã xóa]"). Recursively renders `replies` (max 1 level). |
| `CommentForm.svelte` | Textarea + submit button. Receives `parent_comment_id?: string`. On success refreshes the parent list. |
| `ReportDialog.svelte` | Modal with 5 reason radios + free-text detail. Submits to `POST /posts/:id/report`. |

### 6.3 Component changes

- **`PostCard.svelte`** — embed `<PostActionBar post={post} me={me} />`. Add `me?: MyInteractions` prop (optional — undefined for mock or anonymous).
- **`frontend/src/routes/post/[id]/+page.server.ts`** — also fetch `/posts/:id/me` (catch and degrade to `null` if 401) and `/posts/:id/comments?limit=20`. Returns `{ post, me, comments }`.
- **`frontend/src/routes/post/[id]/+page.svelte`** — renders the PostCard with `me`, then `<CommentForm post_id={post.id} />`, then a `{#each comments as c}<CommentItem {c} />{/each}` list.
- **`frontend/src/lib/mock/feed.ts`** — add the 4 counter fields with mocked values so the action bar shows non-zero numbers.

### 6.4 Interaction handlers (client-side)

In `PostActionBar.svelte`, button clicks call `apiFetch(fetch, '/posts/:id/like', { method: 'POST' })` and optimistically update local state. If the call fails (e.g. 401), roll back the optimistic change and show a toast. (Toast component is a tiny new file — `Toast.svelte` + a `toastStore` — used sparingly.)

For Phase 2A, just optimistic UI without rollback animation; on failure, replace with an alert(). Toast component can be deferred if needed — keep YAGNI.

### 6.5 Comments page UX
- Top-level comments: list ascending by time.
- Each comment shows up to 5 replies inline. "Xem thêm phản hồi…" link if `has_more_replies`. Click → loads via `GET /comments/:id/replies`.
- Reply form appears under a comment when user clicks "Phản hồi". On submit, refreshes the parent's replies inline.
- Author may delete own comments via a "Xóa" link (only owner sees it). Soft delete; displays `"[đã xóa]"` in place.

---

## 7. content-service touchpoint

`content-service::repo::PostRow` adds the 4 counter columns + 4 SELECT lines in every `posts` query. No new endpoints, no new logic. interaction-service writes the columns; content-service reads them. **interaction-service and content-service both touch `posts` — that is acceptable because the writes are restricted to counter columns and post_id-keyed `UPDATE … SET col = col ± 1`, which the DB serializes cleanly per row.** No cross-service HTTP calls.

---

## 8. Testing & DoD

### 8.1 Smoke tests in `backend/services/interaction-service/tests/smoke.rs`

1. **like idempotent + decrement** — register user, create post via content-service, POST like → 201 + counter=1, POST like again → 200 + counter still 1, DELETE like → 204 + counter=0; verify Kafka `liked` then `unliked` events.
2. **save/share single-shot** — same shape as like, abbreviated.
3. **hide does not bump like_count** — POST hide → 201 but post.like_count=0.
4. **report duplicate pending → 409** — POST report once OK, POST again with same reason → 409.
5. **comment + 1-level reply + reject nested** — POST top-level → comment_count=1, POST reply under it → comment_count still 1 (reply doesn't count), POST nested reply under the reply → 400 `VALIDATION_FAILED`.
6. **`/me` reflects state** — after liking + saving + reporting, GET `/me` returns `{ liked:true, saved:true, shared:false, hidden:false, reported_pending:true }`.
7. **soft delete comment** — owner DELETE → 204, GET comments → content shows `"[đã xóa]"`.

Tests run inside the compose network per memory `project-kafka-listener-host`.

### 8.2 Frontend tests
- `vitest`: add 2 unit tests for `PostActionBar` optimistic update logic (mock fetch returns 201 vs 401).
- `svelte-check`: 0 errors.

### 8.3 Manual verify (Phase 2A DoD)

1. `make up` from existing Phase 0+1 healthy state — interaction-service joins the healthy set.
2. Migration runs idempotently; second `docker compose up migrate` is a no-op.
3. Smoke test exit code 0.
4. From browser: open seeded post detail, click ♥ → counter updates → reload → still liked. Add a comment → it appears at the bottom. Reply to comment → reply renders nested. Try to reply to the reply → frontend shows error (no nesting allowed). Report post → after submit dialog closes; second report returns "đã có báo cáo đang xử lý".
5. `docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh --topic oecophylla.interactions --from-beginning --max-messages 1` shows JSON envelope.
6. Counters in DB consistent: `SELECT like_count FROM posts WHERE id=...` matches `(SELECT count(*) FROM interactions WHERE post_id=... AND type='like')`.
7. `cargo clippy -D warnings` + `pnpm exec svelte-check` clean.

---

## 9. Risks & open items

| Risk | Mitigation |
|---|---|
| Counter drift if a future migration or admin tool deletes interactions out-of-band. | Phase 2B feature-store-worker will recompute counters from `interactions` periodically. For 2A, only interaction-service touches the columns. |
| Envoy route regex performance. | Single static regex with 6 alternatives — Envoy handles this efficiently; no perceptible overhead for the small expected RPS. |
| Soft-deleted comment "[đã xóa]" string is hard-coded in the API; admin moderation in Phase 3 may want a different placeholder. | Behind a config `COMMENT_DELETED_PLACEHOLDER` env, default `"[đã xóa]"`. |
| Like + simultaneous unlike race. | `INSERT ON CONFLICT DO NOTHING` + `UPDATE … SET col = col + (rows_affected)` in same TX — naturally atomic. The DELETE path uses `DELETE … RETURNING 1` and decrements only if a row was deleted. |
| `parent_comment_id` lookup adds latency to comment POST. | One extra read with `RETURNING parent_comment_id` collapsing into one query: `INSERT INTO comments ... WHERE NOT EXISTS (SELECT 1 FROM comments p WHERE p.id = parent_comment_id AND p.parent_comment_id IS NOT NULL) RETURNING id`. If 0 rows returned, return 400. |

---

## 10. Decisions log

1. **`comments` is its own table**, not a row in `interactions`. Allows edit/delete + threading.
2. **1-level threading via `parent_comment_id`**. App-enforced (not DB CHECK).
3. **POST/DELETE pairs** for like/save/share/hide (REST), idempotent.
4. **`view_count` only** for views in 2A — deferred row insert to 2B.
5. **`reports` table + endpoint** ship in 2A; admin queue in Phase 3.
6. **Service ownership**: interaction-service owns `/posts/:id/(like|save|share|hide|report|comments|me)` + `/comments/*`. Envoy uses `safe_regex` to route before the broad `/posts` prefix.
7. **Denormalized counters** on `posts` (4 columns), updated by interaction-service in the same TX.
8. **Single Kafka topic** `oecophylla.interactions` with multi-shape `data` per `event_type`. Key = `post_id`.
9. **`post_author_id` denormalized** into every interaction event payload (one extra read per produce, cached in Redis).
10. **Soft-delete comments** with `is_deleted=true`; "[đã xóa]" string returned in API.
