"""Fixture integration trace, explicitly not production/live release evidence."""

from types import SimpleNamespace
from datetime import timedelta

import pytest
from ai_pipeline.build_dataset import build_ranking_samples_v2, build_history_snapshot
from ai_pipeline.tests.test_dataset_v2 import (
    _load_local_fixture,
    config as config_fixture,
    ENCODER,
)
from ai_pipeline.model import NRMSArchitecture, NRMSLikeRanker
from app.model_ranker import NRMSArtifactPredictor, RankerRuntime
from test_model_ranker import _item


@pytest.mark.asyncio
async def test_served_behavior_dataset_history_to_shadow_score():
    _, impressions, events, features = _load_local_fixture()
    config = config_fixture.__wrapped__()
    result = build_ranking_samples_v2(impressions, events, features, config)
    clicked = next(row for row in result.rows if row.click_label == 1)
    assert clicked.served and clicked.visible
    assert any(row.utility_label_name == "qualified_read" for row in result.rows)
    later = max(i.served_at for i in impressions) + timedelta(seconds=10)
    snapshot = build_history_snapshot(
        impressions[0].user_id, later, events, features, config
    )
    assert all(entry.engaged_at < later for entry in snapshot.entries)
    # The shared builder feeds the same ordered embedding history to offline
    # inference and the serving predictor; shadow never replaces display scores.
    model = NRMSLikeRanker.initialize(
        NRMSArchitecture(
            embedding_dimension=384, attention_heads=2, history_length=20, seed=42
        )
    )
    predictor = NRMSArtifactPredictor(
        SimpleNamespace(ranker=model), "trace-nrms", ENCODER, 384
    )
    runtime = RankerRuntime("shadow", predictor)
    record = clicked.to_record()
    expected = model.predict_scores([record])[0]
    item = _item(1, 0.6)
    decision = await runtime.score_async([item], records=[record], timeout_seconds=0.4)
    assert not decision.fallback_used
    assert decision.items[0].score == 0.6
    assert decision.items[0].features.ml_score == pytest.approx(expected)
    assert decision.model_version == "heuristic-v1+shadow:trace-nrms"
