import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app import kafka_consumer
from app.embedding_worker import ProcessResult
from app.settings import Settings


class FakeConsumer:
    def __init__(self, envelope: dict) -> None:
        self._envelope = envelope
        self._iterated = False
        self._getmany_calls = 0
        self.commit_calls = 0
        self.stop_calls = 0

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        self.stop_calls += 1

    async def commit(self) -> None:
        self.commit_calls += 1

    async def getmany(self, timeout_ms: int, max_records: int) -> dict:
        del max_records
        self._getmany_calls += 1
        if self._getmany_calls == 1:
            return {"fake-topic": [SimpleNamespace(value=self._envelope)]}
        await asyncio.sleep(timeout_ms / 1000)
        return {}

    def __aiter__(self) -> "FakeConsumer":
        return self

    async def __anext__(self) -> SimpleNamespace:
        if not self._iterated:
            self._iterated = True
            return SimpleNamespace(value=self._envelope)
        await asyncio.sleep(3600)
        raise StopAsyncIteration


@pytest.mark.asyncio
async def test_run_consumer_flushes_single_message_after_interval(monkeypatch):
    envelope = {"data": {"post_id": "00000000-0000-0000-0000-000000000003"}}
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": "00000000-0000-0000-0000-000000000003",
        "content": "Bài viết về trí tuệ nhân tạo",
        "topics": [],
        "updated_at": datetime(2026, 8, 31, tzinfo=UTC),
    }
    conn.fetchval.return_value = False
    conn.execute.return_value = "UPDATE 1"

    consumer = FakeConsumer(envelope)
    monkeypatch.setattr(kafka_consumer.asyncpg, "connect", AsyncMock(return_value=conn))
    consumer_kwargs: dict = {}

    def build_consumer(*args, **kwargs):
        del args
        consumer_kwargs.update(kwargs)
        return consumer

    monkeypatch.setattr(kafka_consumer, "AIOKafkaConsumer", build_consumer)

    cfg = Settings(flush_interval_seconds=0.01, flush_batch_size=50)
    task = asyncio.create_task(kafka_consumer.run_consumer(cfg))
    await asyncio.sleep(0.05)

    try:
        conn.execute.assert_called_once()
        assert consumer_kwargs["enable_auto_commit"] is False
        assert consumer.commit_calls == 1
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_batch_failure_propagates_before_later_messages_are_processed(monkeypatch):
    process_one = AsyncMock(side_effect=RuntimeError("inference unavailable"))
    monkeypatch.setattr(kafka_consumer, "_process_one", process_one)
    messages = [
        SimpleNamespace(value={"data": {"post_id": "first"}}),
        SimpleNamespace(value={"data": {"post_id": "second"}}),
    ]

    with pytest.raises(RuntimeError, match="inference unavailable"):
        await kafka_consumer._process_batch(AsyncMock(), messages)

    process_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_processing_failure_is_not_retried_during_cleanup(monkeypatch):
    envelope = {"data": {"post_id": "00000000-0000-0000-0000-000000000004"}}
    conn = AsyncMock()
    consumer = FakeConsumer(envelope)
    monkeypatch.setattr(kafka_consumer.asyncpg, "connect", AsyncMock(return_value=conn))
    monkeypatch.setattr(kafka_consumer, "AIOKafkaConsumer", lambda *args, **kwargs: consumer)
    monkeypatch.setattr(kafka_consumer, "build_service", lambda *_args: (object(), object()))
    process_batch = AsyncMock(side_effect=RuntimeError("storage unavailable"))
    monkeypatch.setattr(kafka_consumer, "_process_batch", process_batch)

    with pytest.raises(RuntimeError, match="storage unavailable"):
        await kafka_consumer._run_once(
            Settings(flush_interval_seconds=0.01, flush_batch_size=1)
        )

    process_batch.assert_awaited_once()
    assert consumer.commit_calls == 0
    assert consumer.stop_calls == 1
    conn.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_consumer_start_failure_still_closes_resources(monkeypatch):
    conn = AsyncMock()
    consumer = FakeConsumer({})
    consumer.start = AsyncMock(side_effect=RuntimeError("broker unavailable"))
    monkeypatch.setattr(kafka_consumer.asyncpg, "connect", AsyncMock(return_value=conn))
    monkeypatch.setattr(kafka_consumer, "AIOKafkaConsumer", lambda *args, **kwargs: consumer)

    with pytest.raises(RuntimeError, match="broker unavailable"):
        await kafka_consumer._run_once(Settings())

    assert consumer.stop_calls == 1
    conn.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_topic_fallback_is_acknowledged_for_later_rebuild(monkeypatch):
    envelope = {"data": {"post_id": "00000000-0000-0000-0000-000000000005"}}
    conn = AsyncMock()
    consumer = FakeConsumer(envelope)
    service = AsyncMock()
    service.process.return_value = ProcessResult("fallback")
    repository = AsyncMock()
    repository.get_post.return_value = SimpleNamespace()
    monkeypatch.setattr(kafka_consumer.asyncpg, "connect", AsyncMock(return_value=conn))
    monkeypatch.setattr(kafka_consumer, "AIOKafkaConsumer", lambda *args, **kwargs: consumer)
    monkeypatch.setattr(kafka_consumer, "build_service", lambda *_args: (service, repository))

    task = asyncio.create_task(
        kafka_consumer._run_once(
            Settings(flush_interval_seconds=0.01, flush_batch_size=1)
        )
    )
    for _ in range(20):
        if consumer.commit_calls == 1:
            break
        await asyncio.sleep(0.01)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    service.process.assert_awaited_once()
    assert consumer.commit_calls == 1
