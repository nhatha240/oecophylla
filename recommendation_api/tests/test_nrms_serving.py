"""Request-level NRMS safety: no partial score or queued timeout work."""
import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
from datetime import datetime, timezone, timedelta

import pytest
from app.model_ranker import RankerRuntime
from app.schemas import CandidatePost
from test_model_ranker import _item, StubPredictor


@pytest.mark.asyncio
async def test_async_shadow_keeps_order_and_scores():
    runtime = RankerRuntime('shadow', StubPredictor([0.1, 0.9]))
    items = [_item(1, 0.8), _item(2, 0.2)]
    decision = await runtime.score_async(items, timeout_seconds=0.2)
    assert [i.score for i in decision.items] == [0.8, 0.2]
    assert [i.features.ml_score for i in decision.items] == [0.1, 0.9]
    assert not decision.fallback_used


@pytest.mark.asyncio
async def test_timeout_falls_back_atomically_and_does_not_queue_more_work():
    released = threading.Event()
    class Slow(StubPredictor):
        def predict_scores(self, records):
            self.calls += 1
            released.wait(2)
            return [0.99]
    predictor = Slow()
    runtime = RankerRuntime('ml', predictor)
    items = [_item(1, 0.4)]
    try:
        decision = await runtime.score_async(items, timeout_seconds=0.01)
        again = await runtime.score_async(items, timeout_seconds=0.01)
        assert decision.fallback_used and again.fallback_used
        assert decision.items[0].score == 0.4
        assert decision.items[0].features.ml_score is None
        assert predictor.calls == 1
    finally:
        released.set()
        await asyncio.sleep(0.03)
    assert not (await runtime.score_async(items, timeout_seconds=0.1)).fallback_used


@pytest.mark.asyncio
async def test_missing_nrms_context_falls_back_without_predicting():
    predictor = StubPredictor([0.9])
    predictor.requires_context = True
    runtime = RankerRuntime('shadow', predictor)
    result = await runtime.score_async([_item(1, 0.4)], timeout_seconds=0.1)
    assert result.fallback_used
    assert predictor.calls == 0


@pytest.mark.asyncio
async def test_context_checks_content_revision_and_prior_history(monkeypatch):
    from app import serving_context
    from workers.nlp_worker.app.content_features import content_hash
    at = datetime.now(timezone.utc)
    candidate = CandidatePost(id=uuid4(), author_id=uuid4(), topics=['tech'],
                              content='Current article', created_at=at-timedelta(days=1),
                              source='topic', safety_score=1)
    feature = dict(post_id=candidate.id, embedding=[1., 0.],
                   content_hash=content_hash(candidate.content),
                   encoder_version='test@1', source_updated_at=at-timedelta(hours=1),
                   computed_at=at-timedelta(minutes=1))
    db = SimpleNamespace(pool=SimpleNamespace(fetch=AsyncMock(return_value=[feature])))
    monkeypatch.setattr(serving_context, 'fetch_user_history', AsyncMock(return_value=SimpleNamespace(entries=[])))
    kwargs = dict(db=db, redis=None, user_id=uuid4(), candidates=[candidate],
                  observed_at=at, encoder_version='test@1', dimension=2, config=None)
    records = await serving_context.load_nrms_records(**kwargs)
    assert records[0]['history'] == []
    assert records[0]['article']['embedding'] == [1., 0.]
    assert db.pool.fetch.await_count == 1
    feature['content_hash'] = '0'*64
    with pytest.raises(ValueError, match='feature'):
        await serving_context.load_nrms_records(**kwargs)
    feature['content_hash'] = content_hash(candidate.content)
    feature['computed_at'] = at+timedelta(seconds=1)
    with pytest.raises(ValueError, match='feature'):
        await serving_context.load_nrms_records(**kwargs)
