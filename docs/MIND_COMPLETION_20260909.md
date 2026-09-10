# MIND completion work — 2026-09-09

The MIND implementation (`codex/mind-completion`, `ac18a5a`) and review fixes
(`codex/review-fixes-20260908`, `92fca4e`), including the existing uncommitted
project changes, are consolidated on `codex/integrated-review-mind` in
`/private/tmp/oecophylla-integrated-review-mind`. The original shared checkout
is preserved. This integration is local and has not been pushed or deployed.

## Task and release state

| Task | Implemented and checked | Remaining exit criteria |
| --- | --- | --- |
| T6 | Existing merged dataset/MIND adapter baseline | PostgreSQL extraction now uses persisted event-version metadata and decodes JSONB correctly; production-window review remains required. |
| T7 | Existing NRMS trainer/artifact checks; MIND text-to-embedding bridge; reproducible pilot training; paired comparison against logged order and mean-pool logistic, including segment intervals | The tested NRMS pilot regresses. Logged MIND order is not the Oecophylla heuristic. Full serving-policy parity and production Vietnamese comparison remain open. |
| T8a | Startup NRMS loader, pinned encoder checks, batch candidate/history loading, author follow/affinity snapshot, asynchronous inference with one in-flight batch, timeout/busy/invalid-input fallback, shadow score persistence, generation-time dataset reconstruction | Full-stack serving and latency evidence, including browser-to-database trace, remain required. The publication-age snapshot still uses immutable creation time; exact first-publication provenance needs its own storage contract. |
| T8b | Deduplication/backfill, optional semantic retrieval, sampled append-only candidate table, cache-preserved retrieval ID, hashed membership analysis, retention function/job wiring and metrics | Deployment observation and trace completeness remain required. Semantic search is limited to 2,000 recent eligible articles, not full-catalog ANN. |
| T9 | Fail-closed executable release gate, artifact/report binding, operational thresholds, fixture trace through dataset/history/shadow | Live E2E trace, production Vietnamese holdout, 48-hour shadow observation, bounded canary and rollback rehearsal remain open. |

**ML release is not approved. T7–T9 must not be marked complete.** The tested
MIND pilot is rejected; production readiness remains INCONCLUSIVE because the
production-domain and operational evidence has not been supplied.

## Consolidated branch verification

The combined source passed 116 offline AI tests, 94 API/PostgreSQL/release-contract
tests, the Rust workspace library/binary suite, 15 Rust review regressions,
60 frontend tests, 36 feature-worker tests, 38 NLP-worker tests and 3 shared
Kafka tests. Frontend type checking/build, Helm lint, Compose validation with
`.env.example`, and `git diff --check` passed. The Rust regressions used a fresh
isolated database with all merged migrations. Existing Rust dead-code and two
Python deprecation warnings remain. Browser E2E and production release windows
were not rerun for this merge.

The source snapshot includes existing source/document additions, edits and
removals from the original checkout; generated coverage data is excluded. A
SHA-256 comparison confirmed all 82 original changed paths were preserved in
the shared checkout. The original branches remain available. Model/data
artifacts under `/private/tmp/oecophylla-mind-data` are not included in Git.

## MIND branch verification before integration

Final checks: 116 offline tests, 92 API/integration/release-contract tests, and
5 Rust feed tests passed. Helm lint, Compose config and `git diff --check` passed.
Two existing Python deprecation warnings remain. Browser E2E and production
observation were not run as release evidence.

All SQL migrations were applied to a fresh, isolated PostgreSQL database. A
transactional integration test exercises history, author follow/affinity,
candidate retrieval, semantic scoring, idempotent candidate telemetry,
append-only updates, bounded retention, actual dataset extraction, click/dwell
labels, hashed export and subsequent prior-history loading. The test rolls back
its data. A separate fixture trace compares offline and serving NRMS shadow
scores and confirms heuristic display scores are unchanged.

## Actual MIND pilot

The official Azure links returned HTTP 409. Data was downloaded from the links
used by the maintained [Recommenders downloader](https://github.com/recommenders-team/recommenders/blob/main/recommenders/datasets/mind.py):
[Recommenders/MIND](https://huggingface.co/datasets/Recommenders/MIND).
The Microsoft Research terms were read before download. Data, hashing salt,
embeddings, checkpoints and model artifacts are outside Git.

- MIND-small train archive SHA-256: `6ef97a271580b98ccfc4301ada55cc639423cb0576a78b8dcfcf74a4dbcc3194`.
- MIND-small dev archive SHA-256: `d6ce515dcaa6b6d47ddf0a326eebc8a31b84735ae410285c9882ca2a06eec669`.
- Deterministic request sample, seed `20260909`: 500 official training requests,
  split chronologically into train/validation, and 200 untouched official dev
  requests as test. All candidates from each selected impression are retained.
- 26,958 total candidate rows; 7,786 test candidates in 200 AUC-eligible requests.
- Pinned multilingual E5-small revision and artifact checksum verified. Last 20
  supplied history entries retained; no engagement or publication times inferred.
- Five training epochs with a resumable checkpoint.
- Model SHA-256: `8492ab1fe8db672e6dda7510a053aec55e0a2aed410172c29e83bb0b813bdd78`.

| Metric | Logged order | Logistic baseline | NRMS |
| --- | ---: | ---: | ---: |
| Impression AUC | 0.513642 | 0.618350 | 0.421920 |
| MRR | 0.269046 | 0.361020 | 0.225228 |
| nDCG@5 | 0.246856 | 0.337125 | 0.210026 |
| nDCG@10 | 0.311743 | 0.388017 | 0.256637 |
| Coverage@5 | 0.424714 | 0.365524 | 0.266874 |

NRMS minus logged-order nDCG@10 has a paired 95% interval of
`[-0.095481, -0.013423]`. Against logistic it is `[-0.175303, -0.084988]`.
The lower AUC and coverage also reject this artifact. It must not be promoted.
MIND is an English benchmark and provides no article publication timestamps;
unknown new-article segments remain unknown. This is a bounded pipeline pilot,
not a full MIND-small result or production Vietnamese evidence. Do not tune on
these now-inspected test requests and call them untouched in a later report.

Local evidence directory: `/private/tmp/oecophylla-mind-data/`.
Reports: `comparison-pilot.json`, `comparison-pilot.md`, `release-pilot.json`.
The comparison's `post_policy` currently means confidence fallback only; it is
explicitly not evidence of parity with serving diversity and author constraints.

## Reproduce

From the repository root, after putting the two original archives and extracted
`train/{news,behaviors}.tsv`, `dev/{news,behaviors}.tsv` in a private directory:

```bash
PYTHONPATH=. uv run --python 3.12 --with-requirements ai_pipeline/requirements.txt \
  python scripts/prepare_mind_pilot.py --data-dir /private/tmp/oecophylla-mind-data

uv run --python 3.12 --with-requirements workers/nlp_worker/requirements.txt \
  --with 'pyarrow>=18,<24' python -m ai_pipeline.mind_embeddings \
  --dataset /private/tmp/oecophylla-mind-data/pilot-text.parquet \
  --output /private/tmp/oecophylla-mind-data/pilot-embedded.parquet \
  --model-dir /private/tmp/oecophylla-mind-data/encoder --device mps --batch-size 64

OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
uv run --python 3.12 --with-requirements ai_pipeline/requirements.txt \
  python -m ai_pipeline.train \
  --dataset /private/tmp/oecophylla-mind-data/pilot-embedded.parquet \
  --output /private/tmp/oecophylla-mind-data/nrms-pilot-v1 \
  --epochs 5 --seed 20260909 \
  --checkpoint /private/tmp/oecophylla-mind-data/nrms-pilot.checkpoint

uv run --python 3.12 --with-requirements ai_pipeline/requirements.txt \
  python -m ai_pipeline.evaluate \
  --dataset /private/tmp/oecophylla-mind-data/pilot-embedded.parquet \
  --artifact /private/tmp/oecophylla-mind-data/nrms-pilot-v1 \
  --output /private/tmp/oecophylla-mind-data/comparison-pilot.json

uv run --python 3.12 --with-requirements ai_pipeline/requirements.txt \
  python -m ai_pipeline.release_gate \
  --comparison /private/tmp/oecophylla-mind-data/comparison-pilot.json \
  --model /private/tmp/oecophylla-mind-data/nrms-pilot-v1/model.joblib \
  --output /private/tmp/oecophylla-mind-data/release-pilot.json
```

The release gate exits `2` when rejected or inconclusive. CPU encoding is also
supported via `--device cpu`. A fresh encoder directory must first contain the
repository-pinned, checksum-verified E5 model; inference does not download it.
Do not combine the complete worker and pipeline test requirement files: they
currently pin different pytest-cov versions.

## Operational gate and rollback

Defaults remain `RANKER_MODE=heuristic`, `SEMANTIC_RETRIEVAL_ENABLED=false`, and
`CANDIDATE_TELEMETRY_SAMPLE_RATE=0`. Apply the additive candidate migration before
enabling its sampling. Enable the retention job alongside sampling; candidate
rows have a separate seven-day retention target, processed in batches of at most
10,000. Size job frequency/batch repetitions for actual traffic. Default Helm
retention scheduling remains disabled until configured by the deployment.

`MODEL_TIMEOUT_MS=150` bounds feature-context loading plus inference. One worker
batch per API process may be in flight; requests arriving while a timed-out
worker finishes fall back immediately. Author-context and optional semantic
retrieval have their own bounds. Validate total request p95 against the Rust
feed-service timeout; component bounds are not proof of end-to-end latency.

The executable release gate requires at least 1,000 production test requests;
at least 100 AUC-eligible requests in each cold-user, new-article and Vietnamese
segment; paired metric intervals within 0.01 of both baselines; and coverage,
diversity and strong-negative guardrails within 0.02. Shadow requires 48 hours,
10,000 requests and zero display-order changes. Canary requires 24 hours, 5,000
requests and at most 5% traffic. Both require p95 <= 500 ms, fallback <= 1%, and
errors <= 0.1%. Evidence must bind to the exact model and comparison checksums.

A fixture trace is not live evidence. Before rollout, capture a real matching
served/visible/click/dwell/dataset/history/shadow trace, verify production policy
parity and rehearse `RANKER_MODE=heuristic` with the artifact unavailable. Retain
failed reports; never change thresholds merely to admit a rejected artifact.
