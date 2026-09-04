from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.main import Worker

ROOT = Path(__file__).resolve().parents[3]
VIEWED_FIXTURE = json.loads(
    (
        ROOT / "tests/fixtures/recommendation_telemetry/interaction_viewed_v1.json"
    ).read_text()
)
LABEL_V2_FIXTURE = json.loads(
    (ROOT / "tests/fixtures/recommendation_telemetry/label-v2-cases.json").read_text()
)


class FakeTransaction:
    def __init__(self, conn: FakeConnection) -> None:
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
        self.vector_v2: dict | None = None
        self.canonical_events: list[dict] = []
        self.user_exists = True

    def transaction(self) -> FakeTransaction:
        return FakeTransaction(self)

    async def fetchrow(self, query: str, *_args: object):
        assert self.in_transaction
        if "FROM users" in query:
            return {
                "user_exists": self.user_exists,
                "topic_weights": json.dumps(self.vector) if self.vector else None,
                "vector_v2": self.vector_v2,
            }
        if "user_preference_vectors" in query:
            return {"topic_weights": json.dumps(self.vector)} if self.vector else None
        raise AssertionError(f"unexpected fetchrow query: {query}")

    async def fetch(self, query: str, *args: object):
        assert self.in_transaction
        if "feature_event_receipts" in query:
            event_ids = list(args[0])
            event_types = list(args[1])
            occurred_times = list(args[2])
            claimed = []
            canonical_name = {
                "viewed": "view",
                "qualified_read": "dwell",
                "liked": "like",
                "unliked": "unlike",
                "saved": "save",
                "unsaved": "unsave",
                "shared": "share",
                "unshared": "unshare",
                "hidden": "hide",
                "reported": "report",
                "commented": "comment",
            }
            for event_id, event_type, occurred_at in zip(
                event_ids, event_types, occurred_times, strict=True
            ):
                if str(event_id) not in self.receipts:
                    self.receipts.add(str(event_id))
                    claimed.append({"event_id": event_id})
                    self.canonical_events.append(
                        {
                            "event_id": str(event_id),
                            "post_id": VIEWED_FIXTURE["data"]["post_id"],
                            "impression_id": None,
                            "event_type": canonical_name.get(event_type, event_type),
                            "dwell_ms": (
                                10_000
                                if event_type in {"viewed", "qualified_read"}
                                else None
                            ),
                            "occurred_at": occurred_at,
                            "topics": ["ai"],
                            "tags": [],
                        }
                    )
            return claimed
        if "FROM behavior_events AS event" in query:
            return self.canonical_events
        if "FROM posts" in query:
            return [{"id": args[0][0], "topics": ["ai"], "tags": []}]
        raise AssertionError(f"unexpected fetch query: {query}")

    async def execute(self, query: str, *_args: object) -> None:
        assert self.in_transaction
        if "user_preference_vectors" not in query:
            raise AssertionError(f"unexpected execute query: {query}")
        if not self.user_exists:
            raise ValueError("foreign key violation for deleted user")
        if "user_preference_vectors_v2" in query:
            self.vector_v2 = {
                "schema_version": _args[1],
                "positive": json.loads(str(_args[2])),
                "negative": json.loads(str(_args[3])),
                "reference_at": _args[4],
                "source_event_count": _args[5],
            }
            return
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
        self.deleted: list[str] = []

    async def delete(self, *keys: str) -> None:
        self.deleted.extend(keys)
        for key in keys:
            self.cached.pop(key, None)

    async def setex(self, key: str, _ttl: int, value: str) -> None:
        if self.fail_once:
            self.fail_once = False
            raise ConnectionError("redis unavailable after DB commit")
        self.cached[key] = value


class FakeCounter:
    def __init__(self) -> None:
        self.records: list[tuple[str, str, int]] = []
        self.current: tuple[str, str] | None = None

    def labels(self, *, outcome: str, event_type: str) -> FakeCounter:
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


def worker_with_fakes(
    monkeypatch: pytest.MonkeyPatch, *, redis_fail_once: bool = False
):
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
    worker, conn, redis, counter = worker_with_fakes(monkeypatch)

    worker._buffer = [VIEWED_FIXTURE]
    assert await worker._flush() is True
    worker._buffer = [VIEWED_FIXTURE]
    assert await worker._flush() is True

    assert conn.vector == {"ai": 0.5}
    assert conn.vector_v2 is not None
    assert conn.vector_v2["schema_version"] == "preference-vector-v2"
    assert json.loads(redis.cached[f"pref:v2:{VIEWED_FIXTURE['data']['user_id']}"])[
        "positive"
    ] == {"ai": 0.5}
    assert f"feed:{VIEWED_FIXTURE['data']['user_id']}" in redis.deleted
    assert conn.vector_updates == 1
    assert ("applied", "viewed", 1) in counter.records
    assert ("duplicate", "viewed", 1) in counter.records


async def test_qualified_read_v2_updates_preference_exactly_once_on_replay(monkeypatch):
    worker, conn, _redis, counter = worker_with_fakes(monkeypatch)
    qualified = event("0198f36d-0d80-7000-8000-000000000041", "qualified_read")
    qualified["event_version"] = 2
    qualified["data"]["duration_ms"] = LABEL_V2_FIXTURE["qualified_read_ms"]
    qualified["data"]["source_event_type"] = "dwell"

    worker._buffer = [qualified, qualified]
    assert await worker._flush() is True

    assert conn.vector == {"ai": 0.5}
    assert conn.vector_v2 is not None
    assert conn.vector_v2["positive"] == {"ai": 0.5}
    assert conn.vector_updates == 1
    assert ("applied", "qualified_read", 1) in counter.records
    assert ("duplicate", "qualified_read", 1) in counter.records


async def test_feature_worker_dual_reads_v1_and_v2_qualified_read_events(monkeypatch):
    worker, conn, _redis, _counter = worker_with_fakes(monkeypatch)
    qualified = event("0198f36d-0d80-7000-8000-000000000042", "qualified_read")
    qualified["event_version"] = 2
    qualified["data"]["duration_ms"] = LABEL_V2_FIXTURE["qualified_read_ms"]
    qualified["data"]["source_event_type"] = "view"
    worker._buffer = [VIEWED_FIXTURE, qualified]

    assert await worker._flush() is True
    assert conn.vector == {"ai": 1.0}


async def test_duplicate_event_inside_one_kafka_batch_is_only_applied_once(monkeypatch):
    worker, conn, _redis, counter = worker_with_fakes(monkeypatch)
    worker._buffer = [VIEWED_FIXTURE, VIEWED_FIXTURE]

    assert await worker._flush() is True

    assert conn.vector == {"ai": 0.5}
    assert conn.vector_updates == 1
    assert ("duplicate", "viewed", 1) in counter.records


async def test_replay_after_redis_failure_does_not_apply_vector_twice(monkeypatch):
    worker, conn, redis, _counter = worker_with_fakes(monkeypatch, redis_fail_once=True)
    worker._buffer = [VIEWED_FIXTURE]

    assert await worker._flush() is False
    assert conn.vector == {"ai": 0.5}
    assert await worker._flush() is True

    assert conn.vector == {"ai": 0.5}
    assert conn.vector_updates == 1
    assert json.loads(redis.cached[f"pref:{VIEWED_FIXTURE['data']['user_id']}"]) == {
        "ai": 0.5
    }


@pytest.mark.parametrize(
    ("event_type", "event_id"),
    [
        ("visible", "0198f36d-0d80-7000-8000-000000000011"),
        ("dwell", "0198f36d-0d80-7000-8000-000000000012"),
    ],
)
async def test_visible_and_dwell_do_not_change_preferences(
    monkeypatch, event_type, event_id
):
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


@pytest.mark.parametrize("identity_field", ["user_id", "reporter_id", "commenter_id"])
async def test_malformed_identity_is_not_retried_or_logged(
    monkeypatch, caplog, identity_field
):
    worker, conn, _redis, counter = worker_with_fakes(monkeypatch)
    malformed_identity = "raw-identity-must-not-leak"
    envelope = event("0198f36d-0d80-7000-8000-000000000032", "liked")
    envelope["data"] = {
        "post_id": envelope["data"]["post_id"],
        identity_field: malformed_identity,
    }
    worker._buffer = [envelope]

    with caplog.at_level(logging.WARNING, logger="feature_store_worker"):
        assert await worker._flush() is True

    assert worker._buffer == []
    assert conn.vector_updates == 0
    assert ("invalid", "liked", 1) in counter.records
    assert malformed_identity not in caplog.text


async def test_event_for_deleted_user_is_receipted_and_not_retried(monkeypatch):
    worker, conn, redis, counter = worker_with_fakes(monkeypatch)
    conn.user_exists = False
    worker._buffer = [VIEWED_FIXTURE]

    assert await worker._flush() is True

    assert str(VIEWED_FIXTURE["event_id"]) in conn.receipts
    assert conn.vector_updates == 0
    assert redis.cached == {}
    assert ("ignored", "viewed", 1) in counter.records
