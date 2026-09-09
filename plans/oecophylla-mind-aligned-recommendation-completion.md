# Oecophylla MIND-aligned recommendation completion plan

## Objective

Bring Oecophylla from its current heuristic/topic-based feed to a production-safe, MIND-aligned news recommendation system for Vietnamese content. “MIND-aligned” means preserving impression candidate groups, using leakage-safe click histories and temporal splits, evaluating with MIND ranking metrics, and adding a content/history model inspired by NRMS. It does not mean deploying a model trained only on the English MIND dataset.

Current implementation and task status: [2026-09-08 review](../docs/PROJECT_REVIEW_STATUS.md).
T6 is merged; T7–T9 implementation and review work are now consolidated locally on `codex/integrated-review-mind`. Their acceptance criteria remain open; the tested MIND pilot is rejected and production ML readiness remains INCONCLUSIVE. See `docs/MIND_COMPLETION_20260909.md` for current evidence.

## Original planning baseline (historical)

- Serving logs one `recommendation_impressions` row per served post and links behavior events through `impression_id`.
- Personalized candidates come from followed authors, top user topics, and recent posts.
- The fallback ranker is `heuristic-v1`; the optional ML ranker is pointwise Logistic Regression.
- Behavior preference vectors are cumulative topic weights with no time decay or sequence model.
- The dataset builder performs row-level temporal splits, so one request can cross train/validation/test boundaries.
- Positive behavior semantics differ between the browser, interaction service, feature worker, dataset builder, and online evaluator.
- Article understanding is a fixed keyword-to-topic classifier; there is no multilingual content embedding.
- Production configuration remains `RANKER_MODE=heuristic`, and no production-derived winning artifact is present in the checkout.

## Non-negotiable invariants

1. The canonical request identity is `(user_id, request_id)` online and
   `H(salt:user_id:request_id)` offline; that identity must belong to exactly one
   temporal split.
2. Features and histories for an impression may use only information occurring before its serving timestamp.
3. User/post raw identities must not be exported in training artifacts.
4. One versioned label contract must be used by telemetry, feature computation, dataset construction, and evaluation.
5. ML failure or timeout must return the current heuristic/fallback feed.
6. MIND is used as a benchmark/schema reference; production training must include Vietnamese, production-domain telemetry.
7. The production default remains heuristic until a temporal holdout and live shadow gate pass.
8. Every schema change is additive and forward-only; rollback is performed with a new migration or configuration change.

## Dependency graph

```text
T1a contract ───────────────> T1b behavior implementation ──> T3 pref vector
T2 grouped split + metrics ──────────────────────────────────────────┐
T4a embedding storage ──────> T4b embedding worker ────────> T5 history
T1b + T4b ─────────────────────────────────────────────────> T5 history
T2 + T4b + T5 ─────────────────────────────────────────────> T6 dataset v2
T6 ────────────────────────────────────────────────────────> T7 NRMS model
T3 + T4b + T7 ─────────────────────────────────────────────> T8a serving
T8a ───────────────────────────────────────────────────────> T8b retrieval telemetry
T7 + T8a + T8b ────────────────────────────────────────────> T9 release gate
```

Parallel execution waves:

- Wave 1: T1a, T2, and T4a.
- Wave 2: T1b and T4b.
- Wave 3: T3 and T5.
- Wave 4: T6.
- Wave 5: T7.
- Wave 6: T8a.
- Wave 7: T8b.
- Wave 8: T9.

Git is available on branch `main` with remote `origin`; GitHub CLI is unavailable. Each task should use a short-lived branch and be reviewed/merged using the repository’s normal manual Git workflow. Do not mix unrelated dirty-worktree changes into these branches.

## T1a — Specify one machine-readable behavior and label contract

**Branch:** `ai/t1a-behavior-label-contract`

**Dependencies:** None.

**Execution tier:** Strongest model/reviewer because this contract affects every later label and metric.

**Context brief:** The frontend emits a qualified feed `view` at 5 seconds, while `POSITIVE_DWELL_MS` defaults to 10 seconds. The interaction-service publishes `viewed` to Kafka only when a `view` crosses the positive threshold, but its `dwell` branch never sets `positive_signal`. The dataset treats long `dwell` as positive, whereas the online evaluator treats every `view` as positive and ignores `dwell`.

**Tasks:**

- Add `docs/contracts/recommendation-label-v2.md` defining exposure, click, qualified read, positive engagement, strong positive, negative, and strong negative events.
- Add a machine-readable `docs/contracts/recommendation-label-v2.json` containing event names, required fields, thresholds, precedence, reversals, and output labels.
- Add one shared JSON fixture matrix covering exactly-at-threshold, below-threshold, click-before-visible, long dwell, like/save/share, hide/report, undo events, and duplicates.
- Define concrete rollout flags: `RECOMMENDATION_LABEL_VERSION=v1|v2`, `FEATURE_EVENT_VERSION=v1|v2`, and a configurable `QUALIFIED_READ_MS`.
- Define the canonical request identity and collision policy: one `(user_id, request_id)` has one immutable request envelope and fingerprint derived from request metadata plus the ordered candidate set. Reject reuse with a different feed source, model/version, ordering, or candidate set; separately deduplicate identical per-candidate retries and enforce unique positions/posts within the request.
- Version the label definition as `engagement-label-v2`; keep v1 datasets readable but never mix v1 and v2 in one training run.

**Primary files:**

- `docs/contracts/`
- `tests/fixtures/recommendation_telemetry/`

**Verification:**

```bash
python -m json.tool docs/contracts/recommendation-label-v2.json >/dev/null
python -m json.tool tests/fixtures/recommendation_telemetry/label-v2-cases.json >/dev/null
```

**Exit criteria:** The JSON contract and fixture are complete enough that TS, Rust, and Python implementations can consume the same cases without inventing local semantics.

**Rollback:** Documentation-only task; retain the reviewed contract and do not activate v2 flags.

## T1b — Implement label v2 across telemetry, worker, and evaluation

**Branch:** `ai/t1b-behavior-label-implementation`

**Dependencies:** T1a.

**Execution tier:** Strongest model/reviewer because this changes event semantics across languages.

**Context brief:** Implement the T1a machine-readable contract without creating separate TS, Rust, and Python interpretations. The existing frontend 5-second view, backend 10-second positive threshold, non-positive dwell branch, and divergent Python label rules must converge.

**Tasks:**

- Make the frontend and interaction service use `QUALIFIED_READ_MS`; remove hard-coded threshold disagreement.
- Persist duration consistently for `view` and `dwell`, and publish versioned, idempotent feature events for qualified reads.
- Add lightweight contract readers or generated constants in TS, Rust, and Python; all three test the shared fixture matrix.
- Centralize Python label derivation and use it from the dataset builder and online evaluator.
- Update the feature worker to consume v2 events and apply qualified dwell exactly once.
- Keep v1/v2 dual-read support during rollout and select the producer with `RECOMMENDATION_LABEL_VERSION` and `FEATURE_EVENT_VERSION`.

**Primary files:**

- `frontend/src/lib/actions/viewTracker.ts`
- `frontend/src/lib/telemetry/recommendationTelemetry.ts`
- `backend/services/interaction-service/src/handlers.rs`
- `backend/services/interaction-service/src/events.rs`
- `workers/feature_store_worker/app/main.py`
- `ai_pipeline/build_dataset.py`
- `recommendation_api/app/evaluate.py`

**Verification:**

```bash
(cd frontend && pnpm vitest run src/lib/actions/viewTracker.test.ts src/lib/telemetry/recommendationTelemetry.test.ts)
(cd backend && cargo test -p interaction-service --test behavior_events)
uv run --with-requirements workers/feature_store_worker/requirements.txt pytest -q workers/feature_store_worker/tests
uv run --with-requirements ai_pipeline/requirements.txt pytest -q ai_pipeline/tests/test_build_dataset.py
uv run --with-requirements recommendation_api/requirements.txt pytest -q recommendation_api/tests/test_evaluate.py
```

**Exit criteria:** The shared fixture produces the same semantic label in TS, Rust, worker, dataset, and evaluator; qualified dwell updates the preference signal exactly once.

**Rollback:** Set both version flags to `v1`; continue storing v2-compatible raw events and do not delete them.

## T2 — Preserve impression groups and implement MIND metric semantics

**Branch:** `ai/t2-grouped-temporal-split-metrics`

**Dependencies:** None; this correctness repair precedes all new dataset/model work.

**Execution tier:** Strongest model/reviewer because leakage and metric errors can falsely approve a model.

**Context brief:** `_split_rows` currently sorts and slices individual samples. A synthetic audit reproduced one request split across validation and test. Evaluation later groups by request, so a split request yields an incomplete candidate set.

**Tasks:**

- Replace row-level splitting with chronological splitting over atomic canonical request identities; export `request_group=H(salt:user_id:request_id)`.
- Use a deterministic boundary policy for groups tied at the cutoff timestamp; document it in dataset metadata.
- Add assertions that request groups are disjoint across all splits and that every group retains all eligible candidates.
- Add impression-level AUC and MRR, plus explicit nDCG@5 and nDCG@10.
- Define edge cases per metric: zero-click requests contribute `0` to MRR/nDCG; single-class requests are excluded from impression AUC; reports must show excluded counts and meet a minimum eligible-request gate before AUC can approve a release.
- Retain product metrics such as coverage, diversity, and strong-negative rate as separate guardrails.
- Compute confidence intervals by resampling request groups, not individual rows.
- Fail evaluation when a request has fewer than two candidates, has no stable request identity, or appears in multiple splits.
- Fail ingestion/build on conflicting canonical request identities instead of silently composing different grouping keys.
- Record request counts and candidate-count distributions per split in metadata.

**Primary files:**

- `ai_pipeline/build_dataset.py`
- `ai_pipeline/evaluate.py`
- `ai_pipeline/tests/test_build_dataset.py`
- `ai_pipeline/tests/test_evaluate.py`
- `recommendation_api/app/metrics.py`
- `recommendation_api/tests/test_metrics.py`

**Verification:**

```bash
uv run --with-requirements ai_pipeline/requirements.txt pytest -q ai_pipeline/tests
uv run --with-requirements recommendation_api/requirements.txt pytest -q recommendation_api/tests/test_metrics.py recommendation_api/tests/test_evaluate.py
```

**Exit criteria:** A test fixture with groups crossing percentage boundaries keeps every group atomic; reports include AUC, MRR, nDCG@5, and nDCG@10 with request-level confidence intervals.

**Rollback:** Dataset schema v1 remains available for audit, but release tooling must reject it for new model promotion.

## T3 — Make the heuristic preference vector stable and time-aware

**Branch:** `ai/t3-preference-vector-v2`

**Dependencies:** T1b.

**Execution tier:** Default implementation with strong review of normalization and cache behavior.

**Context brief:** Topic weights currently accumulate forever. Negative weights contribute to the relevance denominator even though negative topic relevance is clamped to zero, which can suppress unrelated positive interests. Declared topics use a fixed additive weight that becomes negligible for mature users.

**Tasks:**

- Define `preference-vector-v2` with event-time exponential decay, bounded per-topic values, and explicit positive/negative channels.
- Normalize behavior and declared topic preferences separately, then blend with configurable coefficients.
- Recompute decay from event timestamps during rebuilds; do not decay repeatedly based on worker delivery time.
- Version Redis keys and stored vectors so v1 and v2 cannot be confused.
- Invalidate `pref:{user_id}`, versioned preference keys, and `feed:{user_id}` after relevant behavior or declared-topic changes.
- Update `cache-invalidator` to recognize v2 behavior event names and delete every active versioned preference/history/feed key through one tested key registry.
- Backfill v2 vectors from canonical `behavior_events`; keep v1 as the immediate fallback during rollout.
- Add tests for out-of-order events, duplicate events, undo actions, long inactivity, negative feedback, and preference cache invalidation.

**Primary files:**

- `workers/feature_store_worker/app/features.py`
- `workers/feature_store_worker/app/main.py`
- `recommendation_api/app/db.py`
- `recommendation_api/app/ranking.py`
- `backend/services/user-service/src/handlers.rs`
- `backend/services/cache-invalidator/src/consumer.rs`
- `migrations/`

**Verification:**

```bash
uv run --with-requirements workers/feature_store_worker/requirements.txt pytest -q workers/feature_store_worker/tests
uv run --with-requirements recommendation_api/requirements.txt pytest -q recommendation_api/tests/test_user_vector.py recommendation_api/tests/test_ranking.py
(cd backend && cargo test -p user-service -p cache-invalidator)
```

**Exit criteria:** Replaying the same ordered or out-of-order event set produces the same bounded vector; stale interests decay; cache invalidation is proven by integration tests.

**Rollback:** Set the active preference schema to v1 and retain v2 rows for diagnosis.

## T4a — Define storage and encoder contract for multilingual article features

**Branch:** `ai/t4a-article-feature-contract`

**Dependencies:** None; can run in parallel with T1a and T2.

**Execution tier:** Strongest model for the storage/encoder contract, default model for implementation.

**Context brief:** News content is currently reduced to eleven keyword topics. Oecophylla content is Vietnamese, while MIND is English, so the production encoder must be multilingual and evaluated on local content.

**Tasks:**

- Add an additive `post_content_features` table containing `post_id`, `encoder_version`, a fixed-dimension embedding, normalized topics, content hash, and timestamps.
- Select and pin one multilingual sentence encoder after a small Vietnamese semantic-retrieval benchmark; record license, checksum, dimension, and preprocessing.
- Define the versioned feature payload and deterministic text normalization contract.
- Define dimension, content-hash, uniqueness, and supported-encoder constraints in migration tests.
- Document the fallback rule: existing keyword topics remain authoritative when embeddings are absent.

**Primary files:**

- `migrations/`
- `docs/contracts/post-content-features-v1.md`
- `tests/fixtures/`

**Verification:**

```bash
(cd backend && cargo sqlx prepare --workspace -- --all-targets)
docker compose config
```

**Exit criteria:** Storage and payload contracts reject wrong dimensions/versions, preserve existing posts, and support multiple immutable encoder versions.

**Rollback:** Do not enable a producer for the additive table; leave the empty schema in place.

## T4b — Implement multilingual embedding inference and backfill

**Branch:** `ai/t4b-article-embedding-worker`

**Dependencies:** T4a.

**Execution tier:** Default implementation with strong review of model provenance and failure behavior.

**Context brief:** Implement the T4a contract in the existing NLP worker. The worker must never prevent a post from being served when the model is unavailable.

**Tasks:**

- Compute embeddings idempotently from normalized content and refresh only when content hash or encoder version changes.
- Keep keyword topics as interpretable fallback features.
- Add batch rebuild tooling with progress, retries, resumability, and CPU/memory limits.
- Pin model license, checksum, preprocessing, dependency versions, and download/deployment strategy.
- Add metrics for missing embeddings, inference latency, encoder version, failures, and rebuild lag.
- Add tests for deterministic normalization, dimension validation, idempotency, changed content, unavailable model, and safe fallback.

**Primary files:**

- `workers/nlp_worker/app/`
- `workers/nlp_worker/tests/`
- `compose.yaml`
- `charts/oecophylla/`

**Verification:**

```bash
uv run --with-requirements workers/nlp_worker/requirements.txt pytest -q workers/nlp_worker/tests
docker compose config
```

**Exit criteria:** New and edited Vietnamese posts obtain a versioned embedding exactly once, and missing-model operation leaves posts servable through topic fallback.

**Rollback:** Disable embedding inference and continue using stored topics; retain content-feature rows.

## T5 — Build leakage-safe sequential user histories

**Branch:** `ai/t5-user-history-snapshots`

**Dependencies:** T1b and T4b.

**Execution tier:** Strongest model/reviewer.

**Context brief:** MIND-style models represent a user through the ordered news they clicked before the target impression. The current cumulative vector has no order and cannot distinguish recent from long-term interest.

**Tasks:**

- Define qualifying history events using the v2 label contract; click is the MIND-comparable primary history, with other engagement available only as product extensions.
- Build ordered histories strictly from events before each impression’s `served_at`.
- Cap history length with configurable recent and long-term windows; preserve timestamps and encoder versions.
- Add a serving-side history loader that batch-fetches article embeddings and caches only versioned, reconstructible history data.
- Invalidate history cache after qualifying events and account deletion.
- Export hashed history post identities only when needed for group auditing; never export raw IDs.
- Add leakage tests for future clicks, simultaneous events, delayed ingestion, deleted posts, missing embeddings, and empty-history users.

**Primary files:**

- `ai_pipeline/build_dataset.py`
- `ai_pipeline/schemas.py`
- `recommendation_api/app/db.py`
- `recommendation_api/app/schemas.py`
- `backend/services/interaction-service/`
- `migrations/` if a materialized history index is required

**Verification:**

```bash
uv run --with-requirements ai_pipeline/requirements.txt pytest -q ai_pipeline/tests/test_build_dataset.py
uv run --with-requirements recommendation_api/requirements.txt pytest -q recommendation_api/tests
(cd backend && cargo test -p interaction-service)
```

**Exit criteria:** For every sample, the newest history timestamp is earlier than serving time; online and offline loaders produce the same ordered history for a fixed fixture.

**Rollback:** Disable sequential history and fall back to preference-vector-v2.

## T6 — Publish recommendation dataset v2 and a MIND adapter

**Branch:** `ai/t6-mind-dataset-v2`

**Dependencies:** T2, T4b, and T5.

**Execution tier:** Strongest model/reviewer.

**Context brief:** The v1 dataset is one flat candidate row with a broad engagement label. A MIND-aligned dataset must retain served-impression identity, ordered prior click history, candidate click labels, article representations, and atomic temporal splits. Current telemetry contains served posts and visibility events, not the full pre-ranking retrieval pool; retrieval recall is therefore explicitly deferred to T8b.

**Tasks:**

- Define `recommendation-dataset-v2` with candidate rows grouped by request, ordered history snapshots, `click_label`, and separate `utility_label`.
- Build ranking samples only from served posts with proven visibility; preserve `served` and `visible` separately and never label an unviewed served post or an unlogged retrieved post as negative.
- Mark the dataset scope as `served-impression-reranking`; do not claim retrieval-recall evaluation from this dataset.
- Add an import adapter for official `news.tsv` and `behaviors.tsv` MIND formats without coupling production storage to MIND IDs.
- Add a local-data exporter using the same logical schema so MIND and Oecophylla fixtures can exercise identical training code.
- Pin dataset, feature, label, encoder, code, and query-window versions in metadata.
- Add validation for class balance, candidates per request, empty histories, missing embeddings, split disjointness, and identity privacy.
- Create small deterministic fixtures for MIND-format English data and local Vietnamese telemetry.

**Primary files:**

- `ai_pipeline/build_dataset.py`
- `ai_pipeline/schemas.py`
- `ai_pipeline/config.py`
- `ai_pipeline/mind_adapter.py` (new)
- `ai_pipeline/tests/fixtures/`
- `docs/contracts/`

**Verification:**

```bash
uv run --with-requirements ai_pipeline/requirements.txt pytest -q ai_pipeline/tests
uv run --with-requirements ai_pipeline/requirements.txt python -m ai_pipeline.build_dataset --help
uv run --with-requirements ai_pipeline/requirements.txt python -m ai_pipeline.mind_adapter --help
```

**Exit criteria:** Both MIND and local fixtures generate schema-v2 datasets accepted by the same validator; no request crosses splits and no history contains future behavior.

**Rollback:** Continue producing v1 for audit only; training and promotion stay blocked until v2 is available.

## T7 — Train and evaluate an NRMS-like impression-aware model

**Branch:** `ai/t7-nrms-ranker`

**Dependencies:** T6.

**Execution tier:** Strongest model for architecture and evaluation, default model for test/packaging work.

**Context brief:** Logistic Regression currently classifies candidates independently and ignores request groups and ordered history. The next model should score candidates within an impression and model recent clicked-news context, while consuming precomputed multilingual article embeddings.

**Tasks:**

- Implement an NRMS-like user encoder using multi-head self-attention over ordered history embeddings and candidate scoring by similarity.
- Train with candidates grouped by impression and negatives sampled only from the same eligible impression.
- Handle empty histories through declared topics and recent/popular fallback features rather than fabricated clicks.
- Keep the current heuristic and Logistic Regression as explicit baselines.
- Evaluate the pure history/content scorer before applying business fallbacks or diversity policies; report raw-model and post-policy metrics separately.
- Make training deterministic, seed-controlled, checkpointed, and resumable.
- Extend immutable artifact manifests with architecture, embedding version, history length, label schema, dataset checksum, dependencies, and calibration details.
- Evaluate on untouched temporal test requests with AUC, MRR, nDCG@5, nDCG@10 and product guardrails.
- Segment reports by new/existing user, new/established article, history length, feed source, and language.
- Reject promotion on insufficient samples, request leakage, missing segment results, or guardrail regression.

**Primary files:**

- `ai_pipeline/model.py`
- `ai_pipeline/train.py`
- `ai_pipeline/evaluate.py`
- `ai_pipeline/artifact.py`
- `ai_pipeline/tests/`
- `ai_pipeline/requirements.txt`

**Verification:**

```bash
make test-ai-pipeline
uv run --with-requirements ai_pipeline/requirements.txt python -m ai_pipeline.build_dataset \
  --schema-version v2 --start "$AI_WINDOW_START" --end "$AI_WINDOW_END" \
  --extraction-time "$AI_EXTRACTION_TIME" --database-url "$DATABASE_URL" \
  --identity-mode hash --hash-salt "$DATASET_HASH_SALT" \
  --output artifacts/datasets/dataset-v2.parquet
make train-ai AI_DATASET=artifacts/datasets/dataset-v2.parquet AI_ARTIFACT=artifacts/models/nrms-v1
make evaluate-ai AI_DATASET=artifacts/datasets/dataset-v2.parquet AI_ARTIFACT=artifacts/models/nrms-v1
```

**Exit criteria:** The artifact is reproducible and loadable in a fresh process; the report compares identical test request groups and does not claim a win without statistical power.

**Rollback:** Keep artifacts immutable and switch training/release selection back to the Logistic Regression or heuristic baseline.

## T8a — Integrate safe NRMS shadow serving

**Branch:** `ai/t8a-nrms-shadow-serving`

**Dependencies:** T3, T4b, and T7.

**Execution tier:** Strongest model/reviewer because this changes the live ranking path.

**Context brief:** Candidate generation uses fixed one-third quotas for follow/topic/recent, does not backfill after deduplication, and the serving feature contract leaves author affinity fields empty. The runtime already supports heuristic, shadow, and ML modes with fallback.

**Tasks:**

- Introduce a versioned serving contract for candidate embeddings, ordered history, followed-author state, and author affinity.
- Batch-load all features once per request; prohibit per-candidate database queries.
- Populate `is_followed_author` from the follow graph and define/populate `author_affinity` from pre-serving behavior only, end to end through snapshot, training, and inference. If affinity cannot be implemented in this PR, remove it from the active feature contract instead of shipping a permanently imputed column.
- Load the NRMS artifact once at startup, batch-score candidates, enforce a latency budget, and fall back atomically on timeout or invalid output.
- Run new artifacts in shadow mode first; persist both heuristic and shadow scores without exposing shadow ordering to users.
- Ensure final diversity, safety, hide/report, seen-cooldown, inactive-author, and unpublished-post policies remain enforced.
- Add integration tests for cold users, new articles, missing embeddings, model timeout, corrupt artifact, cache hit, and fallback.

**Primary files:**

- `recommendation_api/app/ranking.py`
- `recommendation_api/app/model_ranker.py`
- `recommendation_api/app/main.py`
- `recommendation_api/app/schemas.py`
- `backend/services/feed-service/`
- `migrations/`

**Verification:**

```bash
uv run --with-requirements recommendation_api/requirements.txt pytest -q recommendation_api/tests
(cd backend && cargo test -p feed-service)
SKIP_DATABASE_TRACE=true make smoke-ai-telemetry
docker compose config
```

**Exit criteria:** Shadow scoring is traceable per request, respects the latency budget, never changes user-visible order, and falls back without returning a feed error.

**Rollback:** Set `RANKER_MODE=heuristic` and restart recommendation-api; retain shadow telemetry and artifacts.

## T8b — Complete hybrid candidate generation and retrieval telemetry

**Branch:** `ai/t8b-candidate-retrieval-telemetry`

**Dependencies:** T8a.

**Execution tier:** Strongest model/reviewer because telemetry volume and retrieval labels can distort both cost and evaluation.

**Context brief:** Current production telemetry records only final served posts. Retrieval-pool candidates need a distinct, sampled/retained telemetry contract before candidate recall can be evaluated. They must never be treated as negative engagement merely because they were retrieved but not served.

**Tasks:**

- Backfill follow/topic/recent sources after exclusion and deduplication so the requested pool size is met when enough eligible posts exist.
- Keep business and cold-start sources, and add semantic similarity as a retrieval/reranking source with an explicit version.
- Add append-only candidate-stage telemetry containing request identity, candidate `post_id`, stage, source, retrieval score, eligibility reason, model/version, and timestamp. Keep `post_id` only in protected operational storage and export `H(salt:post_id)` for offline reports/artifacts.
- Define sampling and retention limits separately from served impressions; exclude raw content and unnecessary identity fields.
- Join retrieval candidates to served impressions for recall/coverage analysis, while never deriving engagement negatives from unserved rows.
- Add retrieval metrics: eligible-pool size, source contribution, dedup/backfill rate, served recall, latency, and missing-feature rate.
- Add tests for underfilled sources, duplicates across sources, exclusions, sampled telemetry, retention, and request traceability.

**Primary files:**

- `recommendation_api/app/features.py`
- `recommendation_api/app/main.py`
- `recommendation_api/app/schemas.py`
- `migrations/`
- `ai_pipeline/` retrieval-analysis module
- `infra/grafana/dashboards/ai-telemetry.json`

**Verification:**

```bash
uv run --with-requirements recommendation_api/requirements.txt pytest -q recommendation_api/tests
(cd backend && cargo test -p feed-service)
make smoke-ai-telemetry
```

**Exit criteria:** Every sampled retrieval pool traces to its final served request, source underfill is observable, and no unserved candidate is emitted as an engagement negative.

**Rollback:** Disable candidate-stage telemetry and semantic retrieval independently; keep existing follow/topic/recent generation and served-impression logging.

## T9 — Complete E2E, live evidence, and release gates

**Branch:** `ai/t9-mind-release-gates`

**Dependencies:** T7, T8a, and T8b.

**Execution tier:** Strongest reviewer for release decision; default model for test automation and documentation.

**Context brief:** `docs/AI_ML_RELEASE_STATUS.md` is currently `INCONCLUSIVE` because no production-derived comparison or live served-to-behavior-to-dataset trace exists.

**Tasks:**

- Extend `frontend/e2e/social-journey.spec.ts` with feed impression context, visible/view/click/dwell collection, hide behavior, cache invalidation, and subsequent recommendation change; retain its existing register/login/follow/post/like/comment/share/topic-preference coverage.
- Add an integration trace proving `served -> visible/click/dwell -> dataset-v2 row -> history -> shadow score` with matching request/model/feature versions.
- Run a representative temporal evaluation and store its JSON/Markdown report outside Git if it contains sensitive operational data.
- Define minimum request counts and guardrail thresholds for AUC, MRR, nDCG@5, nDCG@10, coverage, diversity, strong negatives, latency, and fallback rate.
- Require cold-user, new-article, and Vietnamese-content segments to pass separately.
- Observe shadow mode for the configured window, then perform a small canary before changing the default ranker.
- Document operational dashboards, alert thresholds, rollback, artifact pinning, telemetry retention, and incident steps.
- Update `docs/AI_ML_RELEASE_STATUS.md` only from evidence: `INCONCLUSIVE`, `FAIL`, `NO_REGRESSION`, or `WIN`.

**Primary files:**

- `frontend/e2e/`
- `scripts/smoke_ai_telemetry.sh`
- `tests/test_ai_release_contract.py`
- `infra/grafana/dashboards/ai-telemetry.json`
- `infra/prometheus/`
- `docs/AI_ML_RELEASE_STATUS.md`
- `docs/contracts/`

**Verification:**

```bash
(cd frontend && pnpm playwright test)
make test
uv run --with-requirements recommendation_api/requirements.txt pytest -q recommendation_api/tests
uv run --with-requirements workers/feature_store_worker/requirements.txt pytest -q workers/feature_store_worker/tests
uv run --with-requirements workers/nlp_worker/requirements.txt pytest -q workers/nlp_worker/tests
make test-ai-pipeline
make smoke-ai-telemetry
uv run --with-requirements ai_pipeline/requirements.txt python -m ai_pipeline.build_dataset \
  --schema-version v2 --start "$AI_WINDOW_START" --end "$AI_WINDOW_END" \
  --extraction-time "$AI_EXTRACTION_TIME" --database-url "$DATABASE_URL" \
  --identity-mode hash --hash-salt "$DATASET_HASH_SALT" \
  --output artifacts/datasets/dataset-v2.parquet
make evaluate-ai AI_DATASET=artifacts/datasets/dataset-v2.parquet AI_ARTIFACT=artifacts/models/nrms-v1
```

**Exit criteria:** A live trace and temporal comparison report are attached to the release record, all segment and operational gates pass, and rollback has been rehearsed.

**Rollback:** Return the canary to zero and set `RANKER_MODE=heuristic`; keep the failed report and trace for investigation.

## Global review gates

Every task must pass these checks before merge:

- Existing test suites for touched services remain green.
- New tests fail on the pre-change implementation and pass after the change.
- No raw user/post IDs appear in datasets, reports, logs, or model artifacts.
- No feature is reconstructed using current/future state during offline evaluation.
- Schema, label, encoder, dataset, feature, and model versions are explicit.
- Fallback behavior is tested, not inferred.
- Metrics are aggregated by request/impression before global averaging.
- Dirty worktree changes not owned by the task are preserved.

## Anti-patterns to reject

- Calling a pointwise classifier “MIND” merely because it uses click labels.
- Random row splits or splitting candidates from one impression across datasets.
- Treating served-but-never-visible items as confident negative labels.
- Computing historical features from the latest user vector or latest post state.
- Training on English MIND data and directly deploying to Vietnamese content.
- Adding user/post IDs as model features to improve offline metrics.
- Enabling ML by default before shadow and canary evidence exists.
- Silently substituting missing embeddings with zeros without reporting the missingness rate.
- Letting candidate generation, diversity, safety, or exclusion policies disappear inside an opaque model.

## Plan mutation protocol

- **Split:** A task may be divided when it cannot fit in one reviewable PR; preserve its original exit criteria across the child tasks.
- **Insert:** New blocking work receives a task ID such as `T4a` and explicit dependency edges.
- **Reorder:** Reordering is allowed only when file ownership and data-contract dependencies remain valid.
- **Skip:** A task may be skipped only with written evidence that its exit criteria are already satisfied.
- **Abandon:** Record the reason, affected downstream tasks, rollback state, and replacement decision.
- **Audit trail:** Update this plan’s dependency graph and append the decision to the related PR or release record.

## Definition of complete

The objective is complete only when T1a, T1b, T2, T3, T4a, T4b, T5, T6, T7, T8a, T8b, and T9 exit criteria pass; dataset v2 preserves impression groups and prior histories; the NRMS-like ranker has production-domain Vietnamese evaluation evidence; shadow/canary gates approve it; and heuristic rollback remains operational. Passing unit tests alone is not sufficient.
