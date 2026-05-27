import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.kafka_consumer as kafka_consumer
from app.settings import Settings


class FakeConsumer:
    def __init__(self, envelope: dict) -> None:
        self._envelope = envelope
        self._iterated = False
        self._getmany_calls = 0

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

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
        "content": "Bài viết về trí tuệ nhân tạo",
        "topics": [],
    }
    conn.execute.return_value = "UPDATE 1"

    consumer = FakeConsumer(envelope)
    monkeypatch.setattr(kafka_consumer.asyncpg, "connect", AsyncMock(return_value=conn))
    monkeypatch.setattr(kafka_consumer, "AIOKafkaConsumer", lambda *args, **kwargs: consumer)

    cfg = Settings(flush_interval_seconds=0.01, flush_batch_size=50)
    task = asyncio.create_task(kafka_consumer.run_consumer(cfg))
    await asyncio.sleep(0.05)

    try:
        conn.execute.assert_called_once()
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
