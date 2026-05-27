# Oecophylla — Phase 3: Moderation, Notifications & NLP Topic Worker Design

**Status:** Draft, ready for implementation planning
**Date:** 2026-05-26
**Scope:** Phase 3 — admin moderation service + audit log, user notification service (REST + SSE), and a dedicated keyword-based NLP worker that consumes `content.created` and enriches `posts.topics`. Builds on tags `phase-0-1-complete`, `phase-2a-complete`, and `phase-2b-complete`.

---

## 1. Goals & non-goals

### 1.1 Goals
- Add `moderation-service` (Rust, :8006) with admin-only endpoints to triage the report queue produced by Phase 2A and to record every admin action in a new `audit_logs` table.
- Add `notification-service` (Rust, :8007) that owns a `notifications` table, exposes REST list/read endpoints, and pushes new notifications to logged-in clients over Server-Sent Events.
- Add `nlp-worker` (Python) that consumes `oecophylla.content.created`, expands the inline keyword inference that Phase 2B Task 5 added to `content-service`, supports Vietnamese + English keyword maps, and updates `posts.topics` asynchronously.
- Wire the SvelteKit frontend: a real admin moderation queue (`/admin`), an in-app notification bell with unread count + dropdown + live updates, and remove the inline topic inference from the post-creation hot path.
- Preserve all locked decisions: Envoy gateway, JWT in cookies, Kafka KRaft, Postgres 18 `uuidv7()`, Trixie runtime, Tailwind-first frontend, Rust 1.85 toolchain.

### 1.2 Non-goals
- No automated content takedown. Moderation is **manual review only**; NLP outputs are advisory metadata only and never gate publication.
- No `posts.safety_score` column, no toxicity model, no `content.flagged` topic, no `moderation-worker` proactive scan. (The original design contemplated these; the Phase 3 brainstorm explicitly defers them.)
- No semantic embedding store, no language-model classification, no multilingual translation pipeline. NLP stays keyword-based.
- No push notifications to mobile/web-push. Only in-app via REST + SSE. Email/web-push is Phase 4+.
- No multi-replica notification-service. SSE state is in-process; Phase 3 ships single-replica with that documented limitation.
- No mention parser (`@username`) yet. Notifications fire on like/comment/follow/admin-action only.
- No content-flagging from external partners or trusted reporters. Reports flow only from the existing Phase 2A user `POST /posts/:id/report` endpoint.

---

## 2. Brainstorm decisions

| Question | Decision |
|---|---|
| Phase split | One Phase 3 covering all three components together. Notifications depend on moderation events ("your post was removed") and on NLP-derived topics for digest-style notifications later; shipping together avoids two awkward partial states. |
| Notification delivery | **SSE + REST**. Single direction (server→client), Envoy passes `text/event-stream` through with `stream_idle_timeout: 0s` on that route. Frontend uses `EventSource` with `withCredentials`. REST endpoints handle list + mark-read so SSE only carries the live push. |
| NLP scope | **Keyword-based topic tagging only**. Expand Phase 2B Task 5's inline list, add a Vietnamese keyword map, and move execution out of the request path into an async worker. No safety score, no language model, no embedding. |
| Moderation policy | **Manual review only**. Admin sees the queue, picks an action (`dismiss` / `hide_post` / `warn_author` / `ban_author`), and the service applies it transactionally + emits an event. NLP never auto-hides. |

---

## 3. Architecture & topology delta

```
Browser
  │
  ├─ EventSource: /api/v1/notifications/stream  (text/event-stream, cookies)
  ▼
SvelteKit frontend (:3000)
  │  fetch /api/v1/notifications, /admin/reports, /admin/audit-logs
  ▼
Envoy (:8080)
  ├─ /api/v1/notifications/*  → notification-service (:8007)
  ├─ /api/v1/admin/*          → moderation-service   (:8006)   (admin role required)
  └─ (existing routes from phases 0/1/2A/2B)

Kafka oecophylla.*
  ├─ interactions          → notification-service (existing consumer group new)
  ├─ user.followed         → notification-service
  ├─ content.created       → nlp-worker (new consumer group)
  └─ moderation.action     → notification-service (new topic, produced by moderation-service)
```

### 3.1 Component responsibilities

| Service | Owns | Reads | Writes |
|---|---|---|---|
| moderation-service (:8006) | `audit_logs` table; report state transitions | `reports`, `posts`, `users` | `audit_logs`, `reports.status`, `posts.status` when hiding, Kafka `oecophylla.moderation.action` |
| notification-service (:8007) | `notifications` table; in-memory SSE fan-out map | `notifications`, `users`, `posts` (for snippet hydration) | `notifications`, Redis `notif:unread_count:{user_id}` |
| nlp-worker (Python) | nothing; pure consumer | `posts.id`, `posts.content`, `posts.topics` | `posts.topics` |

### 3.2 Single-replica constraint (notification-service)

`notification-service` stores active SSE channels in a `tokio::sync::Mutex<HashMap<UserId, Vec<broadcast::Sender>>>`. With more than one replica, a notification produced for user `U` only reaches whichever replica `U` happens to be connected to. Phase 3 ships `deploy.replicas: 1` in compose. The README and `claude.md` Phase 3 closeout note both document the limitation. Phase 4 moves fan-out to Redis pub/sub for horizontal scale.

---

## 4. Data model delta

### 4.1 Migration 10: `20260526000010_audit_logs.sql`

```sql
CREATE TYPE audit_action AS ENUM (
    'report_dismissed',
    'post_hidden',
    'post_unhidden',
    'author_warned',
    'author_banned',
    'author_unbanned'
);

CREATE TABLE audit_logs (
    id          UUID PRIMARY KEY DEFAULT uuidv7(),
    actor_id    UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    action      audit_action NOT NULL,
    target_type TEXT NOT NULL,                    -- 'post' | 'user' | 'report'
    target_id   UUID NOT NULL,
    report_id   UUID REFERENCES reports(id) ON DELETE SET NULL,
    note        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_logs_actor_created ON audit_logs (actor_id, created_at DESC);
CREATE INDEX idx_audit_logs_target        ON audit_logs (target_type, target_id);
CREATE INDEX idx_audit_logs_report        ON audit_logs (report_id);
```

`actor_id` must be a user with `role = 'admin'`; enforced in service layer, not DB (admin role can be revoked but logs stay).

### 4.2 Migration 11: `20260526000011_notifications.sql`

```sql
CREATE TYPE notification_kind AS ENUM (
    'liked',                -- someone liked your post
    'commented',            -- someone commented on your post
    'replied',              -- someone replied to your comment
    'followed',             -- someone followed you
    'post_hidden',          -- moderation: your post was hidden
    'author_warned',        -- moderation: you were warned
    'author_banned'         -- moderation: you were banned
);

CREATE TABLE notifications (
    id           UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind         notification_kind NOT NULL,
    actor_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    post_id      UUID REFERENCES posts(id) ON DELETE CASCADE,
    comment_id   UUID REFERENCES comments(id) ON DELETE CASCADE,
    payload      JSONB NOT NULL DEFAULT '{}'::jsonb,
    read_at      TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_notifications_user_created       ON notifications (user_id, created_at DESC);
CREATE INDEX idx_notifications_user_unread_created
    ON notifications (user_id, created_at DESC) WHERE read_at IS NULL;
```

Multi-column unread index lets `unread_only=true` queries skip the read rows entirely.

### 4.3 Posts table: no schema change

`posts.topics TEXT[]` already exists from Phase 0+1 and is currently written by `content-service` in the inline keyword path. Phase 3 keeps the column shape, removes the inline write, and lets `nlp-worker` overwrite it after the post is created.

Trade-off: there is a brief window (≤ a few seconds) where a fresh post has empty `topics`. Acceptable for feed personalization because the fallback ladder treats empty topics as "trending" candidates.

### 4.4 Reports table: status enum already sufficient

Phase 2A migration 8 already ships `report_status` with `pending`, `resolved_hidden`, `resolved_ok`, `resolved_warned`. Phase 3 transitions:

| Admin action | New `report.status` | New `post.status` | New `audit_logs.action` |
|---|---|---|---|
| Dismiss | `resolved_ok` | unchanged | `report_dismissed` |
| Hide post | `resolved_hidden` | `hidden` | `post_hidden` |
| Warn author | `resolved_warned` | unchanged | `author_warned` |
| Ban author | `resolved_warned` | unchanged (post stays) | `author_banned` (+ `users.is_active = false`) |

Banning sets `users.is_active = false` (column already present from Phase 0+1 user table). `auth-service` already gates login on `is_active`.

---

## 5. Redis keys

| Key | Purpose | TTL |
|---|---|---|
| `notif:unread_count:{user_id}` | Cached unread count; recomputed on miss; invalidated on insert + mark-read | 30 min |

That is the only new Redis key. SSE channels are in-process, not in Redis.

---

## 6. Service endpoints

### 6.1 `moderation-service` (:8006)

All routes require `oec_access` cookie with `role = admin` claim. The shared `crates/common::auth` middleware already extracts `AuthUser { id, role }`; Phase 3 adds a small `require_admin` extractor that 403s otherwise.

```
GET    /admin/reports?status=pending&cursor=&limit=20
GET    /admin/reports/:id
POST   /admin/reports/:id/resolve
       body: { action: "dismiss" | "hide_post" | "warn_author" | "ban_author", note?: string }
GET    /admin/audit-logs?actor_id=&action=&cursor=&limit=20
GET    /admin/users/:id/history          (recent reports + audit entries)
GET    /health
GET    /metrics
```

`POST /admin/reports/:id/resolve` runs the state transition + `audit_logs` insert + Kafka publish inside one Postgres transaction so an admin click is atomic with respect to its audit trail. Kafka publish happens after commit; if Kafka fails, the action still stands and an error counter increments.

Cursor format: opaque base64 of `(created_at, id)` for stable ordering. Same pattern as feed-service.

### 6.2 `notification-service` (:8007)

```
GET    /api/v1/notifications?cursor=&limit=20&unread_only=false
POST   /api/v1/notifications/:id/read
POST   /api/v1/notifications/read-all
GET    /api/v1/notifications/unread-count       (cached via Redis)
GET    /api/v1/notifications/stream             (text/event-stream)
GET    /health
GET    /metrics
```

All require auth. Frontend opens one `EventSource('/api/v1/notifications/stream', { withCredentials: true })` per tab. Stream sends:

- `event: notification`, `data: <NotificationDto JSON>` whenever a new row is inserted for that user.
- `event: heartbeat`, `data: {}` every 25s. Envoy `idle_timeout` per route bumped to 60s; the heartbeat keeps connections through any intervening proxy alive.
- `event: bye`, `data: {}` and graceful close on server shutdown.

Connection lifecycle: on connect, the handler authenticates, creates a `broadcast::channel`, registers it in the in-memory map keyed by user id, awaits cancellation. On disconnect, the channel is removed.

### 6.3 Envoy route changes

```
- /api/v1/notifications/stream  →  notification-service (idle_timeout 60s, no buffering)
- /api/v1/notifications/*       →  notification-service
- /admin/*                      →  moderation-service
```

Order matters: stream route is listed **before** the generic `/api/v1/notifications/` prefix.

### 6.4 `nlp-worker` (Python)

Pure Kafka consumer. No HTTP surface.

- Group: `oecophylla.nlp.v1`
- Topic: `oecophylla.content.created`
- Micro-batch: 5 seconds or 50 events, whichever first
- For each event: load post by id; if `topics` is non-empty leave it alone (admin/seed override); otherwise compute new topic list via the expanded keyword map (en + vi); UPDATE `posts.topics`.
- Idempotent: re-processing the same event is a no-op when topics are already set.
- Skips malformed payloads with a log line; does not crash the worker.

### 6.5 Keyword map

```python
TOPIC_KEYWORDS_EN = {
    "ai":    {"ai", "artificial intelligence", "machine learning", "llm", "gpt", "neural"},
    "tech":  {"tech", "technology", "software", "developer", "coding", "programming"},
    "music": {"music", "song", "album", "concert", "playlist"},
    "food":  {"food", "recipe", "restaurant", "cooking", "cuisine"},
    "sport": {"sport", "football", "soccer", "basketball", "tennis", "match"},
    "travel": {"travel", "trip", "flight", "hotel", "vacation"},
    "news":  {"news", "breaking", "headline", "politics"},
}

TOPIC_KEYWORDS_VI = {
    "ai":    {"trí tuệ nhân tạo", "học máy", "mô hình ngôn ngữ"},
    "tech":  {"công nghệ", "lập trình", "phần mềm", "kỹ sư"},
    "music": {"âm nhạc", "ca khúc", "album", "concert", "bài hát"},
    "food":  {"ẩm thực", "công thức", "nhà hàng", "nấu ăn"},
    "sport": {"bóng đá", "bóng rổ", "thể thao", "trận đấu"},
    "travel": {"du lịch", "khách sạn", "vé máy bay", "kỳ nghỉ"},
    "news":  {"tin tức", "thời sự", "chính trị"},
}
```

Matching is case-insensitive substring after NFKC normalization. Inference returns the union of matched topic keys across both maps. If empty, falls back to `["general"]`.

---

## 7. Kafka topics & consumer groups

### 7.1 New topic

| Topic | Partitions | Retention | Producer | Consumers |
|---|---|---|---|---|
| `oecophylla.moderation.action` | 1 | 7 days | moderation-service | notification-service |

Event schema:

```json
{
  "event_id": "<uuidv7>",
  "event_type": "report_dismissed | post_hidden | author_warned | author_banned",
  "event_version": 1,
  "occurred_at": "<rfc3339>",
  "producer": "moderation-service",
  "data": {
    "actor_id": "<uuid>",
    "target_user_id": "<uuid>",
    "target_post_id": "<uuid|null>",
    "report_id": "<uuid|null>",
    "note": "string|null"
  }
}
```

### 7.2 Consumer groups added

| Consumer group | Topic(s) | Service |
|---|---|---|
| `oecophylla.notification.v1` | `oecophylla.interactions`, `oecophylla.user.followed`, `oecophylla.moderation.action` | notification-service |
| `oecophylla.nlp.v1` | `oecophylla.content.created` | nlp-worker |

### 7.3 Event → notification mapping

| Topic | Event type | Notification kind | `user_id` (recipient) | Skip when |
|---|---|---|---|---|
| `oecophylla.interactions` | `liked` | `liked` | `post_author_id` | `user_id == post_author_id` (self-like) |
| `oecophylla.interactions` | `commented` (post-author target) | `commented` | `post_author_id` | self |
| `oecophylla.interactions` | `commented` (reply parent target) | `replied` | parent comment author | self |
| `oecophylla.user.followed` | `followed` | `followed` | `followee_id` | n/a |
| `oecophylla.interactions` | `hidden`, `saved`, `viewed`, `reported` | — | skipped | always |
| `oecophylla.moderation.action` | `post_hidden` | `post_hidden` | `target_user_id` | n/a |
| `oecophylla.moderation.action` | `author_warned` | `author_warned` | `target_user_id` | n/a |
| `oecophylla.moderation.action` | `author_banned` | `author_banned` | `target_user_id` | n/a |
| `oecophylla.moderation.action` | `report_dismissed` | — | skipped | always |

Insert + SSE push happen in one Tokio task per event. SSE push is best-effort; a failure to push does not block the insert.

---

## 8. Frontend changes

### 8.1 Notification bell

A new top-bar component `NotificationBell.svelte`:

- Reads from a Svelte store `notifications` populated by:
  1. On mount: `GET /api/v1/notifications?limit=20` + `GET /api/v1/notifications/unread-count`.
  2. SSE: subscribe to `/api/v1/notifications/stream`; on `event: notification`, prepend the row and bump unread count.
- Renders a bell icon with a numeric badge.
- Click opens a dropdown with the latest 20 notifications + a "Mark all as read" button.

### 8.2 `/admin` real moderation queue

Replaces the existing mock at `frontend/src/routes/admin/+page.svelte`. Two tabs: **Reports** and **Audit**.

- **Reports tab**: paginated list of `pending` reports with post snippet, reporter, time, reason. Each row has buttons `Dismiss`, `Hide post`, `Warn`, `Ban`. Clicking calls `POST /admin/reports/:id/resolve` and refreshes.
- **Audit tab**: paginated list of audit entries with admin, action, target, note, timestamp.
- Page guard: SSR load checks `data.user?.role === 'admin'`; otherwise 403.

### 8.3 Content service hot path

`content-service` POST/PUT post handler no longer infers topics. The Phase 2B Task 5 helper is removed; the unit test for it moves into `nlp-worker`. The integration smoke that asserted `topics @> ARRAY['ai']` is updated to wait up to 5s for the worker to update the row.

### 8.4 Tailwind-first

No new global CSS class is introduced. Notification dropdown reuses `.glass-surface` from Phase 2B. Admin tables use plain Tailwind utilities.

---

## 9. Auth, RBAC & security

- `crates/common::auth::AuthUser` already exposes `role: UserRole`. Add `crates/common::auth::require_admin` extractor that returns 403 if role ≠ Admin.
- All `/admin/*` routes use `require_admin`.
- All `/api/v1/notifications/*` routes including SSE use the existing `AuthUser` extractor.
- SSE cookie auth: `EventSource` sends cookies when `withCredentials: true`; Envoy forwards `oec_access`. No bearer token needed.
- CSRF: the only mutating notification endpoints are `POST :id/read` and `POST read-all`; both same-origin, cookies `SameSite=Lax`, no JSON body. Acceptable.
- Rate limit: per-user `5 req/s` on `/api/v1/notifications/*` (excluding stream), reusing the bucketed middleware Phase 2B Task 6 introduced. Stream endpoint exempt.

---

## 10. Observability & NFRs

### 10.1 Metrics (Prometheus)

| Metric | Type | Labels | Source |
|---|---|---|---|
| `moderation_actions_total` | counter | `action` | moderation-service |
| `moderation_actions_kafka_failures_total` | counter | — | moderation-service |
| `notifications_inserted_total` | counter | `kind` | notification-service |
| `notifications_sse_clients` | gauge | — | notification-service |
| `notifications_sse_push_failures_total` | counter | `reason` | notification-service |
| `nlp_events_processed_total` | counter | `result` (`updated`/`skipped`/`error`) | nlp-worker |
| `nlp_batch_size` | histogram | — | nlp-worker |

### 10.2 Non-functional requirements

| Concern | Target |
|---|---|
| Notification insert → SSE push latency | p95 < 250 ms in single-host compose |
| Admin action latency | p95 < 200 ms |
| NLP worker batch processing | p95 < 2 s per 50-event batch |
| Notification list query | p95 < 100 ms for `limit=20` |
| Memory: SSE map per 1k users | < 5 MB |

---

## 11. Testing & Definition of Done

- 9 + **2 new** migrations apply cleanly on a fresh database.
- `cargo test --workspace --no-fail-fast` green, including new smoke tests:
  - moderation-service: admin auth gate, dismiss, hide-post + audit row, ban + user inactive + Kafka event.
  - notification-service: insert from interactions/follow/moderation, unread-count cache, mark-read, SSE handshake.
- `make test-python` green; `nlp-worker` has a unit test asserting English + Vietnamese keyword inference plus an idempotency test.
- `pnpm run check && pnpm run build` green; new `NotificationBell` + `/admin` page compile.
- `scripts/smoke_phase3.sh` walks: register → admin login → user reports another user's post → admin resolves with `hide_post` → reporter & author both see notification → audit row visible.
- Manual checks:
  - Bell badge updates live when another tab/user likes your post.
  - SSE auto-reconnects after `docker compose restart notification-service`.
  - Hiding a post removes it from feed within one cache TTL (or immediately after manual cache flush).
  - Banning a user blocks their next login attempt.
- Tag: `git tag phase-3-complete` only after all DoD items pass.

---

## 12. Open questions for later phases

- Mention parser (`@username`) and notification kind `mentioned`.
- Trusted reporter program (auto-priority for some report sources).
- Multi-replica notification-service via Redis pub/sub fan-out.
- Email + web-push delivery.
- Toxicity / safety scoring with a real model + auto-action thresholds.
- Notification preferences (per-kind mute) and quiet hours.
