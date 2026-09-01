import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest
from app import db as db_module
from app.db import DB, RedisCli, fetch_user_vector, merge_preference_vector_v2

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


class FakeRedisClient:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values
        self.reads: list[str] = []

    async def get(self, key: str):
        self.reads.append(key)
        return self.values.get(key)


class FakePool:
    def __init__(self, rows: list[dict | None]) -> None:
        self.rows = list(rows)
        self.queries: list[str] = []

    async def fetchrow(self, query: str, *_args):
        self.queries.append(query)
        return self.rows.pop(0) if self.rows else None


def _cfg(**overrides):
    values = {
        "preference_schema_version": "v2",
        "preference_half_life_hours": 24.0,
        "preference_behavior_coefficient": 0.75,
        "preference_declared_coefficient": 0.25,
        "preference_evidence_saturation": 1.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_v2_payload_decays_at_read_time_and_blends_declared_topics_separately():
    payload = {
        "schema_version": "preference-vector-v2",
        "positive": {"ai": 1.0},
        "negative": {"politics": 1.0},
        "reference_at": (NOW - timedelta(hours=24)).isoformat(),
        "source_event_count": 2,
    }

    merged = merge_preference_vector_v2(
        payload,
        ["sports"],
        at=NOW,
        half_life_hours=24,
        behavior_coefficient=0.75,
        declared_coefficient=0.25,
        evidence_saturation=1.0,
    )

    assert merged == pytest.approx({"ai": 0.375, "politics": -0.375, "sports": 0.25})


@pytest.mark.asyncio
async def test_v2_cache_is_preferred_and_legacy_v1_is_immediate_fallback():
    v1 = json.dumps({"legacy": 0.8})
    redis_client = FakeRedisClient({f"pref:v1:{USER_ID}": v1})
    redis = SimpleNamespace(cli=redis_client)
    db = SimpleNamespace(pool=FakePool([]))

    result = await fetch_user_vector(db, redis, USER_ID, config=_cfg())

    assert result == {"legacy": 0.8}
    assert redis_client.reads == [f"pref:v2:{USER_ID}", f"pref:v1:{USER_ID}"]


@pytest.mark.asyncio
async def test_invalid_v2_payload_falls_back_to_v1_database_without_mixing_versions():
    redis = SimpleNamespace(
        cli=FakeRedisClient(
            {f"pref:v2:{USER_ID}": json.dumps({"schema_version": "wrong"})}
        )
    )
    pool = FakePool([None, {"topic_weights": json.dumps({"legacy": 1.5})}])
    db = SimpleNamespace(pool=pool)

    result = await fetch_user_vector(db, redis, USER_ID, config=_cfg())

    assert result == {"legacy": 1.5}
    assert any("user_preference_vectors_v2" in query for query in pool.queries)
    assert any("user_preference_vectors " in query for query in pool.queries)


@pytest.mark.asyncio
async def test_v2_database_payload_is_decayed_and_blended_with_declared_topics():
    redis_client = FakeRedisClient({})
    redis = SimpleNamespace(cli=redis_client)
    pool = FakePool(
        [
            {
                "schema_version": "preference-vector-v2",
                "positive_weights": {"ai": 1.0},
                "negative_weights": {"politics": 1.0},
                "reference_at": datetime.now(timezone.utc),
                "source_event_count": 2,
            },
            {"topic_prefs": ["sports"]},
        ]
    )

    result = await fetch_user_vector(
        SimpleNamespace(pool=pool), redis, USER_ID, config=_cfg()
    )

    assert result["ai"] > 0
    assert result["politics"] < 0
    assert result["sports"] == pytest.approx(0.25)
    assert redis_client.reads == [
        f"pref:v2:{USER_ID}",
        f"pref:v1:{USER_ID}",
        f"pref:{USER_ID}",
    ]


@pytest.mark.asyncio
async def test_v1_mode_uses_versioned_cache_without_querying_database():
    redis_client = FakeRedisClient({f"pref:v1:{USER_ID}": json.dumps({"legacy": 0.75})})

    result = await fetch_user_vector(
        SimpleNamespace(pool=FakePool([])),
        SimpleNamespace(cli=redis_client),
        USER_ID,
        config=_cfg(preference_schema_version="v1"),
    )

    assert result == {"legacy": 0.75}
    assert redis_client.reads == [f"pref:v1:{USER_ID}"]


@pytest.mark.asyncio
async def test_malformed_v1_storage_falls_back_to_declared_topics():
    redis_client = FakeRedisClient(
        {
            f"pref:v1:{USER_ID}": "not-json",
            f"pref:{USER_ID}": "[]",
        }
    )
    pool = FakePool(
        [
            {"topic_weights": "not-json"},
            {"topic_prefs": ["science", "ai"]},
        ]
    )

    result = await fetch_user_vector(
        SimpleNamespace(pool=pool),
        SimpleNamespace(cli=redis_client),
        USER_ID,
        config=_cfg(preference_schema_version="v1"),
    )

    assert result == {"science": 1.0, "ai": 1.0}


@pytest.mark.parametrize(
    ("payload", "overrides", "error"),
    [
        ({"schema_version": "wrong"}, {}, ValueError),
        (
            {
                "schema_version": "preference-vector-v2",
                "positive": {},
                "negative": {},
                "reference_at": NOW.isoformat(),
            },
            {"half_life_hours": 0},
            ValueError,
        ),
        (
            {
                "schema_version": "preference-vector-v2",
                "positive": {},
                "negative": {},
                "reference_at": NOW.isoformat(),
            },
            {"behavior_coefficient": -1},
            ValueError,
        ),
        (
            {
                "schema_version": "preference-vector-v2",
                "positive": [],
                "negative": {},
                "reference_at": NOW.isoformat(),
            },
            {},
            TypeError,
        ),
        (
            {
                "schema_version": "preference-vector-v2",
                "positive": {"ai": 11},
                "negative": {},
                "reference_at": NOW.isoformat(),
            },
            {},
            ValueError,
        ),
    ],
)
def test_v2_merge_rejects_invalid_contract_inputs(payload, overrides, error):
    kwargs = {
        "at": NOW,
        "half_life_hours": 24,
        "behavior_coefficient": 0.75,
        "declared_coefficient": 0.25,
        "evidence_saturation": 1,
        **overrides,
    }
    with pytest.raises(error):
        merge_preference_vector_v2(payload, [], **kwargs)


def test_v2_merge_allows_an_explicit_zero_weight_blend():
    result = merge_preference_vector_v2(
        {
            "schema_version": "preference-vector-v2",
            "positive": {"ai": 1},
            "negative": {},
            "reference_at": NOW.isoformat(),
        },
        ["sports"],
        at=NOW,
        half_life_hours=24,
        behavior_coefficient=0,
        declared_coefficient=0,
        evidence_saturation=1,
    )

    assert result == {}


@pytest.mark.asyncio
async def test_database_and_redis_runtime_wrappers_manage_their_resources(monkeypatch):
    pool = SimpleNamespace(close=AsyncMock())
    redis_client = SimpleNamespace(ping=AsyncMock(), close=AsyncMock())
    create_pool = AsyncMock(return_value=pool)
    from_url = Mock(return_value=redis_client)
    monkeypatch.setattr(db_module.asyncpg, "create_pool", create_pool)
    monkeypatch.setattr(db_module.redis_async, "from_url", from_url)

    database = DB("postgres://example")
    redis = RedisCli("redis://example")
    with pytest.raises(RuntimeError):
        _ = database.pool
    with pytest.raises(RuntimeError):
        _ = redis.cli

    await database.start()
    await redis.start()
    assert database.pool is pool
    assert redis.cli is redis_client
    redis_client.ping.assert_awaited_once()

    await redis.stop()
    await database.stop()
    redis_client.close.assert_awaited_once()
    pool.close.assert_awaited_once()
