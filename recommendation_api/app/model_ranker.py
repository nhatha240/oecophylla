from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol, Sequence

import joblib
import numpy as np
from prometheus_client import Counter
from sklearn.pipeline import Pipeline

from .ranking import HEURISTIC_MODEL_VERSION
from .schemas import RecommendationItem

ARTIFACT_SCHEMA_VERSION = "recommendation-model-artifact-v1"
FEATURE_SCHEMA_VERSION = "rank-features-v1"
MODEL_FILENAME = "model.joblib"
FEATURE_COLUMNS = (
    "topic_relevance",
    "freshness",
    "safety_score",
    "author_affinity",
    "heuristic_score",
    "feed_source",
    "candidate_source",
    "is_followed_author",
)
RankerMode = Literal["heuristic", "ml", "shadow"]

MODEL_LOADS = Counter(
    "recommendation_model_load_total",
    "Recommendation model artifact load attempts.",
    ("mode", "status"),
)
MODEL_PREDICTIONS = Counter(
    "recommendation_model_predict_total",
    "Recommendation model batch prediction attempts.",
    ("mode", "status"),
)
MODEL_FALLBACKS = Counter(
    "recommendation_model_fallback_total",
    "Recommendation requests falling back to heuristic ranking.",
    ("mode", "reason"),
)

logger = logging.getLogger(__name__)


class Predictor(Protocol):
    model_version: str

    def predict_scores(self, records: Sequence[Mapping[str, Any]]) -> list[float]: ...


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _matrix(records: Sequence[Mapping[str, Any]]) -> np.ndarray:
    categorical = {"feed_source", "candidate_source", "is_followed_author"}
    rows: list[list[Any]] = []
    for record in records:
        row: list[Any] = []
        for feature in FEATURE_COLUMNS:
            if feature not in record:
                raise ValueError(f"missing model feature: {feature}")
            value = record[feature]
            if feature not in categorical and value is None:
                value = np.nan
            row.append(value)
        rows.append(row)
    return np.asarray(rows, dtype=object)


@dataclass(frozen=True)
class ModelArtifactPredictor:
    pipeline: Pipeline
    model_version: str

    @classmethod
    def load(cls, directory: Path) -> ModelArtifactPredictor:
        manifest_path = directory / "manifest.json"
        model_path = directory / MODEL_FILENAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("artifact_schema_version") != ARTIFACT_SCHEMA_VERSION:
            raise ValueError("unsupported model artifact schema")
        if manifest.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
            raise ValueError("unsupported rank feature schema")
        if tuple(manifest.get("feature_columns", ())) != FEATURE_COLUMNS:
            raise ValueError("artifact feature columns do not match serving runtime")
        expected = manifest["files"][MODEL_FILENAME]["sha256"]
        if _sha256(model_path) != expected:
            raise ValueError("model artifact checksum mismatch")
        pipeline = joblib.load(model_path)
        if not isinstance(pipeline, Pipeline):
            raise ValueError("model artifact is not a sklearn Pipeline")
        model_version = str(manifest.get("model_version", "")).strip()
        if not model_version:
            raise ValueError("model version is missing")
        return cls(pipeline=pipeline, model_version=model_version)

    def predict_scores(self, records: Sequence[Mapping[str, Any]]) -> list[float]:
        probabilities = self.pipeline.predict_proba(_matrix(records))[:, 1]
        return [float(value) for value in probabilities]


@dataclass(frozen=True)
class NRMSArtifactPredictor:
    artifact: Any
    model_version: str
    encoder_version: str
    dimension: int
    requires_context: bool = True

    @classmethod
    def load(cls, directory: Path) -> NRMSArtifactPredictor:
        from ai_pipeline.artifact import LoadedNRMSArtifact, load_artifact
        from workers.nlp_worker.app.content_features import (
            ENCODER_VERSION,
            EMBEDDING_DIMENSION,
        )

        artifact = load_artifact(directory)
        if not isinstance(artifact, LoadedNRMSArtifact):
            raise ValueError("artifact is not NRMS")
        manifest = artifact.manifest
        embedding = manifest["embedding"]
        if (
            embedding["version"] != ENCODER_VERSION
            or embedding["dimension"] != EMBEDDING_DIMENSION
        ):
            raise ValueError("NRMS encoder is incompatible with serving features")
        version = str(manifest.get("model_version", "")).strip()
        if (
            not version
            or manifest.get("dataset_schema_version") != "recommendation-dataset-v2"
        ):
            raise ValueError("NRMS model version or dataset contract is missing")
        return cls(artifact, version, embedding["version"], embedding["dimension"])

    def predict_scores(self, records: Sequence[Mapping[str, Any]]) -> list[float]:
        # The request has one history. Encode it once for the entire candidate batch.
        if not records:
            return []
        first = records[0]
        history = sorted(first["history"], key=lambda entry: entry["ordinal"])
        ranker = self.artifact.ranker
        context = ranker.prepare_user_context(
            history_embeddings=[entry["article"]["embedding"] for entry in history],
            declared_topic_embedding=first.get("declared_topic_embedding"),
        )
        return [
            ranker.score(context.vector, record["article"]["embedding"])
            for record in records
        ]


@dataclass(frozen=True)
class RankingDecision:
    items: list[RecommendationItem]
    model_version: str
    fallback_used: bool


@dataclass
class RankerRuntime:
    mode: RankerMode
    predictor: Predictor | None = None
    _inflight: asyncio.Task | None = field(default=None, init=False, repr=False)

    @classmethod
    def initialize(cls, mode: RankerMode, artifact_path: Path) -> RankerRuntime:
        if mode == "heuristic":
            return cls(mode=mode)
        try:
            manifest = json.loads((artifact_path / "manifest.json").read_text())
            predictor = (
                NRMSArtifactPredictor.load(artifact_path)
                if manifest.get("model_type") == "nrms-like-impression-ranker"
                else ModelArtifactPredictor.load(artifact_path)
            )
        except Exception as error:
            MODEL_LOADS.labels(mode=mode, status="error").inc()
            MODEL_FALLBACKS.labels(mode=mode, reason="load_error").inc()
            logger.error(
                "recommendation_model_load_failed",
                extra={
                    "ranker_mode": mode,
                    "artifact_path": str(artifact_path),
                    "error_type": type(error).__name__,
                },
            )
            return cls(mode=mode)
        MODEL_LOADS.labels(mode=mode, status="success").inc()
        return cls(mode=mode, predictor=predictor)

    def fallback(self, items: list[RecommendationItem], reason: str) -> RankingDecision:
        MODEL_FALLBACKS.labels(mode=self.mode, reason=reason).inc()
        return RankingDecision(items, HEURISTIC_MODEL_VERSION, True)

    async def score_async(
        self,
        items: list[RecommendationItem],
        *,
        timeout_seconds: float = 0.15,
        records: Sequence[Mapping[str, Any]] | None = None,
    ) -> RankingDecision:
        if self.mode == "heuristic" or self.predictor is None:
            return self.score(items)
        if self._inflight is not None and not self._inflight.done():
            return self.fallback(items, "busy")
        # Shield the worker: a timed-out thread still occupies the single slot
        # until completion. Subsequent requests fall back instead of queuing.
        task = asyncio.create_task(
            asyncio.to_thread(self.score, items, records=records)
        )
        self._inflight = task
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout_seconds)
        except TimeoutError:
            return self.fallback(items, "timeout")

    def score(
        self,
        items: list[RecommendationItem],
        *,
        feed_source: str = "personalized",
        records: Sequence[Mapping[str, Any]] | None = None,
    ) -> RankingDecision:
        if self.mode == "heuristic":
            return RankingDecision(items, HEURISTIC_MODEL_VERSION, False)
        if self.predictor is None:
            return RankingDecision(items, HEURISTIC_MODEL_VERSION, True)

        if getattr(self.predictor, "requires_context", False) and records is None:
            return self.fallback(items, "missing_context")
        if records is None:
            records = []
            for item in items:
                snapshot = item.features.model_dump()
                snapshot["feed_source"] = feed_source
                records.append({name: snapshot[name] for name in FEATURE_COLUMNS})
        try:
            if len(records) != len(items):
                raise ValueError("model context count does not match candidates")
            scores = self.predictor.predict_scores(records)
            if len(scores) != len(items) or any(
                not math.isfinite(score) or not 0.0 <= score <= 1.0 for score in scores
            ):
                raise ValueError("model returned invalid probability scores")
        except Exception as error:
            MODEL_PREDICTIONS.labels(mode=self.mode, status="error").inc()
            MODEL_FALLBACKS.labels(mode=self.mode, reason="predict_error").inc()
            logger.error(
                "recommendation_model_predict_failed",
                extra={
                    "ranker_mode": self.mode,
                    "model_version": self.predictor.model_version,
                    "error_type": type(error).__name__,
                },
            )
            return RankingDecision(items, HEURISTIC_MODEL_VERSION, True)

        MODEL_PREDICTIONS.labels(mode=self.mode, status="success").inc()
        updated = [
            item.model_copy(
                update={
                    "score": score if self.mode == "ml" else item.score,
                    "reason": (
                        f"ml:{self.predictor.model_version}"
                        if self.mode == "ml"
                        else item.reason
                    ),
                    "features": item.features.model_copy(update={"ml_score": score}),
                }
            )
            for item, score in zip(items, scores, strict=True)
        ]
        model_version = (
            self.predictor.model_version
            if self.mode == "ml"
            else f"{HEURISTIC_MODEL_VERSION}+shadow:{self.predictor.model_version}"
        )
        return RankingDecision(updated, model_version, False)
