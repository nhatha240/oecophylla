from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import joblib
import numpy as np
import pytest
from app import main
from app.model_ranker import (
    FEATURE_COLUMNS,
    ModelArtifactPredictor,
    RankerRuntime,
)
from app.schemas import (
    CandidatePost,
    RankFeatureSnapshot,
    RecommendationItem,
    RecommendFeedRequest,
)
from sklearn.dummy import DummyClassifier
from sklearn.pipeline import Pipeline

REPO_ROOT = Path(__file__).parents[2]


class StubPredictor:
    model_version = "logreg-v1"

    def __init__(
        self, scores: list[float] | None = None, error: Exception | None = None
    ):
        self.scores = scores or []
        self.error = error
        self.calls = 0

    def predict_scores(self, records):
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert all("label" not in record for record in records)
        return self.scores


def _item(index: int, score: float) -> RecommendationItem:
    return RecommendationItem(
        post_id=UUID(f"00000000-0000-0000-0000-{index:012d}"),
        score=score,
        source="topic",
        reason="heuristic",
        features=RankFeatureSnapshot(
            schema_version="rank-features-v1",
            topic_relevance=score,
            freshness=0.8,
            safety_score=1.0,
            candidate_source="topic",
            is_followed_author=None,
            author_affinity=None,
            heuristic_score=score,
            ml_score=None,
        ),
    )


def test_heuristic_mode_does_not_require_or_load_artifact(tmp_path: Path):
    runtime = RankerRuntime.initialize("heuristic", tmp_path / "missing")

    decision = runtime.score([_item(1, 0.8), _item(2, 0.2)])

    assert [item.score for item in decision.items] == [0.8, 0.2]
    assert decision.model_version == "heuristic-v1"
    assert decision.fallback_used is False


def test_ml_mode_uses_artifact_scores_and_model_version():
    predictor = StubPredictor([0.1, 0.9])
    runtime = RankerRuntime(mode="ml", predictor=predictor)

    decision = runtime.score([_item(1, 0.8), _item(2, 0.2)])

    assert [item.score for item in decision.items] == [0.1, 0.9]
    assert [item.features.ml_score for item in decision.items] == [0.1, 0.9]
    assert decision.model_version == "logreg-v1"
    assert predictor.calls == 1


def test_shadow_mode_records_ml_scores_without_changing_heuristic_order():
    predictor = StubPredictor([0.1, 0.9])
    runtime = RankerRuntime(mode="shadow", predictor=predictor)

    decision = runtime.score([_item(1, 0.8), _item(2, 0.2)])

    assert [item.post_id for item in decision.items] == [
        _item(1, 0.8).post_id,
        _item(2, 0.2).post_id,
    ]
    assert [item.score for item in decision.items] == [0.8, 0.2]
    assert [item.features.ml_score for item in decision.items] == [0.1, 0.9]
    assert decision.model_version == "heuristic-v1+shadow:logreg-v1"


def test_prediction_failure_falls_back_to_heuristic_without_raising():
    predictor = StubPredictor(error=RuntimeError("predict failed"))
    runtime = RankerRuntime(mode="ml", predictor=predictor)

    decision = runtime.score([_item(1, 0.8), _item(2, 0.2)])

    assert [item.score for item in decision.items] == [0.8, 0.2]
    assert decision.model_version == "heuristic-v1"
    assert decision.fallback_used is True


def test_load_failure_falls_back_before_requests(tmp_path: Path):
    runtime = RankerRuntime.initialize("ml", tmp_path / "missing")

    decision = runtime.score([_item(1, 0.8)])

    assert decision.model_version == "heuristic-v1"
    assert decision.fallback_used is True


def test_serving_loader_validates_and_predicts_artifact(tmp_path: Path):
    pipeline = Pipeline([("classifier", DummyClassifier(strategy="prior"))])
    matrix = np.asarray(
        [
            [0.1, 0.8, 1.0, np.nan, 0.2, "personalized", "topic", None],
            [0.9, 0.8, 1.0, 0.7, 0.8, "personalized", "follow", True],
        ],
        dtype=object,
    )
    pipeline.fit(matrix, [0, 1])
    model_path = tmp_path / "model.joblib"
    joblib.dump(pipeline, model_path)
    checksum = hashlib.sha256(model_path.read_bytes()).hexdigest()
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "artifact_schema_version": "recommendation-model-artifact-v1",
                "feature_schema_version": "rank-features-v1",
                "feature_columns": list(FEATURE_COLUMNS),
                "model_version": "fixture-v1",
                "files": {"model.joblib": {"sha256": checksum}},
            }
        )
    )

    predictor = ModelArtifactPredictor.load(tmp_path)
    scores = predictor.predict_scores(
        [
            {
                "topic_relevance": 0.5,
                "freshness": 0.8,
                "safety_score": 1.0,
                "author_affinity": None,
                "heuristic_score": 0.5,
                "feed_source": "personalized",
                "candidate_source": "unknown-source",
                "is_followed_author": None,
            }
        ]
    )

    assert predictor.model_version == "fixture-v1"
    assert len(scores) == 1
    assert 0.0 <= scores[0] <= 1.0


@pytest.mark.asyncio
async def test_recommend_endpoint_wires_ml_scores_before_diversity(monkeypatch):
    candidates = [
        CandidatePost(
            id=UUID(f"00000000-0000-0000-0000-{index:012d}"),
            author_id=uuid4(),
            topics=[f"topic-{index}"],
            safety_score=1.0,
            created_at=datetime.now(timezone.utc),
            source="topic",
        )
        for index in (1, 2)
    ]
    monkeypatch.setattr(main, "fetch_user_vector", AsyncMock(return_value={"x": 1.0}))
    monkeypatch.setattr(main, "gather_candidates", AsyncMock(return_value=candidates))
    main.app.state.db = object()
    main.app.state.redis = object()
    main.app.state.cfg = SimpleNamespace(
        feed_candidate_pool=100,
        seen_cooldown_days=7,
        half_life_hours=36.0,
    )
    main.app.state.ranker = RankerRuntime(
        mode="ml", predictor=StubPredictor([0.1, 0.9])
    )

    response = await main.recommend_feed(uuid4(), RecommendFeedRequest(limit=2))

    assert response.model_version == "logreg-v1"
    assert response.items[0].post_id == candidates[1].id
    assert response.items[0].features.ml_score == 0.9


def test_container_and_deployments_use_compatible_read_only_artifact_mount():
    runtime_requirements = (
        REPO_ROOT / "recommendation_api" / "requirements.runtime.txt"
    ).read_text()
    dockerfile = (REPO_ROOT / "recommendation_api" / "Dockerfile").read_text()
    compose = (REPO_ROOT / "compose.yaml").read_text()
    deployment = (
        REPO_ROOT / "charts" / "oecophylla" / "templates" / "deployments.yaml"
    ).read_text()

    assert "scikit-learn" in runtime_requirements
    assert "joblib" in runtime_requirements
    assert "artifacts/models" not in dockerfile
    assert "MODEL_ARTIFACT_PATH" in compose
    assert ":/models:ro" in compose
    assert "modelArtifact" in deployment
    assert "readOnly: true" in deployment
