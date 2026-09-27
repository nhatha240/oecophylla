# AI/ML release status

Release decision: INCONCLUSIVE

Oecophylla currently runs a heuristic recommendation system with an ML experimentation pipeline. The ML and shadow serving paths are implemented, but ML is not approved as the production default because this checkout does not contain enough real temporal holdout evidence or a live end-to-end telemetry trace.

## MINDlarge run (2026-09-27)

Round 2 improves over the semantic baseline on 10,000 fresh requests: AUC 0.601871
versus 0.593952 and nDCG@10 0.372102 versus 0.356622, with a positive paired 95%
interval. The constrained model also passes seven synthetic English/Vietnamese
relevance examples and the local API shadow loader. See [round 2 evidence and
usage](MIND_LARGE_R2_20260927.md). This is offline progress; production readiness
remains INCONCLUSIVE pending real social/Vietnamese data and operational gates.

The first run sampled the supplied local MINDlarge files into 8,497 training, 1,503 validation,
and 2,000 held-out requests. A multilingual embedding/attention-head experiment
completed, but the fine-tuned candidate did not beat the semantic mean-pool baseline
and failed the synthetic Vietnamese relevance smoke check. Both artifacts and a
local text recommendation interface are available. Neither is approved for production;
the heuristic default is unchanged. See [the run report and commands](MIND_LARGE_RUN_20260927.md).

## MIND pilot and completion work (2026-09-09)

See [MIND completion evidence](MIND_COMPLETION_20260909.md) for the isolated
implementation branch, reproducible commands, actual reports and remaining task
exit criteria. The requested MIND-small pilot was run: 700 sampled requests,
26,958 candidate rows and 200 untouched official dev requests as test. NRMS AUC
was 0.421920 versus 0.513642 for logged order and 0.618350 for the logistic
baseline. The pilot artifact is rejected. Production readiness remains
INCONCLUSIVE, and T7–T9 remain open; no default ranker change is authorized by
these results.

The PostgreSQL integration check now exercises the real history/context/retrieval
queries and a served/visible/click/dwell-to-dataset/history trace in an isolated,
rolled-back test transaction. This exposed and fixed nonexistent `event_version`
column references and JSONB text decoding in dataset extraction. This controlled
integration test does not replace a production browser trace or observation window.

## Gate evidence required

| Gate | Requirement | Current status |
|---|---|---|
| Ranking quality | ML NDCG@10 must show no regression against the heuristic baseline on the same temporal test requests | Inconclusive: no production-derived comparison report |
| Coverage | Catalog coverage must remain within the configured guardrail | Inconclusive |
| Diversity | Intra-list diversity must remain within the configured guardrail | Inconclusive |
| Strong negatives | Strong-negative ranking proxy must not regress | Inconclusive |
| Statistical power | Test request count and bootstrap interval must be sufficient to make a release decision | Inconclusive |
| Privacy and leakage | Dataset metadata, identity handling, feature allowlist, and temporal split checks must pass | Code checks pass; real dataset review pending |
| Traceability | A served impression must trace through visible/view/dwell events into a dataset row with model version and feature snapshot | Live trace pending |

`make evaluate-ai` compares heuristic and ML rankers on identical request groups and writes machine-readable JSON plus a Markdown report. Its decision is fail-closed: insufficient samples or confidence produces `inconclusive`; a guardrail regression produces `fail`.

## Operations and privacy

Raw `recommendation_impressions` and `behavior_events` are retained for 180 days. The scheduled Helm retention job calls `prune_recommendation_telemetry`; longer-lived aggregate reports are intentionally separate. Physical user deletion cascades through user-linked raw rows. The current account deletion API only deactivates the account (`is_active=false`), so it does not trigger these erasure cascades. Raw rows remain subject to retention; account erasure is an outstanding privacy acceptance item.

Prometheus alerts cover impression persistence failures, model fallbacks, event rejection ratio, and event ingest lag. The AI telemetry dashboard also exposes accepted/duplicate/rejected events, candidate exclusions, feed source, and model lifecycle outcomes. Dataset generation emits row counts, split counts, and class balance in its metadata.

## Verification and rollback

Run:

```bash
make test-ai-pipeline
SKIP_DATABASE_TRACE=true make smoke-ai-telemetry
make evaluate-ai AI_DATASET=artifacts/datasets/dataset.parquet AI_ARTIFACT=artifacts/models/current
```

Before release, run `make smoke-ai-telemetry` without `SKIP_DATABASE_TRACE` against the deployment and attach both its trace and the comparison report to the release record.

Rollback is configuration-only: set `RANKER_MODE=heuristic` and restart the recommendation API. Heuristic mode never loads the model artifact. Keep both `LEGACY_VIEW_COUNTER_ENABLED` and `BEHAVIOR_VIEW_COUNTER_ENABLED` false unless executing an explicitly monitored cutover; they must never both be true.

Current phase/task verification and limitations: [project review status](PROJECT_REVIEW_STATUS.md).
