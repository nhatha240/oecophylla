from app.content_features import ENCODER_VERSION
from app.metrics import EmbeddingMetrics
from prometheus_client import CollectorRegistry, generate_latest


def test_embedding_metrics_expose_required_versioned_signals() -> None:
    registry = CollectorRegistry()
    metrics = EmbeddingMetrics(registry)

    metrics.observe_inference(0.25)
    metrics.feature_created()
    metrics.feature_unchanged()
    metrics.embedding_failure("model")
    metrics.embedding_missing()
    metrics.set_rebuild_lag(42)

    exposition = generate_latest(registry).decode()
    assert ENCODER_VERSION in exposition
    assert "nlp_embedding_inference_seconds" in exposition
    assert "nlp_embedding_failures_total" in exposition
    assert "nlp_embedding_missing" in exposition
    assert "nlp_embedding_rebuild_lag_seconds" in exposition
