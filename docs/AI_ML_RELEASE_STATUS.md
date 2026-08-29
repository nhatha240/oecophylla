# AI/ML release status

Release decision: INCONCLUSIVE

Oecophylla currently runs a heuristic recommendation system with an ML experimentation pipeline. The ML and shadow serving paths are implemented, but ML is not approved as the production default because this checkout does not contain enough real temporal holdout evidence or a live end-to-end telemetry trace.

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

Raw `recommendation_impressions` and `behavior_events` are retained for 180 days. The scheduled Helm retention job calls `prune_recommendation_telemetry`; longer-lived aggregate reports are intentionally separate. Account deletion continues to remove user-linked raw rows through database foreign-key cascades.

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
