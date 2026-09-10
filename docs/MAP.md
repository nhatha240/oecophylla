# Oecophylla — Code Map

> **Purpose:** locate code without reading it. Every row answers "I want to change X — which file?"
> Verified against the repo on 2026-09-04. If a path here is wrong, fix this file in the same commit.
>
> **Method:** `rg -n '<symbol>' <path from this table>` → `Read` with `offset`/`limit`.
> Never `Read` a whole service to find one function.

---

## 1. Repository layout (what each top-level dir is)

| Path | What lives there |
|---|---|
| `backend/` | Cargo workspace. `crates/common` (shared) + `services/*` (8 binaries) |
| `recommendation_api/` | Python FastAPI ranking service (:8090). **Not** `services/recommendation-api` |
| `services/analytics-service/` | Python FastAPI dashboard metrics (:8091). Only service under `services/` |
| `workers/` | `common/` (shared Kafka helper), `feature_store_worker/`, `nlp_worker/` |
| `ai_pipeline/` | Offline ML: dataset build, train, evaluate. Run via `make train-ai` / `make evaluate-ai` |
| `recommendation_label/` | Dependency-free label contract shared by telemetry, worker, dataset, evaluator |
| `frontend/` | SvelteKit (adapter-node, Tailwind). `e2e/` = Playwright |
| `migrations/` | 19 sqlx migrations + `Dockerfile` for the one-shot `migrate` job |
| `charts/oecophylla/` | Helm chart for Kubernetes deploy (prod + orbstack values) |
| `envoy/envoy.yaml` | API gateway routing. Single source for "which path goes to which service" |
| `infra/` | `prometheus/`, `grafana/`, `kafka/` config mounted into compose |
| `docs/contracts/` | Versioned data contracts (label v2, content features v1, telemetry v1) |
| `plans/` | Active multi-task plan (MIND-aligned recommendation, T1a–T9) |
| `tests/` | Cross-cutting contract tests (Python, repo root) |
| `artifacts/models/` | Trained model artifacts; mounted read-only into recommendation-api |

---

## 2. "I want to change…" → read this

### Auth & identity
| Task | File |
|---|---|
| Register / login / refresh / logout handlers | `backend/services/auth-service/src/handlers.rs` |
| Password hashing, token issue | `backend/services/auth-service/src/handlers.rs` + `backend/crates/common/src/auth.rs` |
| JWT validation middleware (all services) | `backend/crates/common/src/middleware/auth.rs` |
| Cookie names / TTL | `backend/services/auth-service/src/handlers.rs` (`oec_access`, `oec_refresh`) |
| Rate limiting | `backend/crates/common/src/middleware/rate_limit.rs` |

### Content & social graph
| Task | File |
|---|---|
| Post create / update / delete | `backend/services/content-service/src/handlers.rs`, `update.rs` |
| Post SQL queries | `backend/services/content-service/src/repo.rs` |
| Feed pagination cursor | `backend/services/content-service/src/cursor.rs` |
| Search endpoint | `backend/services/content-service/src/handlers.rs` (`GET /api/v1/search`) |
| Profile, follow/unfollow | `backend/services/user-service/src/handlers.rs`, `repo.rs` |
| Avatar upload | `backend/services/user-service/src/avatar.rs` |

### Interactions & telemetry
| Task | File |
|---|---|
| Like / save / hide / report, comments | `backend/services/interaction-service/src/handlers.rs` |
| Behavior event batch ingest | `backend/services/interaction-service/src/handlers.rs` (`POST /api/v1/interactions/events/batch`) |
| Label semantics (Rust side) | `backend/services/interaction-service/src/label_contract.rs` |
| Label semantics (Python, canonical) | `recommendation_label/__init__.py` |
| Kafka event emission | `backend/services/interaction-service/src/events.rs` + `backend/crates/common/src/kafka.rs` |
| Comment notification fan-out | `backend/services/interaction-service/src/comment_fanout.rs` |

### Feed & recommendation
| Task | File |
|---|---|
| Feed endpoint, cache read/write | `backend/services/feed-service/src/handlers.rs`, `cache.rs` |
| Call to recommendation-api + fallback | `backend/services/feed-service/src/recommendation.rs` |
| Candidate retrieval (follow/topic/trending) | `recommendation_api/app/main.py` |
| Heuristic ranking formula | `recommendation_api/app/ranking.py` |
| ML ranker (shadow) | `recommendation_api/app/model_ranker.py` |
| Preference vector read | `recommendation_api/app/features.py` |
| Preference vector write (v2, time-decayed) | `workers/feature_store_worker/app/features.py` |
| Feed cache invalidation | `backend/services/cache-invalidator/src/consumer.rs` |

### NLP & embeddings
| Task | File |
|---|---|
| Topic tagging / keywords | `workers/nlp_worker/app/keywords.py`, `content_features.py` |
| Multilingual embedding inference | `workers/nlp_worker/app/embedding_worker.py`, `model.py` |
| Model download / prefetch | `workers/nlp_worker/app/model_download.py` |
| Kafka consumer loop + checkpointing | `workers/nlp_worker/app/kafka_consumer.py`, `runtime.py` |
| Backfill existing posts | `workers/nlp_worker/app/rebuild.py` |

### Offline ML
| Task | File |
|---|---|
| Dataset construction, temporal split | `ai_pipeline/build_dataset.py` |
| Training | `ai_pipeline/train.py` |
| Metrics, guardrails, release decision | `ai_pipeline/evaluate.py` |
| Feature/artifact schemas | `ai_pipeline/schemas.py`, `artifact.py` |

### Moderation, notifications, admin
| Task | File |
|---|---|
| Report queue, resolve, audit log | `backend/services/moderation-service/src/handlers.rs`, `repo.rs` |
| Moderation rules config | `backend/services/moderation-service/src/config.rs` |
| Notification create + SSE stream | `backend/services/notification-service/src/handlers.rs`, `fanout.rs`, `kafka.rs` |
| Admin dashboard metrics | `services/analytics-service/app/main.py` |

### Frontend
| Task | File |
|---|---|
| API wrapper, token refresh | `frontend/src/lib/api.ts` (+ `lib/server/`) |
| Server-side proxy to Envoy | `frontend/src/routes/api/v1/[...path]/+server.ts` |
| Feed page + view tracking | `frontend/src/routes/+page.svelte`, `+page.server.ts` |
| Auth / UI stores | `frontend/src/lib/stores/` |
| Shared components | `frontend/src/lib/components/`, `lib/apple-glass/` |
| Any page | `frontend/src/routes/<route>/+page.svelte` (route list in CLAUDE.md) |
| E2E tests | `frontend/e2e/*.spec.ts` |

### Infrastructure
| Task | File |
|---|---|
| Add/route an API path | `envoy/envoy.yaml` |
| Add a service / change env | `compose.yaml` (+ `compose.dev.yaml` for host ports) |
| Rust build stages | `backend/Dockerfile` (cargo-chef, one stage per binary) |
| DB schema change | new file in `migrations/` (additive, forward-only) |
| Kafka topic creation | `compose.yaml` → `init-topics` service |
| Prometheus scrape / alerts | `infra/prometheus/` |
| Grafana dashboards | `infra/grafana/` |
| Kubernetes deploy | `charts/oecophylla/templates/`, `values*.yaml` |

---

## 3. Cross-cutting: where a concept is defined once

| Concept | Single source of truth |
|---|---|
| Label / behavior semantics | `recommendation_label/__init__.py` (`CONTRACT_VERSION = "engagement-label-v2"`) |
| Contract docs | `docs/contracts/*.md` |
| API path → service routing | `envoy/envoy.yaml` |
| Env var defaults | `compose.yaml` (`${VAR:-default}` form) |
| Shared Rust types, errors, metrics | `backend/crates/common/src/` |
| Shared worker Kafka helper | `workers/common/oecophylla_worker_common/kafka.py` |
| Release gates / ML status | `docs/AI_ML_RELEASE_STATUS.md` |

---

## 4. Fast lookups (copy-paste)

```bash
# Which service owns an API path?
rg -n '<path>' envoy/envoy.yaml

# Where is a route handler?
rg -n 'route\("/api/v1/<thing>' backend/services

# Which migration touched a table?
rg -l '<table_name>' migrations/

# Which env var is read where?
rg -n '<VAR_NAME>' compose.yaml charts/oecophylla backend recommendation_api workers

# Which Kafka topic does a consumer read?
rg -n 'topic|TOPIC' workers/*/app/settings.py backend/services/*/src/consumer.rs

# Does it compile / do queries match the DB?
cd backend && cargo check --workspace
```

---

## 5. Reading budget

| Question type | Cost | Do this |
|---|---|---|
| "Where is X?" | ~1k tokens | `rg -l` / `rg -n`, this file |
| "How does X work?" | ~5k | `rg -n` to find it, then `Read` with `offset`/`limit` |
| "Audit all of X across the repo" | ~5k in main context | dispatch an `Explore` subagent, keep only its conclusion |
| "What changed recently?" | ~1k | `git log --oneline -20`, `git diff --stat` |

Do **not** read `docs/SPEC.md` unless the task needs schema/API detail — it is reference, not context.
