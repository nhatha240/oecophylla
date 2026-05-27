# Phase 3: Moderation, Notifications & NLP Topic Worker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Phase 3 of Oecophylla: Rust `moderation-service`, Rust `notification-service` (REST + SSE), Python `nlp-worker`, an `/admin` moderation queue in SvelteKit, a notification bell with live updates, an `audit_logs` table, and a `notifications` table.

**Architecture:** `moderation-service` is admin-only, transitions reports + writes audit rows + publishes `oecophylla.moderation.action`. `notification-service` consumes interactions/follow/moderation, inserts into `notifications`, and pushes live updates to in-process SSE channels keyed by `user_id`. `nlp-worker` takes the keyword inference logic that lives inline in `content-service` today (Phase 2B Task 5), moves it into an async consumer of `oecophylla.content.created`, and supports both English and Vietnamese keyword maps.

**Tech Stack:** Rust 1.85, Axum, SQLx, deadpool-redis, rdkafka, Python 3.13, aiokafka, asyncpg, redis-py, Postgres 18, Redis, Kafka KRaft, Envoy, Prometheus, SvelteKit, Tailwind.

---

**Companion spec:** `docs/superpowers/specs/2026-05-26-phase-3-moderation-notifications-nlp-design.md`.

**Working directory:** `/Users/nhathaminh/oecophylla`.

**Baseline:** repo on `main`, expected tags `phase-0-1-complete`, `phase-2a-complete`, `phase-2b-complete`.

**Key decisions from spec:**
- One bundled Phase 3 across all three concerns.
- SSE + REST for notification delivery; no WebSocket.
- NLP is keyword-only (English + Vietnamese), no model.
- Moderation is manual review only; NLP never auto-hides.
- `notification-service` is single-replica; SSE state is in-process.

---

## Execution protocol

- Execute tasks in order unless the controller explicitly splits a task into smaller subtasks before dispatch.
- Use a fresh implementation subagent per task.
- After each task, run spec-compliance review first and code-quality review second.
- Do not dispatch multiple implementation subagents in parallel because the repo has shared workspace, compose, frontend, and Cargo files.
- Do not edit unrelated dirty files. Current dirty paths include `claude.md`, `frontend/src/routes/+layout.svelte`, and `frontend/src/lib/apple-glass/` unless a task explicitly names them.
- Every implementation task must end with a focused verification command and a commit unless verification is blocked by missing services or dependency downloads. If blocked, record the exact command and error in the task handoff.
- Test-only environment overrides (e.g., a low rate-limit threshold) must be off by default in compose and enabled only by the smoke that needs them.
- The user has indicated **they will commit the changes themselves** during Phase 3; subagent commits should be small, focused, and clearly labelled so the user can review and squash.

---

## File structure map

```
backend/
├── crates/common/
│   ├── auth.rs                       # add require_admin extractor
│   └── events.rs                     # add ModerationActionEvent type + helpers
└── services/
    ├── moderation-service/
    │   ├── Cargo.toml
    │   ├── Dockerfile
    │   ├── src/
    │   │   ├── main.rs
    │   │   ├── state.rs
    │   │   ├── config.rs
    │   │   ├── repo.rs
    │   │   ├── handler.rs
    │   │   ├── kafka.rs
    │   │   └── audit.rs
    │   └── tests/smoke.rs
    └── notification-service/
        ├── Cargo.toml
        ├── Dockerfile
        ├── src/
        │   ├── main.rs
        │   ├── state.rs
        │   ├── config.rs
        │   ├── repo.rs
        │   ├── handler.rs
        │   ├── kafka.rs
        │   ├── sse.rs
        │   └── fanout.rs
        └── tests/smoke.rs

workers/nlp_worker/
├── Dockerfile
├── pytest.ini
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── keywords.py
│   ├── infer.py
│   ├── kafka_consumer.py
│   └── repo.py
└── tests/
    ├── test_keywords.py
    └── test_infer_idempotent.py

migrations/
├── 20260526000010_audit_logs.sql
└── 20260526000011_notifications.sql

frontend/src/
├── lib/
│   ├── components/
│   │   ├── NotificationBell.svelte
│   │   ├── NotificationItem.svelte
│   │   └── AdminReportsTable.svelte
│   ├── stores/notifications.ts
│   └── api/notifications.ts
└── routes/
    ├── admin/+page.svelte           # replace existing mock with real UI
    └── admin/+page.server.ts        # SSR guard: role === admin

envoy/envoy.yaml                      # add admin + notifications + SSE routes
compose.yaml                          # add 3 new services; pin notification replicas: 1
README.md                             # service table + smoke instructions
scripts/smoke_phase3.sh               # end-to-end Phase 3 smoke
Makefile                              # add nlp-worker pytest target + test-phase-3
```

---

## Milestone overview

| Group | Tasks | Outcome |
|---|---|---|
| Data | 1, 2 | Two new migrations apply on a fresh DB |
| Backend skeleton | 3, 4, 5 | Three new services build and start (no real logic yet) |
| Moderation | 6, 7, 8 | Reports endpoint, resolve actions, audit log, Kafka publish |
| Notification core | 9, 10, 11 | REST list/read endpoints, Redis unread-count cache, Kafka consumer |
| Notification SSE | 12, 13 | In-process fan-out + Envoy SSE-friendly route |
| NLP worker | 14, 15 | Keyword maps (en + vi), idempotent consumer, removal of inline path |
| Frontend | 16, 17, 18 | Notification bell with SSE, admin reports queue, audit tab |
| Glue | 19, 20, 21 | Envoy routes, compose wiring, Prometheus scrape |
| Verification | 22, 23, 24 | Test commands + integration smoke + final DoD + tag |

---

## Task 1: Migration 10 for `audit_logs`

- [ ] Create `migrations/20260526000010_audit_logs.sql` with the schema from spec §4.1.
- [ ] Add `idx_audit_logs_actor_created`, `idx_audit_logs_target`, `idx_audit_logs_report` indexes.
- [ ] Define the `audit_action` enum with all six members.
- [ ] Verify:
  ```bash
  cd /Users/nhathaminh/oecophylla
  docker compose run --rm migrate
  docker compose exec postgres psql -U oecophylla -d oecophylla \
    -c "\dt audit_logs" \
    -c "SELECT typname FROM pg_type WHERE typname = 'audit_action';"
  ```

---

## Task 2: Migration 11 for `notifications`

- [ ] Create `migrations/20260526000011_notifications.sql` with the schema from spec §4.2.
- [ ] Define `notification_kind` enum with all seven members.
- [ ] Add `idx_notifications_user_created` and partial `idx_notifications_user_unread_created`.
- [ ] Verify:
  ```bash
  docker compose run --rm migrate
  docker compose exec postgres psql -U oecophylla -d oecophylla \
    -c "\dt notifications" \
    -c "\d notifications"
  ```

---

## Task 3: Cargo workspace + skeletons for moderation-service & notification-service

- [ ] Append `services/moderation-service` and `services/notification-service` to `backend/Cargo.toml`'s `members`.
- [ ] For each, scaffold:
  - `Cargo.toml` depending on `common`, `axum`, `sqlx`, `deadpool-redis`, `tokio`, `serde`, `tracing`, `tracing-subscriber`, `metrics`, `metrics-exporter-prometheus`. notification-service additionally pulls `tokio` `sync` features + `tokio-stream` for SSE; moderation-service additionally pulls `rdkafka` because it produces events.
  - `src/main.rs` wiring tracing, config load, Postgres pool, Redis client, health, metrics, then a single placeholder route.
  - `src/state.rs` with `AppState { pg, redis, kafka_producer? }`.
  - `src/config.rs` reading env vars.
- [ ] Verify both binaries build: `cd backend && cargo build -p moderation-service -p notification-service`.

---

## Task 4: Dockerfiles for moderation-service & notification-service

- [ ] Mirror Phase 2B feed-service Dockerfile pattern:
  - Builder: `rust:1.85` (Debian bookworm) with `apt-get install -y cmake pkg-config libssl-dev ca-certificates`.
  - Workspace cargo fetch + workspace build with `--bin moderation-service` / `--bin notification-service`.
  - Runtime: `debian:trixie-slim` + `apt-get install -y ca-certificates libssl3` (rdkafka in moderation-service).
- [ ] Verify each image builds: `docker compose build moderation-service notification-service`.

---

## Task 5: nlp-worker scaffold

- [ ] Create `workers/nlp_worker/` with:
  - `requirements.txt`: `asyncpg==0.30.*`, `aiokafka==0.12.*`, `cramjam>=2.8`, `pydantic==2.*`, `pydantic-settings==2.*`, `pytest==8.*`, `pytest-asyncio==0.25.*`.
  - `pytest.ini` with `pythonpath = .` (mirror Phase 2B closeout fix).
  - `app/main.py` entrypoint with a placeholder loop that joins the consumer group and exits cleanly on SIGTERM.
  - `app/config.py` reading `DATABASE_URL`, `KAFKA_BROKERS`.
- [ ] Dockerfile: `FROM python:3.13-trixie`, copy + `pip install --no-cache-dir`, `CMD ["python", "-m", "app.main"]`.
- [ ] Verify locally: `docker compose build nlp-worker` succeeds.

---

## Task 6: moderation-service endpoints (list + detail)

- [ ] Implement:
  - `GET /admin/reports?status=pending&cursor=&limit=20` → opaque cursor (base64 of `created_at,id` from the pending-status partial index).
  - `GET /admin/reports/:id` → full report with post snippet + reporter username.
  - `GET /admin/audit-logs?actor_id=&action=&cursor=&limit=20`.
  - `GET /admin/users/:id/history` → join recent reports targeting the user + audit log entries.
- [ ] All routes gated by `require_admin` extractor (Task 7).
- [ ] Pagination uses `(created_at, id) <` predicate so the partial pending index is hit.

---

## Task 7: `require_admin` extractor in `crates/common`

- [ ] Add `crates/common/src/auth/require_admin.rs` (or extend `auth.rs`):
  - Axum `FromRequestParts` impl that runs the existing `AuthUser` extractor and returns 403 unless `user.role == UserRole::Admin`.
- [ ] Unit test:
  - Admin → handler runs.
  - User/creator → 403.
  - No cookie → 401.
- [ ] Verify: `cargo test -p common require_admin`.

---

## Task 8: moderation-service resolve + audit + Kafka

- [ ] `POST /admin/reports/:id/resolve` body `{ action, note? }` with the four actions from spec §4.4.
- [ ] Service runs one Postgres transaction:
  1. Lock the report row (`FOR UPDATE`); error 409 if not `pending`.
  2. Update `reports.status` to the target state.
  3. For `hide_post`: update `posts.status = 'hidden'`.
  4. For `ban_author`: update `users.is_active = false` for `post.author_id`.
  5. Insert one row into `audit_logs` with the appropriate `audit_action`.
- [ ] Commit, then publish a `oecophylla.moderation.action` event via rdkafka.
- [ ] Smoke tests in `services/moderation-service/tests/smoke.rs`:
  - Non-admin gets 403.
  - Admin can `dismiss` a pending report → status `resolved_ok` + audit row + Kafka event.
  - Admin `hide_post` flips post status + audit + Kafka.
  - Admin `ban_author` flips `users.is_active` + audit + Kafka.
  - Resolving an already-resolved report returns 409.

---

## Task 9: notification-service repo + REST endpoints

- [ ] Implement:
  - `GET /api/v1/notifications?cursor=&limit=20&unread_only=false` — opaque cursor of `(created_at,id)`.
  - `POST /api/v1/notifications/:id/read` — sets `read_at` if not set; invalidates `notif:unread_count:{user_id}` in Redis.
  - `POST /api/v1/notifications/read-all` — bulk `UPDATE ... SET read_at = now() WHERE user_id = $1 AND read_at IS NULL`; invalidates the cache key.
  - `GET /api/v1/notifications/unread-count` — read-through Redis; 30-min TTL.
- [ ] DTO: `{ id, kind, actor: { id, username, avatar_url? }?, post: { id, snippet }?, comment_id?, payload, read, created_at }`. Actor + post hydration via small joined query, not separate round trips.
- [ ] Smoke tests in `services/notification-service/tests/smoke.rs`:
  - Insert a notification directly through repo; `GET` returns it.
  - Mark-read flips `read_at` and decrements unread count.
  - Read-all returns the count of newly-read rows.
  - Cursor pagination does not overlap.

---

## Task 10: notification-service Kafka consumer (interactions + follow + moderation)

- [ ] Spawn one `rdkafka` consumer per topic on startup (or one client subscribed to three topics; same group).
- [ ] Group id: `oecophylla.notification.v1`.
- [ ] For each event:
  - Apply the mapping table from spec §7.3.
  - Skip self-actions (user_id == actor_id).
  - Insert into `notifications` (with `actor_id`, `post_id`, etc.) and capture the inserted DTO.
  - Hand the DTO to the fan-out registry (Task 12). Failures here log but do not block the insert.
  - Invalidate `notif:unread_count:{user_id}` in Redis.
- [ ] Smoke (still in the existing tests/smoke.rs):
  - Produce a `liked` interaction event for a post owned by user B (liker = user A); notification-service inserts a `liked` notification for B and `unread_count` returns 1.
  - Self-like emits zero notifications.
  - Produce a `moderation.action` `post_hidden` event for user C; notification appears for C.

---

## Task 11: Redis `notif:unread_count` cache helpers

- [ ] In notification-service `repo.rs`, add:
  - `unread_count(user_id) -> u64` with read-through pattern.
  - `invalidate_unread_count(user_id)` called on every insert and on every read-update.
- [ ] TTL 1800s.
- [ ] Verify by hand: increment count, sleep 1 min, see count cached; mark-read → cache deleted, next read recomputes.

---

## Task 12: SSE fan-out registry

- [ ] `src/fanout.rs`:
  - `pub struct Fanout { map: Mutex<HashMap<Uuid, Vec<broadcast::Sender<NotificationDto>>>> }`.
  - `Fanout::subscribe(user_id) -> broadcast::Receiver<NotificationDto>` registers a new sender + returns its receiver.
  - `Fanout::publish(user_id, dto)` clones to every sender for that user; prunes closed senders.
  - `Fanout::unsubscribe(user_id, sender_id)` on stream drop.
- [ ] Wire `Fanout` into `AppState` as `Arc<Fanout>`.
- [ ] Kafka consumer task (Task 10) calls `fanout.publish` after the row insert.

---

## Task 13: SSE stream endpoint

- [ ] `GET /api/v1/notifications/stream` returns an `axum::response::sse::Sse` stream:
  - Authenticate via cookies (`AuthUser`).
  - Subscribe to `fanout` for the user.
  - Emit `event: notification` for each new dto.
  - Emit `event: heartbeat` every 25 s via `tokio::time::interval` merged with the broadcast stream.
  - On disconnect / shutdown, unsubscribe.
- [ ] Headers: `Content-Type: text/event-stream`, `Cache-Control: no-store`, `X-Accel-Buffering: no` (Envoy honors).
- [ ] Smoke (using `reqwest` and reading partial response):
  - Open stream → insert a notification via Kafka → first non-heartbeat event arrives within 1 s.
  - Two concurrent connections for the same user both receive the event.

---

## Task 14: nlp-worker keyword maps & inference

- [ ] `app/keywords.py`: define `TOPIC_KEYWORDS_EN` and `TOPIC_KEYWORDS_VI` from spec §6.5.
- [ ] `app/infer.py`:
  - `def infer_topics(content: str) -> list[str]:` normalizes to lowercase + NFKC, scans both maps, returns sorted set of matched keys; if empty returns `["general"]`.
- [ ] Tests (`tests/test_keywords.py`):
  - "I love AI and coding" → contains `ai` and `tech`.
  - "Bài hát mới của ca sĩ X" → contains `music`.
  - Mixed-language post → union from both maps.
  - Empty content → `["general"]`.

---

## Task 15: nlp-worker consumer + idempotency

- [ ] `app/kafka_consumer.py` subscribes to `oecophylla.content.created`, group `oecophylla.nlp.v1`.
- [ ] Micro-batch: 5 s or 50 events.
- [ ] For each event: load post by id; if `topics` already non-empty, skip (idempotent for replays and admin overrides); else compute via `infer_topics` and `UPDATE posts SET topics = $1 WHERE id = $2 AND coalesce(cardinality(topics), 0) = 0`.
- [ ] Remove the inline call site in `backend/services/content-service/src/handler.rs` that Phase 2B Task 5 added and delete the helper module. Adjust the unit test that proved the helper; the assertion now lives in the worker tests.
- [ ] Update the Phase 2B smoke step that checked `topics @> ARRAY['ai']` to retry every 500 ms for up to 5 s.
- [ ] Idempotency test (`tests/test_infer_idempotent.py`): re-invoking the worker logic on the same post leaves topics untouched (uses `pytest-asyncio` + an in-memory fake repo).

---

## Task 16: Frontend types, API helpers, store

- [ ] `frontend/src/lib/api/notifications.ts` with typed clients for list, mark-read, read-all, unread-count.
- [ ] `frontend/src/lib/stores/notifications.ts`:
  - Writable store `{ items, unread, connected }`.
  - `init()` fetches initial list + unread count.
  - `subscribeSSE()` opens `EventSource('/api/v1/notifications/stream', { withCredentials: true })`, handles `notification` + `heartbeat` events, reconnects with exponential back-off (1s, 2s, 5s, 10s, then cap) on `error`.

---

## Task 17: NotificationBell + dropdown

- [ ] `frontend/src/lib/components/NotificationBell.svelte` — bell SVG + numeric badge + click toggles dropdown.
- [ ] `frontend/src/lib/components/NotificationItem.svelte` — one item: actor avatar + verb phrase + relative time + click marks read + navigates.
- [ ] Mount the bell in `Topbar.svelte`. **Note:** the bar/header re-introduction depends on the dirty state of `frontend/src/routes/+layout.svelte`; if the user kept Topbar removed, instead mount the bell directly at the top of `/`.
- [ ] Tailwind-first; reuse `.glass-surface`. No new global CSS.

---

## Task 18: `/admin` real reports + audit UI

- [ ] `frontend/src/routes/admin/+page.server.ts` SSR loader: requires `data.user?.role === 'admin'`; otherwise SvelteKit error 403.
- [ ] Replace the existing mock in `frontend/src/routes/admin/+page.svelte` with a two-tab layout (Reports / Audit) using `<AdminReportsTable>` + `<AdminAuditTable>`.
- [ ] Each row in Reports has the four action buttons + a textarea for an optional note. Submitting calls `POST /admin/reports/:id/resolve` and re-fetches the page after success. Show a confirm modal on `ban_author` only.
- [ ] Audit tab paginates with cursor; filters by actor and action via query params.

---

## Task 19: Envoy routes for admin + notifications + SSE

- [ ] In `envoy/envoy.yaml`:
  - Add cluster entries for `moderation_service` and `notification_service`.
  - Route `/api/v1/notifications/stream` first (more specific) with `idle_timeout: 60s`, no response buffering (`auto_host_rewrite: false`, `internal_redirect_action: PASS_THROUGH` not needed; ensure no buffer filter in the chain rewrites the body).
  - Route `/api/v1/notifications/` to notification-service.
  - Route `/admin/` to moderation-service.
  - Keep these routes **above** the catch-all to interactions.

---

## Task 20: Compose + Prometheus wiring

- [ ] In `compose.yaml`:
  - Add `moderation-service`, `notification-service`, `nlp-worker` blocks.
  - `notification-service` gets `deploy.replicas: 1` and a comment documenting the single-replica constraint.
  - Health checks (curl `/health`) for the two HTTP services.
  - Each new service mounted with the standard env block (DATABASE_URL, REDIS_URL, KAFKA_BROKERS, JWT_SECRET, optional METRICS_BIND).
  - Apply `restart: unless-stopped` matching peers.
- [ ] `envoy.dev` extension or main compose: keep ports 8006 + 8007 exposed on host only via `compose.dev.yaml`.
- [ ] In `infra/prometheus/prometheus.yml` add scrape configs for the new services + worker.
- [ ] No `.env.example` changes (repo currently has none tracked).

---

## Task 21: Kafka topic provisioning

- [ ] Update `scripts/init-topics.sh` (or `compose.yaml` `init-topics` command) to create `oecophylla.moderation.action` with 1 partition, retention 7 days.
- [ ] Idempotent: skip if topic already exists.
- [ ] Verify: `docker compose run --rm init-topics && docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --list | grep moderation`.

---

## Task 22: Makefile + README updates

- [ ] Makefile:
  - `test-python` already runs recommendation + feature store; extend to also run `cd workers/nlp_worker && pytest`.
  - `test-phase-3` target = `cargo test --workspace --no-fail-fast` + `pnpm run check && pnpm run build` + `$(MAKE) test-python` + `bash scripts/smoke_phase3.sh`.
- [ ] README adds rows for moderation-service, notification-service, nlp-worker; documents the SSE caveat (idle_timeout, single replica) and how to bypass via `docker compose exec` for Kafka.

---

## Task 23: Phase 3 integration smoke script

- [ ] `scripts/smoke_phase3.sh` (mirrors Phase 2B structure):
  1. Start a fresh user A (reporter), user B (author), and admin user C (must be seeded with `role = 'admin'`; seed script or `docker compose exec postgres psql` insert acceptable).
  2. B publishes a post.
  3. A reports the post via `POST /api/v1/posts/:id/report` (Phase 2A endpoint).
  4. C `GET /admin/reports` shows the pending row; C `POST /admin/reports/:id/resolve` with `action=hide_post`.
  5. Assert post is now `hidden`, audit log has one new row, Kafka topic has one event.
  6. A receives a `liked`-style baseline notification via prior step (or substitute: A also liked the post earlier). Either way assert `unread_count >= 1` for B and a `post_hidden` notification arrived for B.
  7. NLP worker check: write a fresh post containing "trí tuệ nhân tạo" and poll `posts.topics` until it contains `ai` (up to 5 s).
- [ ] Use UUIDv7 random-suffix usernames; clean up cookies on exit.

---

## Task 24: Final verification and tag

- [ ] Run, from `/Users/nhathaminh/oecophylla`:
  ```bash
  docker compose up -d --build
  docker compose ps
  docker compose run --rm migrate
  cd backend && cargo test --workspace --no-fail-fast
  cd ../frontend && pnpm run check && pnpm run build
  cd ../recommendation_api && pytest
  cd ../workers/feature_store_worker && pytest
  cd ../workers/nlp_worker && pytest
  cd .. && bash scripts/smoke_phase3.sh
  ```
- [ ] Manual checks:
  - Open two browser sessions for the same user; liking from session 1 produces a live notification in session 2 within 1 s.
  - Killing recommendation-api still keeps the feed working (Phase 2B fallback unaffected).
  - Banning a user with `ban_author` and then trying to log in as them fails.
  - `docker compose restart notification-service` and confirm the bell reconnects automatically.
- [ ] Tag (the user will run this themselves):
  ```bash
  git tag phase-3-complete
  git push origin main phase-3-complete
  ```

---

## Execution notes for subagents

- Do not edit unrelated dirty files (`claude.md`, `frontend/src/routes/+layout.svelte`, `frontend/src/lib/apple-glass/`) unless a task explicitly names them.
- Use `rg`/`rg --files` for discovery.
- Avoid destructive commands; never run `git reset --hard`, `git checkout -- .`, `git push --force`, or `docker compose down -v`.
- Kafka host caveat: macOS host cannot resolve `kafka:9092`; Kafka-dependent smoke runs inside compose or via `docker compose exec kafka ...`.
- Use UUIDv7 random suffixes for any test usernames.
- Keep frontend Tailwind-first; do not introduce large custom CSS.
- nlp-worker and recommendation-api live outside the Cargo workspace.
- Long-running container runtime base must be `debian:trixie-slim` or a Trixie-based upstream image.
- Python workers must include `cramjam>=2.8` so aiokafka can decode LZ4-compressed batches from Kafka 4.0.
- Per the Phase 2B closeout the user wants to **batch commits themselves**. Subagents should stage focused diffs, run verification, then stop. Surface a one-line commit-message suggestion in the task summary but do not run `git commit` unless the user reverses that instruction.
