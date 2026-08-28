from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.main import Worker

ROOT = Path(__file__).resolve().parents[3]
VIEWED_FIXTURE = json.loads(
    (ROOT / "tests/fixtures/recommendation_telemetry/interaction_viewed_v1.json").read_text()
)


class FakeTransaction:
    def __init__(self, conn: "FakeConnection") -> None:
        self.conn = conn

    async def __aenter__(self) -> None:
        self.conn.in_transaction = True

    async def __aexit__(self, *_args: object) -> None:
        self.conn.in_transaction = False


class FakeConnection:
    def __init__(self) -> None:
        self.in_transaction = False
        self.receipts: set[str] = set()
        self.vector: dict[str, float] = {}
        self.vector_updates = 0

    def transaction(self) -> FakeTransaction:
        return FakeTransaction(self)

    async def fetchrow(self, query: str, *_args: object):
        assert self.in_transaction
        if "user_preference_vectors" in query:
            return {"topic_weights": json.dumps(self.vector)} if self.vector else None
        raise AssertionError(f"unexpected fetchrow query: {query}")

    async def fetch(self, query: str, *args: object):
        assert self.in_transaction
        if "feature_event_receipts" in query:
            event_ids = list(args[0])
            claimed = []
            for event_id in event_ids:
                if str(event_id) not in self.receipts:
                    self.receipts.add(str(event_id))
                    claimed.append({"event_id": event_id})
            return claimed
        if "FROM posts" in query:
            return [{"id": args[0][0], "topics": ["ai"], "tags": []}]
        raise AssertionError(f"unexpected fetch query: {query}")

    async def execute(self, query: str, *_args: object) -> None:
        assert self.in_transaction
        if "user_preference_vectors" not in query:
            raise AssertionError(f"unexpected execute query: {query}")
        self.vector = json.loads(str(_args[1]))
        self.vector_updates += 1


class AcquireConnection:
    def __init__(self, conn: FakeConnection) -> None:
        self.conn = conn

    async def __aenter__(self) -> FakeConnection:
        return self.conn

    async def __aexit__(self, *_args: object) -> None:
        pass


class FakePool:
    def __init__(self, conn: FakeConnection) -> None:
        self.conn = conn

    def acquire(self) -> AcquireConnection:
        return AcquireConnection(self.conn)


class FakeRedis:
    def __init__(self, fail_once: bool = False) -> None:
        self.fail_once = fail_once
        self.cached: dict[str, str] = {}

    async def setex(self, key: str, _ttl: int, value: str) -> None:
        if self.fail_once:
            self.fail_once = False
            raise ConnectionError("redis unavailable after DB commit")
        self.cached[key] = value


class FakeCounter:
    def __init__(self) -> None:
        self.records: list[tuple[str, str, int]] = []
        self.current: tuple[str, str] | None = None

    def labels(self, *, outcome: str, event_type: str) -> "FakeCounter":
        self.current = (outcome, event_type)
        return self

    def inc(self, amount: int = 1) -> None:
        assert self.current is not None
        self.records.append((*self.current, amount))


def event(event_id: str, event_type: str) -> dict:
    envelope = json.loads(json.dumps(VIEWED_FIXTURE))
    envelope["event_id"] = event_id
    envelope["event_type"] = event_type
    return envelope


def worker_with_fakes(monkeypatch: pytest.MonkeyPatch, *, redis_fail_once: bool = False):
    from app import main

    conn = FakeConnection()
    redis = FakeRedis(fail_once=redis_fail_once)
    counter = FakeCounter()
    monkeypatch.setattr(main, "FEATURE_EVENT_OUTCOMES", counter, raising=False)
    worker = Worker()
    worker.pool = FakePool(conn)  # type: ignore[assignment]
    worker.redis = redis  # type: ignore[assignment]
    worker._update_trending = AsyncMock()  # type: ignore[method-assign]
    return worker, conn, redis, counter


async def test_viewed_envelope_updates_preference_exactly_once_on_replay(monkeypatch):
    worker, conn, _redis, counter = worker_with_fakes(monkeypatch)

    worker._buffer = [VIEWED_FIXTURE]
    assert await worker._flush() is True
    worker._buffer = [VIEWED_FIXTURE]
    assert await worker._flush() is True

    assert conn.vector == {"ai": 0.5}
    assert conn.vector_updates == 1
    assert ("applied", "viewed", 1) in counter.records
    assert ("duplicate", "viewed", 1) in counter.records


async def test_replay_after_redis_failure_does_not_apply_vector_twice(monkeypatch):
    worker, conn, redis, _counter = worker_with_fakes(monkeypatch, redis_fail_once=True)
    worker._buffer = [VIEWED_FIXTURE]

    assert await worker._flush() is False
    assert conn.vector == {"ai": 0.5}
    assert await worker._flush() is True

    assert conn.vector == {"ai": 0.5}
    assert conn.vector_updates == 1
    assert json.loads(redis.cached[f"pref:{VIEWED_FIXTURE['data']['user_id']}"]) == {"ai": 0.5}


@pytest.mark.parametrize(
    ("event_type", "event_id"),
    [
        ("visible", "0198f36d-0d80-7000-8000-000000000011"),
        ("dwell", "0198f36d-0d80-7000-8000-000000000012"),
    ],
)
async def test_visible_and_dwell_do_not_change_preferences(monkeypatch, event_type, event_id):
    worker, conn, _redis, counter = worker_with_fakes(monkeypatch)
    worker._buffer = [event(event_id, event_type)]

    assert await worker._flush() is True

    assert conn.vector == {}
    assert conn.vector_updates == 0
    assert ("ignored", event_type, 1) in counter.records


async def test_legacy_liked_and_saved_envelopes_still_apply(monkeypatch):
    worker, conn, _redis, _counter = worker_with_fakes(monkeypatch)
    worker._buffer = [
        event("0198f36d-0d80-7000-8000-000000000021", "liked"),
        event("0198f36d-0d80-7000-8000-000000000022", "saved"),
    ]

    assert await worker._flush() is True

    assert conn.vector == {"ai": 4.0}


async def test_unknown_event_is_counted_and_skipped_safely(monkeypatch):
    worker, conn, _redis, counter = worker_with_fakes(monkeypatch)
    worker._buffer = [event("0198f36d-0d80-7000-8000-000000000031", "future_signal")]

    assert await worker._flush() is True

    assert conn.vector == {}
    assert conn.vector_updates == 0
    assert ("unknown", "future_signal", 1) in counter.records
