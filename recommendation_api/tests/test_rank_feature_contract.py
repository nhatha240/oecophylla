from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.ranking import build_rank_feature_snapshot
from app.schemas import (
    CandidatePost,
    RankFeatureSnapshot,
    RecommendationItem,
    RecommendFeedResponse,
)


def _candidate() -> CandidatePost:
    return CandidatePost(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        author_id=uuid4(),
        topics=["ai", "tech"],
        safety_score=0.9,
        created_at=datetime.now(timezone.utc),
        source="topic",
    )


def test_rank_snapshot_contains_once_computed_heuristic_signals():
    snapshot = build_rank_feature_snapshot({"ai": 1.0}, _candidate())

    assert snapshot.schema_version == "rank-features-v1"
    assert snapshot.topic_relevance == pytest.approx(1.0)
    assert snapshot.freshness is not None and snapshot.freshness > 0.99
    assert snapshot.safety_score == pytest.approx(0.9)
    assert snapshot.candidate_source == "topic"
    assert snapshot.is_followed_author is None
    assert snapshot.author_affinity is None
    assert snapshot.ml_score is None
    assert snapshot.heuristic_score == pytest.approx(
        0.5 * snapshot.topic_relevance
        + 0.2 * snapshot.freshness
        + 0.1 * snapshot.safety_score
    )


def test_rank_snapshot_uses_all_matching_topics_in_relevance():
    snapshot = build_rank_feature_snapshot(
        {"ai": 2.0, "tech": 1.0, "sports": 1.0},
        _candidate(),
    )

    assert snapshot.topic_relevance == pytest.approx(0.75)


def test_recommendation_response_serializes_versioned_snapshot_and_nulls():
    snapshot = build_rank_feature_snapshot({}, _candidate())
    response = RecommendFeedResponse(
        items=[
            RecommendationItem(
                post_id=_candidate().id,
                score=snapshot.heuristic_score,
                source="topic",
                reason="heuristic-rank",
                features=snapshot,
            )
        ],
        model_version="heuristic-v1",
        generated_at=datetime.now(timezone.utc),
    )

    payload = response.model_dump(mode="json")
    assert payload["model_version"] == "heuristic-v1"
    assert payload["items"][0]["features"]["schema_version"] == "rank-features-v1"
    assert payload["items"][0]["features"]["author_affinity"] is None
    assert payload["items"][0]["features"]["ml_score"] is None


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (RankFeatureSnapshot, {"candidate_source": "topic"}),
        (
            RankFeatureSnapshot,
            {"schema_version": "rank-features-v2", "candidate_source": "topic"},
        ),
        (
            RecommendationItem,
            {
                "post_id": "00000000-0000-0000-0000-000000000001",
                "score": 0.5,
                "source": "topic",
            },
        ),
        (
            RecommendFeedResponse,
            {"items": [], "generated_at": datetime.now(timezone.utc)},
        ),
    ],
)
def test_contract_rejects_missing_or_unsupported_versions(model, payload):
    with pytest.raises(ValidationError):
        model.model_validate(payload)
