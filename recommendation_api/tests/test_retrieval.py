from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from app import features
from app.schemas import CandidatePost


def candidate():
    return CandidatePost(id=uuid4(), author_id=uuid4(), topics=[], safety_score=1,
                         created_at=datetime.now(timezone.utc), source='recent')


@pytest.mark.asyncio
async def test_underfilled_sources_backfill_after_dedup(monkeypatch):
    posts = [candidate() for _ in range(6)]
    monkeypatch.setattr(features, 'record_candidate_exclusions', AsyncMock())
    monkeypatch.setattr(features, 'candidates_from_followed', AsyncMock(return_value=[posts[0]]))
    monkeypatch.setattr(features, 'candidates_from_topics', AsyncMock(return_value=[posts[0]]))
    async def recent(db, uid, limit, **kwargs):
        return posts[:limit]
    monkeypatch.setattr(features, 'candidates_recent', recent)
    result = await features.gather_candidates(None, uuid4(), {}, 6, seen_cooldown_days=7)
    assert len(result) == 6
    assert len({p.id for p in result}) == 6


@pytest.mark.asyncio
async def test_candidate_telemetry_is_sampled_and_keeps_engagement_labels_out():
    from app.retrieval_telemetry import record_pool, sampled
    request = uuid4()
    assert not sampled(request, 0)
    assert sampled(request, 1)
    assert sampled(request, .1) == sampled(request, .1)
    db = SimpleNamespace(pool=SimpleNamespace(executemany=AsyncMock()))
    await record_pool(db, request, [candidate()], model_version='heuristic-v1', sample_rate=0)
    db.pool.executemany.assert_not_awaited()
    await record_pool(db, request, [candidate()], model_version='heuristic-v1', sample_rate=1)
    query, rows = db.pool.executemany.call_args.args
    assert 'recommendation_candidate_events' in query
    assert rows[0][0] == request
    assert 'click_label' not in query and 'utility_label' not in query
