from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
from functools import lru_cache

from .content_features import ENCODER_VERSION


class EmbeddingMetrics:
    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        labels = {"encoder_version": ENCODER_VERSION}
        self._labels = labels
        self._inference = Histogram(
            "nlp_embedding_inference_seconds",
            "Latency of multilingual article embedding inference.",
            ["encoder_version"],
            registry=registry,
        )
        self._outcomes = Counter(
            "nlp_embedding_outcomes_total",
            "Embedding processing outcomes.",
            ["encoder_version", "outcome"],
            registry=registry,
        )
        self._failures = Counter(
            "nlp_embedding_failures_total",
            "Embedding failures grouped by bounded reason.",
            ["encoder_version", "reason"],
            registry=registry,
        )
        self._missing = Gauge(
            "nlp_embedding_missing",
            "Whether the most recently processed post required topic fallback.",
            ["encoder_version"],
            registry=registry,
        )
        self._rebuild_lag = Gauge(
            "nlp_embedding_rebuild_lag_seconds",
            "Age of the source post most recently reached by the rebuild.",
            ["encoder_version"],
            registry=registry,
        )

    def observe_inference(self, elapsed: float) -> None:
        self._inference.labels(**self._labels).observe(elapsed)

    def feature_created(self) -> None:
        self._missing.labels(**self._labels).set(0)
        self._outcomes.labels(**self._labels, outcome="created").inc()

    def feature_unchanged(self) -> None:
        self._missing.labels(**self._labels).set(0)
        self._outcomes.labels(**self._labels, outcome="unchanged").inc()

    def embedding_missing(self) -> None:
        self._missing.labels(**self._labels).set(1)
        self._outcomes.labels(**self._labels, outcome="fallback").inc()

    def embedding_failure(self, reason: str) -> None:
        bounded = reason if reason in {"model", "validation", "storage", "future_source"} else "other"
        self._failures.labels(**self._labels, reason=bounded).inc()

    def set_rebuild_lag(self, seconds: float) -> None:
        self._rebuild_lag.labels(**self._labels).set(max(0.0, seconds))


@lru_cache(maxsize=1)
def default_metrics() -> EmbeddingMetrics:
    return EmbeddingMetrics()
