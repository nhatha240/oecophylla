import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.db import fetch_user_vector, merge_preference_vector_v2


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
        cli=FakeRedisClient({f"pref:v2:{USER_ID}": json.dumps({"schema_version": "wrong"})})
    )
    pool = FakePool([None, {"topic_weights": json.dumps({"legacy": 1.5})}])
    db = SimpleNamespace(pool=pool)

    result = await fetch_user_vector(db, redis, USER_ID, config=_cfg())

    assert result == {"legacy": 1.5}
    assert any("user_preference_vectors_v2" in query for query in pool.queries)
    assert any("user_preference_vectors " in query for query in pool.queries)

