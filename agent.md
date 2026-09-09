# Oecophylla — Agent Context

Social network with news-feed recommendation and multi-layer moderation.
Rust microservices + Python ranking/ML, event-driven over Kafka.

**This file is auto-loaded every session. Keep it under ~200 lines.**
Detail lives elsewhere and is read only when a task needs it:

| Need | Read |
|---|---|
| "Which file do I change?" | `docs/MAP.md` — read this before searching |
| Schema, API surface, Kafka payloads, ranking formula, conventions | `docs/SPEC.md` |
| Active recommendation work (T1a–T9) | `plans/oecophylla-mind-aligned-recommendation-completion.md` |
| ML release gates & rollback | `docs/AI_ML_RELEASE_STATUS.md` |
| Versioned data contracts | `docs/contracts/` |

---

## Current state — 2026-09-08

### What is running

- **Rust** — Cargo workspace `backend/`: `crates/common` + 8 binaries under `backend/services/`:
  `auth-service` :8001, `user-service` :8002, `content-service` :8003, `interaction-service` :8004,
  `feed-service` :8005, `moderation-service` :8006, `notification-service` :8007,
  `cache-invalidator` (Kafka consumer, no HTTP).
- **Python** — `recommendation_api/` FastAPI :8090 (repo root, *not* under `services/`),
  `services/analytics-service/` FastAPI :8091, `workers/feature_store_worker/`,
  `workers/nlp_worker/`, shared `workers/common/`.
- **Offline ML** — `ai_pipeline/` (dataset → train → evaluate), `recommendation_label/`
  (canonical label contract, dependency-free).
- **Frontend** — SvelteKit adapter-node + Tailwind. Routes: `/`, `/login`, `/register`, `/logout`,
  `/profile/[id]`, `/post/new`, `/post/[id]`, `/post/[id]/edit`, `/notifications`, `/saved`,
  `/search`, `/settings`, `/tag/[tag]`, `/topic/[topic]`, `/admin`, plus `/api/v1/[...path]` proxy.
  Playwright specs in `frontend/e2e/`.
- **Infra** — `compose.yaml` + `compose.dev.yaml` (host ports). Envoy gateway, Prometheus,
  Grafana :3001. Helm chart in `charts/oecophylla/` for Kubernetes.
- **Migrations** — 19 in `migrations/`, applied by the one-shot `migrate` service.

### Phase history

| Phase | Tag |
|---|---|
| 0+1 infra, auth/user/content, frontend | `phase-0-1-complete` |
| 2A interactions, comments, reports | `phase-2a-complete` |
| 2B feed, recommendation, workers | `phase-2b-complete` |
| 3 moderation, notifications, NLP | `phase-3-complete` |

Phase 4 (analytics, evaluation, observability) shipped but was **never tagged**.

### Active work — MIND-aligned recommendation

**Done:** T1a (label contract) · T1b (label implementation) · T2 (grouped split + metrics) ·
T3 (time-aware preference vector v2) · T4a (content feature contract) ·
T4b (multilingual embedding worker) · T5 (leakage-safe history snapshots) ·
T6 (dataset v2 + MIND adapter, merged at `ea9c51b`).

**Open:** T7 (NRMS-like model, work remains on a separate branch) · T8a (NRMS shadow serving) ·
T8b (hybrid retrieval telemetry) · T9 (E2E live evidence + release gates).

ML release decision is **INCONCLUSIVE**. Production default is `RANKER_MODE=heuristic`.
“Done” above means merged implementation, not full live release acceptance.
Current review evidence and remaining exit criteria: `docs/PROJECT_REVIEW_STATUS.md`.

---

## Locked decisions — do not re-decide

Override only on explicit instruction from Nhật.

| Decision | Detail |
|---|---|
| API gateway | **Envoy v1.32** (`envoy/envoy.yaml`). Not Nginx |
| Postgres | **18**, `uuidv7()` for every PK. Volume at `/var/lib/postgresql`, not the legacy `/data` subpath |
| Kafka | **KRaft** single-node `apache/kafka:4.0.0`. No Zookeeper |
| Redis | `redis:8-trixie` — no Trixie build of Redis 7 exists |
| Rust toolchain | **1.94.0** (`ARG RUST_VERSION` in `backend/Dockerfile`) |
| Rust build | cargo-chef, one builder stage per binary → `debian:trixie-slim` runtime. Builder needs `cmake pkg-config libssl-dev ca-certificates` for rdkafka |
| `jsonwebtoken` | `default-features = false` — HS256 only, avoids the time/simple_asn1 chain |
| Auth cookies | `oec_access` (Path=/, 15m, SameSite=Lax) + `oec_refresh` (Path=/api/v1/auth, 7d, SameSite=Strict). HttpOnly always. argon2id |
| Ranker default | `heuristic`. ML is shadow-only until the gates in `docs/AI_ML_RELEASE_STATUS.md` pass |
| Label contract | `recommendation_label/` is the single source. Never fork the semantics per service |
| Schema changes | Additive, forward-only. Roll back with a new migration or a config flag |
| Frontend styling | Tailwind-first. Named class only when a pattern repeats across 3+ components (`.glass-surface`, `.glass-chip`, `.glass-pill`, `.glass-button-primary`, `.text-display-serif`, `.text-mono-meta`) |
| Smoke test usernames | UUIDv7 **suffix** `&u[22..]`, not the timestamp prefix — the prefix collides in fast loops |
| Kafka from host | macOS cannot resolve `kafka:9092`. Run inside the compose network or via `docker compose exec kafka ...` |

---

## Coding rules — enforced

1. No `.unwrap()` / `.expect()` in handler or service layers. `?` with `AppError`.
2. No blocking calls in async context — `tokio::task::spawn_blocking`.
3. Every Kafka produce failure is logged. Events are never silently dropped.
4. Rate limiting runs **before** auth extraction.
5. Every admin action writes `audit_logs` in the same transaction as the action.
6. Feed fallback is non-negotiable: recommendation-api 5xx or >500 ms → trending feed, never a 500.
7. All errors use `{ "error": { "code", "message" } }`.
8. Workers are idempotent — replaying an event must not double-count.
9. New tests before the fix (RED then GREEN) — the git history follows this pattern.

---

## Commands

```bash
make up                 # compose up -d --build (with dev port overrides)
make down / logs / ps
make test               # cargo test --workspace + frontend vitest
make test-python        # pytest: recommendation_api, feature_store_worker, nlp_worker
make test-ai-pipeline   # pytest in ai_pipeline via uv
make fmt / lint         # cargo fmt|clippy -D warnings + prettier|eslint
make deny / audit       # cargo-deny, cargo-audit
make sqlx-prepare       # after changing any SQL query
make train-ai / evaluate-ai
make smoke-ai-telemetry # SKIP_DATABASE_TRACE=true to run without a live DB
make prune-ai-telemetry
```

---

## Working agreements

- **Locate, don't read.** Start from `docs/MAP.md`, then `rg -n`, then `Read` with `offset`/`limit`.
  Reading whole files to orient is the main way sessions get expensive.
- **Fan-out searches go to an `Explore` subagent** — its file dumps stay out of the main context.
- **Prefer commands over reading**: `cargo check`, `rg -c`, `git diff --stat` answer more per token.
- **Edit in place** with `sed -i` or a read-modify-write script. Never retype a file from tool output.
- Independent tasks are dispatched in parallel — one message, multiple `Agent` calls.
- "Let run" / "ngủ" mode = skip approval gates, run end-to-end.
- Update this file when state changes, then run `make sync-agent-md`.

---

## Known follow-ups

- No `phase-4-complete` tag; `phase-0-1-complete` and `phase-2a-complete` were never pushed to origin.
- Counter drift recompute job — periodic SQL to heal `posts` counters after out-of-band deletes.
- Toast component to replace `alert()` rollbacks in `PostActionBar`.
- Pre-bake `sqlx-cli` into the migrate image — first boot currently builds it from source (~6–8 min).
- Host-accessible Kafka listener on `:29092` so smoke tests can run outside the compose network.

## Environment notes

- `feature-store-worker` needs `cramjam>=2.8` (not pip `lz4`) so aiokafka can decode Kafka 4.0's
  LZ4 batches. Without it the worker dies on first fetch and preference vectors stay silently empty.
- After adding Envoy clusters, `docker compose restart envoy` — compose does not detect bind-mount
  config changes.
- Python service tests need `pythonpath = .` in `pytest.ini`.
