from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest

from ai_pipeline.build_dataset import build_history_snapshot
from ai_pipeline.config import DatasetConfig
from ai_pipeline.schemas import ArticleFeatureRecord, BehaviorEvent
from app.db import fetch_user_history
from app.settings import Settings

USER_ID = UUID("00000000-0000-0000-0000-000000000001")
REFERENCE_AT = datetime(2026, 9, 4, 8, 0, tzinfo=timezone.utc)
ENCODER_VERSION = (
    "intfloat/multilingual-e5-small@614241f622f53c4eeff9890bdc4f31cfecc418b3"
)


class FakeRedisClient:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}
        self.reads: list[str] = []
        self.writes: list[tuple[str, int, str]] = []

    async def get(self, key: str):
        self.reads.append(key)
        return self.values.get(key)

    async def setex(self, key: str, ttl: int, value: str):
        self.values[key] = value
        self.writes.append((key, ttl, value))


class FakePool:
    def __init__(self, event_rows, feature_rows) -> None:
        self.event_rows = list(event_rows)
        self.feature_rows = list(feature_rows)
        self.queries: list[str] = []

    async def fetch(self, query: str, *_args):
        self.queries.append(query)
        if "FROM behavior_events" in query:
            return list(self.event_rows)
        if "FROM post_content_features" in query:
            return list(self.feature_rows)
        raise AssertionError(query)


def _cfg(**overrides):
    values = {
        "history_recent_limit": 2,
        "history_long_term_limit": 1,
        "history_cache_ttl_seconds": 1800,
        "history_lookup_slack": 4,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _dataset_config() -> DatasetConfig:
    return DatasetConfig(
        start=datetime(2026, 9, 1, tzinfo=timezone.utc),
        end=datetime(2026, 9, 5, tzinfo=timezone.utc),
        extraction_time=REFERENCE_AT,
        label_window_hours=24,
        qualified_read_ms=10_000,
        recommendation_label_version="v2",
        identity_mode="hash",
        hash_salt="history-test-salt",
        history_recent_limit=2,
        history_long_term_limit=1,
    )


def _event_row(event_id: int, post_id: UUID, occurred_at: datetime, *, ingested_at: datetime | None = None):
    return {
        "id": UUID(int=event_id),
        "impression_id": None,
        "user_id": USER_ID,
        "post_id": post_id,
        "event_type": "click",
        "dwell_ms": None,
        "occurred_at": occurred_at,
        "ingested_at": ingested_at or occurred_at,
        "event_version": "v2",
        "metadata": {"event_version": "v2"},
    }


def _feature_row(feature_id: int, post_id: UUID, content_hash: str, when: datetime):
    embedding = [0.0] * 384
    embedding[0] = 1.0
    return {
        "id": UUID(int=feature_id),
        "post_id": post_id,
        "encoder_version": ENCODER_VERSION,
        "content_hash": content_hash,
        "embedding": embedding,
        "source_updated_at": when,
        "computed_at": when,
    }


@pytest.mark.asyncio
async def test_fetch_user_history_matches_offline_snapshot_and_caches_reconstructible_metadata():
    posts = [UUID(int=500 + index) for index in range(3)]
    event_rows = [
        _event_row(1, posts[0], REFERENCE_AT - timedelta(hours=3)),
        _event_row(2, posts[1], REFERENCE_AT - timedelta(hours=2)),
        _event_row(3, posts[2], REFERENCE_AT - timedelta(hours=1)),
    ]
    feature_rows = [
        _feature_row(11, posts[0], "a" * 64, REFERENCE_AT - timedelta(days=1)),
        _feature_row(12, posts[1], "b" * 64, REFERENCE_AT - timedelta(days=1)),
        _feature_row(13, posts[2], "c" * 64, REFERENCE_AT - timedelta(days=1)),
    ]
    redis_client = FakeRedisClient()
    pool = FakePool(event_rows, feature_rows)

    online = await fetch_user_history(
        SimpleNamespace(pool=pool),
        SimpleNamespace(cli=redis_client),
        USER_ID,
        at=REFERENCE_AT,
        config=_cfg(),
    )
    offline = build_history_snapshot(
        USER_ID,
        REFERENCE_AT,
        [BehaviorEvent.from_mapping(row) for row in event_rows],
        [ArticleFeatureRecord.from_mapping(row) for row in feature_rows],
        _dataset_config(),
    )

    assert online.to_offline_snapshot() == offline
    assert redis_client.writes == []

    live_reference_at = datetime.now(timezone.utc)
    live_event_rows = [
        _event_row(21, posts[0], live_reference_at - timedelta(hours=3)),
        _event_row(22, posts[1], live_reference_at - timedelta(hours=2)),
        _event_row(23, posts[2], live_reference_at - timedelta(hours=1)),
    ]
    live_feature_rows = [
        _feature_row(31, posts[0], "a" * 64, live_reference_at - timedelta(days=1)),
        _feature_row(32, posts[1], "b" * 64, live_reference_at - timedelta(days=1)),
        _feature_row(33, posts[2], "c" * 64, live_reference_at - timedelta(days=1)),
    ]
    live_pool = FakePool(live_event_rows, live_feature_rows)
    live_redis = FakeRedisClient()
    live = await fetch_user_history(
        SimpleNamespace(pool=live_pool),
        SimpleNamespace(cli=live_redis),
        USER_ID,
        config=_cfg(),
    )
    live_offline = build_history_snapshot(
        USER_ID,
        live.reference_at,
        [BehaviorEvent.from_mapping(row) for row in live_event_rows],
        [ArticleFeatureRecord.from_mapping(row) for row in live_feature_rows],
        _dataset_config(),
    )

    assert live.to_offline_snapshot() == live_offline
    assert live_redis.writes
    payload = json.loads(live_redis.writes[0][2])
    assert payload["schema_version"] == "user-history-snapshot-v1"
    assert "embedding" not in payload["entries"][0]
    assert payload["entries"][0]["event_id"] == str(UUID(int=21))
    assert payload["entries"][0]["content_hash"] == "a" * 64


def test_runtime_settings_expose_history_loader_controls():
    settings = Settings()

    assert settings.history_recent_limit == 20
    assert settings.history_long_term_limit == 30
    assert settings.history_cache_ttl_seconds == 1800
    assert settings.history_lookup_slack == 50


@pytest.mark.asyncio
async def test_fetch_user_history_treats_malformed_cache_as_a_miss():
    post_id = UUID(int=700)
    occurred_at = datetime.now(timezone.utc) - timedelta(hours=1)
    pool = FakePool(
        [_event_row(701, post_id, occurred_at)],
        [_feature_row(702, post_id, "7" * 64, occurred_at - timedelta(days=1))],
    )
    redis_client = FakeRedisClient(
        {
            f"history:v2:{USER_ID}": json.dumps(
                {
                    "schema_version": "user-history-snapshot-v1",
                    "entries": [{"post_id": "not-a-uuid"}],
                }
            )
        }
    )

    result = await fetch_user_history(
        SimpleNamespace(pool=pool),
        SimpleNamespace(cli=redis_client),
        USER_ID,
        config=_cfg(),
    )

    assert [entry.post_id for entry in result.entries] == [post_id]
    assert any("FROM behavior_events" in query for query in pool.queries)
