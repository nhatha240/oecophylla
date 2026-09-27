from dataclasses import replace

import numpy as np
import pytest

from ai_pipeline import recommend
from ai_pipeline.model import NRMSArchitecture, NRMSLikeRanker


def initialize_ranker(architecture, popular):
    model = NRMSLikeRanker.initialize(architecture, popular_embedding=popular)
    return replace(
        model,
        query_projection=np.zeros((2, 8, 4)),
        value_projection=np.stack([np.eye(8)[:, :4], np.eye(8)[:, 4:]]),
    )


def test_recommends_eligible_friend_and_news_posts_from_history():
    ranker = initialize_ranker(NRMSArchitecture(8, 2, 4, 7, 0), np.eye(8)[0])
    texts = {
        "AI history": np.eye(8)[0],
        "friend AI": np.eye(8)[0],
        "news AI": np.eye(8)[0],
        "sports": np.eye(8)[1],
    }
    result = recommend.recommend_posts(
        ranker,
        {
            "history": ["AI history"],
            "candidates": [
                {"id": "sport", "text": "sports", "source": "news"},
                {"id": "friend", "text": "friend AI", "source": "following"},
                {"id": "news", "text": "news AI", "source": "news"},
            ],
        },
        encode=lambda values: np.array([texts[v] for v in values]),
    )
    assert [r["id"] for r in result["recommendations"]] == ["friend", "news", "sport"]
    assert result["based_on"] == "history"
    assert result["recommendations"][0]["source"] == "following"


def test_cold_user_uses_declared_interests_without_fake_clicks():
    ranker = initialize_ranker(NRMSArchitecture(8, 2, 4, 7, 0), np.eye(8)[0])
    payload = {
        "history": [],
        "interests": ["sports"],
        "candidates": [{"id": "1", "text": "sports"}],
    }
    result = recommend.recommend_posts(
        ranker, payload, encode=lambda values: np.array([np.eye(8)[1] for _ in values])
    )
    assert result["based_on"] == "declared_topics"
    assert result["history_used"] == 0


def test_candidate_validation_and_encoder_contract():
    ranker = initialize_ranker(NRMSArchitecture(8, 2, 4, 7, 0), np.eye(8)[0])
    with pytest.raises(ValueError, match="unique"):
        recommend.recommend_posts(
            ranker,
            {"candidates": [{"id": "1", "text": "x"}, {"id": "1", "text": "x"}]},
            encode=lambda _: None,
        )
    with pytest.raises(ValueError, match="embedding"):
        recommend.recommend_posts(
            ranker,
            {"candidates": [{"id": "1", "text": "x"}]},
            encode=lambda _: np.ones((1, 8)),
        )


def test_cli_checks_artifact_encoder_and_writes_recommendations(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace

    from ai_pipeline.artifact import LoadedNRMSArtifact
    from workers.nlp_worker.app import model
    from workers.nlp_worker.app.content_features import ENCODER_VERSION

    ranker = NRMSLikeRanker.initialize(
        NRMSArchitecture(384, 2, 4, 7), popular_embedding=np.eye(384)[0]
    )
    manifest = {
        "model_version": "test",
        "embedding": {"version": ENCODER_VERSION, "dimension": 384},
    }
    monkeypatch.setattr(
        recommend, "load_artifact", lambda _: LoadedNRMSArtifact(ranker, manifest)
    )

    def encode(texts, **kwargs):
        assert all(text.startswith("passage: ") for text in texts)
        return np.array([np.eye(384)[0] for _ in texts])

    monkeypatch.setattr(
        model,
        "PinnedSentenceEncoder",
        lambda *args, **kwargs: SimpleNamespace(
            _load=lambda: SimpleNamespace(encode=encode)
        ),
    )
    source = tmp_path / "input.json"
    source.write_text(json.dumps({"candidates": [{"id": "1", "text": "example"}]}))
    output = tmp_path / "out.json"
    args = [
        "--artifact",
        str(tmp_path),
        "--model-dir",
        str(tmp_path),
        "--input",
        str(source),
        "--output",
        str(output),
    ]
    assert recommend.main(args) == 0
    assert json.loads(output.read_text())["based_on"] == "popular_articles"
    manifest["embedding"]["version"] = "wrong"
    with pytest.raises(SystemExit):
        recommend.main(args)
