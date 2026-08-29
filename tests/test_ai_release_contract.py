from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).parents[1]


def _read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def test_raw_telemetry_has_180_day_retention_and_scheduled_pruning():
    migration = _read(
        "migrations/20260829000017_recommendation_telemetry_retention.sql"
    )
    values = _read("charts/oecophylla/values.yaml")
    jobs = _read("charts/oecophylla/templates/jobs.yaml")

    assert "prune_recommendation_telemetry" in migration
    assert "180 days" in migration
    assert "DELETE FROM behavior_events" in migration
    assert "DELETE FROM recommendation_impressions" in migration
    assert "telemetryRetention" in values
    assert "kind: CronJob" in jobs
    assert "prune_recommendation_telemetry" in jobs


def test_required_ai_telemetry_metrics_have_dashboard_and_alerts():
    feed = _read("backend/services/feed-service/src/handlers.rs")
    interaction = _read("backend/services/interaction-service/src/handlers.rs")
    recommendation = _read("recommendation_api/app/model_ranker.py") + _read(
        "recommendation_api/app/features.py"
    )
    dataset = _read("ai_pipeline/build_dataset.py")
    alerts = _read("infra/prometheus/ai-alerts.yml")
    prometheus = _read("infra/prometheus/prometheus.yml")
    dashboard = json.loads(_read("infra/grafana/dashboards/ai-telemetry.json"))

    required_metrics = {
        "feed_impressions_persisted_total": feed,
        "feed_impression_persist_failures_total": feed,
        "feed_responses_total": feed,
        "behavior_events_accepted_total": interaction,
        "behavior_events_duplicate_total": interaction,
        "behavior_events_rejected_total": interaction,
        "behavior_event_ingest_lag_seconds": interaction,
        "recommendation_candidate_exclusions_total": recommendation,
        "recommendation_model_load_total": recommendation,
        "recommendation_model_predict_total": recommendation,
        "recommendation_model_fallback_total": recommendation,
        '"class_balance"': dataset,
    }
    for metric, source in required_metrics.items():
        assert metric in source

    assert "ai-alerts.yml" in prometheus
    assert "feed_impression_persist_failures_total" in alerts
    assert "recommendation_model_fallback_total" in alerts
    assert "behavior_events_rejected_total" in alerts
    assert "behavior_event_ingest_lag_seconds" in alerts
    assert len(dashboard["panels"]) >= 6


def test_top_level_ai_targets_and_trace_smoke_are_reproducible():
    makefile = _read("Makefile")
    smoke = _read("scripts/smoke_ai_telemetry.sh")

    assert "test-ai-pipeline:" in makefile
    assert "smoke-ai-telemetry:" in makefile
    assert "evaluate-ai:" in makefile
    assert "prune-ai-telemetry:" in makefile
    assert "recommendation_impressions" in smoke
    assert "behavior_events" in smoke
    assert "feature_snapshot" in smoke
    assert "RANKER_MODE=heuristic" in smoke


def test_cutover_defaults_prevent_two_view_counter_writers():
    compose = _read("compose.yaml")
    values = _read("charts/oecophylla/values.yaml")
    smoke = _read("scripts/smoke_ai_telemetry.sh")

    assert "LEGACY_VIEW_COUNTER_ENABLED: ${LEGACY_VIEW_COUNTER_ENABLED:-false}" in compose
    assert (
        "BEHAVIOR_VIEW_COUNTER_ENABLED: ${BEHAVIOR_VIEW_COUNTER_ENABLED:-false}"
        in compose
    )
    assert "LEGACY_VIEW_COUNTER_ENABLED" in values
    assert "BEHAVIOR_VIEW_COUNTER_ENABLED" in values
    assert "must not both be true" in smoke


def test_product_status_remains_honest_until_release_gate_has_evidence():
    readme = _read("README.md")
    status = _read("docs/AI_ML_RELEASE_STATUS.md")

    assert "heuristic recommendation system with an ML experimentation pipeline" in readme
    assert "Release decision: INCONCLUSIVE" in status
    assert "NDCG@10" in status
    assert "RANKER_MODE=heuristic" in status
    assert "180 days" in status
