from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass
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
class RankingDecision:
    items: list[RecommendationItem]
    model_version: str
    fallback_used: bool


@dataclass(frozen=True)
class RankerRuntime:
    mode: RankerMode
    predictor: Predictor | None = None

    @classmethod
    def initialize(cls, mode: RankerMode, artifact_path: Path) -> RankerRuntime:
        if mode == "heuristic":
            return cls(mode=mode)
        try:
            predictor = ModelArtifactPredictor.load(artifact_path)
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

    def score(
        self,
        items: list[RecommendationItem],
        *,
        feed_source: str = "personalized",
    ) -> RankingDecision:
        if self.mode == "heuristic":
            return RankingDecision(items, HEURISTIC_MODEL_VERSION, False)
        if self.predictor is None:
            return RankingDecision(items, HEURISTIC_MODEL_VERSION, True)

        records = []
        for item in items:
            snapshot = item.features.model_dump()
            snapshot["feed_source"] = feed_source
            records.append({name: snapshot[name] for name in FEATURE_COLUMNS})
        try:
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
