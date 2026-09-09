from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from app import features
from app.schemas import CandidatePost


def candidate():
    return CandidatePost(
        id=uuid4(),
        author_id=uuid4(),
        topics=[],
        safety_score=1,
        created_at=datetime.now(timezone.utc),
        source="recent",
    )


@pytest.mark.asyncio
async def test_underfilled_sources_backfill_after_dedup(monkeypatch):
    posts = [candidate() for _ in range(6)]
    monkeypatch.setattr(features, "record_candidate_exclusions", AsyncMock())
    monkeypatch.setattr(
        features, "candidates_from_followed", AsyncMock(return_value=[posts[0]])
    )
    monkeypatch.setattr(
        features, "candidates_from_topics", AsyncMock(return_value=[posts[0]])
    )

    async def recent(db, uid, limit, **kwargs):
        return posts[:limit]

    monkeypatch.setattr(features, "candidates_recent", recent)
    result = await features.gather_candidates(
        None, uuid4(), {}, 6, seen_cooldown_days=7
    )
    assert len(result) == 6
    assert len({p.id for p in result}) == 6


@pytest.mark.asyncio
async def test_candidate_telemetry_is_sampled_and_keeps_engagement_labels_out():
    from app.retrieval_telemetry import record_pool, sampled

    request = uuid4()
    assert not sampled(request, 0)
    assert sampled(request, 1)
    assert sampled(request, 0.1) == sampled(request, 0.1)
    db = SimpleNamespace(pool=SimpleNamespace(executemany=AsyncMock()))
    await record_pool(
        db, request, [candidate()], model_version="heuristic-v1", sample_rate=0
    )
    db.pool.executemany.assert_not_awaited()
    await record_pool(
        db, request, [candidate()], model_version="heuristic-v1", sample_rate=1
    )
    query, rows = db.pool.executemany.call_args.args
    assert "recommendation_candidate_events" in query
    assert rows[0][0] == request
    assert "click_label" not in query and "utility_label" not in query


def test_cached_served_requests_join_original_pool_without_creating_negatives():
    from ai_pipeline.retrieval_analysis import analyze_retrieval

    generation, post, unserved = uuid4(), uuid4(), uuid4()
    candidates = [
        dict(retrieval_request_id=generation, post_id=p, stage="eligible")
        for p in [post, unserved]
    ]
    impressions = [
        dict(
            request_id=uuid4(),
            post_id=post,
            feature_snapshot=dict(retrieval_request_id=str(generation)),
        )
        for _ in range(2)
    ]
    report = analyze_retrieval(candidates, impressions, hash_salt="test")
    assert report["served_pool_membership"] == 1
    assert report["counts"]["served"] == 2
    assert not report["engagement_labels_derived"]
    assert str(post) not in str(report) and str(unserved) not in str(report)


@pytest.mark.asyncio
async def test_semantic_source_rejects_stale_article_revision(monkeypatch):
    import app.db
    from workers.nlp_worker.app.content_features import ENCODER_VERSION, content_hash

    post = candidate().model_copy(update=dict(content="A current article"))
    vector = [1.0] + [0.0] * 383
    monkeypatch.setattr(
        app.db,
        "fetch_user_history",
        AsyncMock(
            return_value=SimpleNamespace(
                entries=[
                    SimpleNamespace(embedding=vector, encoder_version=ENCODER_VERSION)
                ]
            )
        ),
    )
    row = dict(
        id=post.id,
        author_id=post.author_id,
        topics=[],
        safety_score=1,
        created_at=post.created_at,
        content=post.content,
        embedding=vector,
        content_hash=content_hash(post.content),
    )
    db = SimpleNamespace(pool=SimpleNamespace(fetch=AsyncMock(return_value=[row])))
    cfg = SimpleNamespace(seen_cooldown_days=7, feed_candidate_pool=300)
    good = await features.candidates_semantic(
        db, None, uuid4(), config=cfg, observed_at=post.created_at
    )
    assert good[0].source == "semantic" and good[0].retrieval_score == 1
    row["content_hash"] = "0" * 64
    assert not await features.candidates_semantic(
        db, None, uuid4(), config=cfg, observed_at=post.created_at
    )
    query = db.pool.fetch.call_args.args[0]
    for required in [
        "reports r",
        "interactions i",
        "behavior_events b",
        "author.is_active = true",
        "p.status = 'published'",
    ]:
        assert required in query
