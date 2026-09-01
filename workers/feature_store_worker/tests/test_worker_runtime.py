from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app import main
from app.main import Worker, _event_id, _extract_user, _occurred_at


class Closeable:
    def __init__(self) -> None:
        self.close = AsyncMock()


class FakeConsumer(Closeable):
    def __init__(self, **kwargs) -> None:
        super().__init__()
        self.kwargs = kwargs
        self.start = AsyncMock()
        self.stop = AsyncMock()


async def test_worker_starts_and_stops_all_runtime_resources(monkeypatch):
    pool = Closeable()
    redis = Closeable()
    consumer = FakeConsumer()
    metrics_server = Mock()

    monkeypatch.setattr(main.asyncpg, "create_pool", AsyncMock(return_value=pool))
    monkeypatch.setattr(main.redis_async, "from_url", Mock(return_value=redis))
    monkeypatch.setattr(main, "AIOKafkaConsumer", Mock(return_value=consumer))
    monkeypatch.setattr(
        main, "start_http_server", Mock(return_value=(metrics_server, Mock()))
    )
    worker = Worker()

    await worker.start()
    await worker.stop()

    consumer.start.assert_awaited_once()
    consumer.stop.assert_awaited_once()
    redis.close.assert_awaited_once()
    pool.close.assert_awaited_once()
    metrics_server.shutdown.assert_called_once()
    metrics_server.server_close.assert_called_once()
    deserialize = main.AIOKafkaConsumer.call_args.kwargs["value_deserializer"]
    assert deserialize(b'{"event_type":"liked"}') == {"event_type": "liked"}


async def test_startup_backfill_finishes_before_kafka_consumer_joins(monkeypatch):
    order: list[str] = []
    pool = Closeable()
    redis = Closeable()
    consumer = FakeConsumer()
    consumer.start = AsyncMock(side_effect=lambda: order.append("consumer"))
    metrics_server = Mock()

    monkeypatch.setattr(main.asyncpg, "create_pool", AsyncMock(return_value=pool))
    monkeypatch.setattr(main.redis_async, "from_url", Mock(return_value=redis))
    monkeypatch.setattr(main, "AIOKafkaConsumer", Mock(return_value=consumer))
    monkeypatch.setattr(
        main, "start_http_server", Mock(return_value=(metrics_server, Mock()))
    )
    worker = Worker()
    worker.cfg = worker.cfg.model_copy(update={"preference_backfill_on_start": True})
    worker._backfill_v2 = AsyncMock(side_effect=lambda: order.append("backfill"))

    await worker.start()
    await worker.stop()

    assert order == ["backfill", "consumer"]


async def test_run_flushes_records_commits_and_flushes_again_on_cancel():
    event = {"event_type": "visible"}

    class RunConsumer:
        def __init__(self) -> None:
            self.calls = 0
            self.commits = 0

        async def getmany(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return {"partition": [SimpleNamespace(value=event)]}
            raise asyncio.CancelledError

        async def commit(self) -> None:
            self.commits += 1

    worker = Worker()
    consumer = RunConsumer()
    worker.consumer = consumer  # type: ignore[assignment]
    worker._should_flush = Mock(return_value=True)  # type: ignore[method-assign]
    worker._flush = AsyncMock(return_value=True)  # type: ignore[method-assign]

    with pytest.raises(asyncio.CancelledError):
        await worker.run()

    assert worker._buffer == [event]
    assert worker._flush.await_count == 2
    assert consumer.commits == 2


async def test_empty_flush_and_batch_size_flush_decision():
    worker = Worker()
    assert await worker._flush() is True

    worker._buffer = [{}] * worker.cfg.flush_batch_size
    assert worker._should_flush() is True


async def test_trending_is_updated_as_an_approximate_weighted_projection():
    class Pipeline:
        def __init__(self) -> None:
            self.increments: list[tuple[str, float, str]] = []
            self.expiry: tuple[str, int] | None = None
            self.executed = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            pass

        def zincrby(self, key: str, delta: float, post_id: str) -> None:
            self.increments.append((key, delta, post_id))

        def expire(self, key: str, ttl: int) -> None:
            self.expiry = (key, ttl)

        async def execute(self) -> None:
            self.executed = True

    pipe = Pipeline()
    worker = Worker()
    worker.redis = SimpleNamespace(pipeline=lambda: pipe)  # type: ignore[assignment]

    await worker._update_trending(
        [
            {"event_type": "liked", "data": {"post_id": "post-1"}},
            {"event_type": "hidden", "data": {"post_id": "post-2"}},
            {"event_type": "liked", "data": {}},
        ]
    )

    assert pipe.increments == [
        ("trending:24h", 1.5, "post-1"),
        ("trending:24h", -2.0, "post-2"),
    ]
    assert pipe.expiry == ("trending:24h", worker.cfg.trending_ttl_seconds)
    assert pipe.executed is True


def test_envelope_helpers_handle_legacy_users_and_malformed_values():
    assert _extract_user({"data": {"reporter_id": "user-1"}}) == "user-1"
    assert _extract_user({"data": {}}) is None
    assert _event_id({"event_id": "not-a-uuid"}) is None
    assert _occurred_at({"occurred_at": "2026-08-28T03:15:00"}).tzinfo is not None
    assert _occurred_at({"occurred_at": "invalid"}).tzinfo is not None
