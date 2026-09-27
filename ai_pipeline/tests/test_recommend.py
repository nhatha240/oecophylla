import numpy as np
import pytest
from dataclasses import replace

from ai_pipeline import recommend
from ai_pipeline.model import NRMSArchitecture, NRMSLikeRanker


def initialize_ranker(architecture, popular):
    model = NRMSLikeRanker.initialize(architecture, popular_embedding=popular)
    return replace(model, query_projection=np.zeros((2, 8, 4)), value_projection=np.stack([np.eye(8)[:, :4], np.eye(8)[:, 4:]]))


def test_recommends_eligible_friend_and_news_posts_from_history():
    ranker = initialize_ranker(NRMSArchitecture(8, 2, 4, 7, 0), np.eye(8)[0])
    texts = {"AI history": np.eye(8)[0], "friend AI": np.eye(8)[0], "news AI": np.eye(8)[0], "sports": np.eye(8)[1]}
    result = recommend.recommend_posts(ranker, {"history": ["AI history"], "candidates": [
        {"id": "sport", "text": "sports", "source": "news"},
        {"id": "friend", "text": "friend AI", "source": "following"},
        {"id": "news", "text": "news AI", "source": "news"},
    ]}, encode=lambda values: np.array([texts[v] for v in values]))
    assert [r["id"] for r in result["recommendations"]] == ["friend", "news", "sport"]
    assert result["based_on"] == "history"
    assert result["recommendations"][0]["source"] == "following"


def test_cold_user_uses_declared_interests_without_fake_clicks():
    ranker = initialize_ranker(NRMSArchitecture(8, 2, 4, 7, 0), np.eye(8)[0])
    payload = {"history": [], "interests": ["sports"], "candidates": [{"id": "1", "text": "sports"}]}
    result = recommend.recommend_posts(ranker, payload, encode=lambda values: np.array([np.eye(8)[1] for _ in values]))
    assert result["based_on"] == "declared_topics"
    assert result["history_used"] == 0


def test_candidate_validation_and_encoder_contract():
    ranker = initialize_ranker(NRMSArchitecture(8, 2, 4, 7, 0), np.eye(8)[0])
    with pytest.raises(ValueError, match="unique"):
        recommend.recommend_posts(ranker, {"candidates": [{"id": "1", "text": "x"}, {"id": "1", "text": "x"}]}, encode=lambda _: None)
    with pytest.raises(ValueError, match="embedding"):
        recommend.recommend_posts(ranker, {"candidates": [{"id": "1", "text": "x"}]}, encode=lambda _: np.ones((1, 8)))
