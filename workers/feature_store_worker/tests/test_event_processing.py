from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from app.features import build_preference_vector_v2
from app.main import Worker, _canonical_preference_events, _refresh_recent_topics_for_user

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
        self.topic_prefs: list[str] = []
        self.recent_pref_refreshes = 0

    def transaction(self) -> FakeTransaction:
        return FakeTransaction(self)

    async def fetchrow(self, query: str, *_args: object):
        assert self.in_transaction
        if "FROM user_recent_topic_preferences" in query:
            return {"user_id": _args[0]}
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
                "view_observed": "view",
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
                    # A dwell trigger follows its already-committed behavior
                    # row; the fake test seeds that canonical row explicitly.
                    if event_type == "dwell":
                        continue
                    self.canonical_events.append(
                        {
                            "event_id": str(event_id),
                            "post_id": VIEWED_FIXTURE["data"]["post_id"],
                            "impression_id": None,
                            "session_id": None,
                            "event_type": canonical_name.get(event_type, event_type),
                            "dwell_ms": (
                                10_000
                                if event_type in {"viewed", "qualified_read"}
                                else None
                            ),
                            "occurred_at": occurred_at,
                            "read_trigger": None,
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
        if "UPDATE users SET topic_prefs" in query:
            self.topic_prefs = list(_args[1])
            return
        if "INSERT INTO user_recent_topic_preferences" in query:
            self.recent_pref_refreshes += 1
            return
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
        self.due_users: list[str] = []

    def acquire(self) -> AcquireConnection:
        return AcquireConnection(self.conn)

    async def fetch(self, _query: str):
        return [{"user_id": user_id} for user_id in self.due_users]


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


def test_canonical_topic_snapshot_survives_later_post_topic_change():
    occurred_at = datetime.fromisoformat(
        VIEWED_FIXTURE["occurred_at"].replace("Z", "+00:00")
    )
    row = {
        "event_id": VIEWED_FIXTURE["event_id"],
        "post_id": VIEWED_FIXTURE["data"]["post_id"],
        "impression_id": None,
        "session_id": None,
        "event_type": "click",
        "dwell_ms": None,
        "occurred_at": occurred_at,
        "topic_snapshot": ["ai"],
        "topics": ["ai"],
        "tags": [],
    }
    original = build_preference_vector_v2(
        _canonical_preference_events([row]), reference_at=occurred_at
    )

    row["topics"] = ["politics"]
    row["tags"] = ["culture"]
    after_post_edit = build_preference_vector_v2(
        _canonical_preference_events([row]), reference_at=occurred_at
    )

    assert original == after_post_edit
    assert after_post_edit.positive == {"ai": 1.0}


def test_legacy_null_snapshot_uses_current_post_topics_but_empty_is_authoritative():
    row = {
        "event_id": VIEWED_FIXTURE["event_id"],
        "post_id": VIEWED_FIXTURE["data"]["post_id"],
        "impression_id": None,
        "session_id": None,
        "event_type": "click",
        "dwell_ms": None,
        "occurred_at": datetime.fromisoformat(
            VIEWED_FIXTURE["occurred_at"].replace("Z", "+00:00")
        ),
        "topic_snapshot": None,
        "topics": ["politics"],
        "tags": ["culture"],
    }

    assert _canonical_preference_events([row])[0].topics == ("politics",)
    row["topic_snapshot"] = []
    assert _canonical_preference_events([row])[0].topics == ()


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
    assert conn.recent_pref_refreshes == 1
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


async def test_click_replays_v2_without_changing_v1_on_redelivery(monkeypatch):
    worker, conn, redis, counter = worker_with_fakes(monkeypatch)
    clicked = event("0198f36d-0d80-7000-8000-000000000043", "click")

    worker._buffer = [clicked]
    assert await worker._flush() is True
    worker._buffer = [clicked]
    assert await worker._flush() is True

    assert conn.vector == {}
    assert conn.vector_updates == 1
    assert conn.vector_v2 is not None
    assert conn.vector_v2["positive"] == {"ai": 1.0}
    assert conn.vector_v2["source_event_count"] == 1
    assert json.loads(redis.cached[f"pref:v2:{clicked['data']['user_id']}"])[
        "positive"
    ] == {"ai": 1.0}
    assert ("applied", "click", 1) in counter.records
    assert ("duplicate", "click", 1) in counter.records


@pytest.mark.parametrize("event_type", ["click", "dwell", "unhide", "view_observed"])
async def test_zero_delta_trigger_does_not_refresh_trending_expiry(event_type):
    worker = Worker()
    worker.redis = FakeRedis()  # type: ignore[assignment]

    await worker._update_trending(
        [event("0198f36d-0d80-7000-8000-000000000044", event_type)]
    )


async def test_unhide_trigger_reverses_v2_hide_without_changing_v1(monkeypatch):
    worker, conn, _redis, counter = worker_with_fakes(monkeypatch)
    hidden = event("0198f36d-0d80-7000-8000-000000000047", "hidden")
    unhidden = event("0198f36d-0d80-7000-8000-000000000048", "unhide")
    unhidden["occurred_at"] = "2026-08-28T03:16:00Z"

    worker._buffer = [hidden]
    assert await worker._flush() is True
    assert conn.vector == {"ai": -2.0}
    assert conn.vector_v2 is not None
    assert conn.vector_v2["negative"] == {"ai": 2.0}

    worker._buffer = [unhidden]
    assert await worker._flush() is True
    worker._buffer = [unhidden]
    assert await worker._flush() is True

    assert conn.vector == {"ai": -2.0}
    assert conn.vector_updates == 2
    assert conn.vector_v2 is not None
    assert conn.vector_v2["negative"] == {}
    assert conn.vector_v2["source_event_count"] == 0
    assert ("applied", "unhide", 1) in counter.records
    assert ("duplicate", "unhide", 1) in counter.records


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


async def test_trending_counts_receipted_event_once_across_batch_and_replay(monkeypatch):
    worker, conn, _redis, _counter = worker_with_fakes(monkeypatch)
    worker._buffer = [VIEWED_FIXTURE, VIEWED_FIXTURE]

    assert await worker._flush() is True
    worker._buffer = [VIEWED_FIXTURE]
    assert await worker._flush() is True

    assert conn.vector_updates == 1
    worker._update_trending.assert_awaited_once_with([VIEWED_FIXTURE])


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
    # The receipt committed before the cache failure, so replay cannot safely
    # add an uncertain trending increment later.
    worker._update_trending.assert_not_awaited()


async def test_visible_is_ignored_without_changing_preferences(monkeypatch):
    worker, conn, _redis, counter = worker_with_fakes(monkeypatch)
    worker._buffer = [event("0198f36d-0d80-7000-8000-000000000011", "visible")]

    assert await worker._flush() is True

    assert conn.vector == {}
    assert conn.vector_updates == 0
    assert ("ignored", "visible", 1) in counter.records


async def test_qualified_dwell_triggers_v2_replay_without_v1_delta(monkeypatch):
    worker, conn, redis, counter = worker_with_fakes(monkeypatch)
    dwell = event("0198f36d-0d80-7000-8000-000000000012", "dwell")
    conn.canonical_events.append(
        {
            "event_id": dwell["event_id"],
            "post_id": dwell["data"]["post_id"],
            "impression_id": None,
            "session_id": dwell["data"]["session_id"],
            "event_type": "dwell",
            "dwell_ms": 15_000,
            "occurred_at": datetime.fromisoformat(
                dwell["occurred_at"].replace("Z", "+00:00")
            ),
            "read_trigger": "destroy",
            "topics": ["ai"],
            "tags": [],
        }
    )

    worker._buffer = [dwell, dwell]
    assert await worker._flush() is True
    worker._buffer = [dwell]
    assert await worker._flush() is True

    assert conn.vector == {}
    assert conn.vector_updates == 1
    assert conn.vector_v2 is not None
    assert conn.vector_v2["positive"] == {"ai": 0.5}
    assert conn.vector_v2["source_event_count"] == 1
    assert f"feed:{dwell['data']['user_id']}" in redis.deleted
    assert ("applied", "dwell", 1) in counter.records
    assert ("duplicate", "dwell", 1) in counter.records


async def test_dwell_triggers_replay_distinct_visit_ids_without_destroy(monkeypatch):
    worker, conn, _redis, _counter = worker_with_fakes(monkeypatch)
    first = event("0198f36d-0d80-7000-8000-000000000045", "dwell")
    second = event("0198f36d-0d80-7000-8000-000000000046", "dwell")
    occurred_at = datetime.fromisoformat(first["occurred_at"].replace("Z", "+00:00"))
    for envelope, visit_id in ((first, "visit-1"), (second, "visit-2")):
        conn.canonical_events.append(
            {
                "event_id": envelope["event_id"],
                "post_id": envelope["data"]["post_id"],
                "impression_id": None,
                "session_id": envelope["data"]["session_id"],
                "visit_id": visit_id,
                "event_type": "dwell",
                "dwell_ms": 10_000,
                "occurred_at": occurred_at,
                "read_trigger": None,
                "topics": ["ai"],
                "tags": [],
            }
        )

    worker._buffer = [first, second]
    assert await worker._flush() is True
    worker._buffer = [first, second]
    assert await worker._flush() is True

    assert conn.vector == {}
    assert conn.vector_updates == 1
    assert conn.vector_v2 is not None
    assert conn.vector_v2["positive"] == {"ai": 1.0}
    assert conn.vector_v2["source_event_count"] == 2


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


async def test_recent_view_event_writes_topic_prefs_and_expiry_clears_them(monkeypatch):
    worker, conn, redis, _counter = worker_with_fakes(monkeypatch)
    current = datetime.now(timezone.utc)
    viewed = event("0198f36d-0d80-7000-8000-000000000061", "view_observed")
    viewed["occurred_at"] = current.isoformat()

    worker._buffer = [viewed]
    assert await worker._flush() is True
    assert conn.topic_prefs == ["ai"]
    assert conn.vector == {}
    assert conn.vector_updates == 0
    assert f"feed:{viewed['data']['user_id']}" in redis.deleted

    async with conn.transaction():
        await _refresh_recent_topics_for_user(
            conn, viewed["data"]["user_id"], at=current + timedelta(days=22)
        )
    assert conn.topic_prefs == []


async def test_due_refresh_expires_topics_without_new_kafka_events(monkeypatch):
    worker, conn, redis, _counter = worker_with_fakes(monkeypatch)
    user_id = VIEWED_FIXTURE["data"]["user_id"]
    conn.topic_prefs = ["ai"]
    worker.pool.due_users = [user_id]

    await worker._refresh_due_recent_topics()

    assert conn.topic_prefs == []
    assert f"feed:{user_id}" in redis.deleted
