from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.content_features import CONTENT_HASH_VERSION, ENCODER_VERSION, SCHEMA_VERSION
from app.embedding_worker import PostFeature
from app.repository import AsyncpgFeatureRepository


@pytest.mark.asyncio
async def test_repository_loads_post_and_updates_topics() -> None:
    connection = AsyncMock()
    timestamp = datetime(2026, 8, 31, tzinfo=UTC)
    connection.fetchrow.return_value = {
        "id": "post-id",
        "content": "Nội dung",
        "topics": ["tech"],
        "updated_at": timestamp,
    }
    repository = AsyncpgFeatureRepository(connection)

    record = await repository.get_post("post-id")
    await repository.ensure_topics("post-id", ["tech"])

    assert record is not None
    assert record.content == "Nội dung"
    connection.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_repository_idempotency_and_insert() -> None:
    connection = AsyncMock()
    connection.fetchval.side_effect = [True, "feature-id"]
    repository = AsyncpgFeatureRepository(connection)
    timestamp = datetime(2026, 8, 31, tzinfo=UTC)
    vector = [0.0] * 384
    vector[0] = 1.0
    feature = PostFeature(
        SCHEMA_VERSION,
        "post-id",
        ENCODER_VERSION,
        CONTENT_HASH_VERSION,
        "a" * 64,
        vector,
        ["tech"],
        timestamp,
        timestamp,
    )

    assert await repository.feature_exists("post-id", ENCODER_VERSION, "a" * 64)
    assert await repository.insert_feature(feature)
    assert connection.fetchval.await_count == 2


@pytest.mark.asyncio
async def test_repository_batch_cursor_is_resume_safe() -> None:
    connection = AsyncMock()
    first = datetime(2026, 8, 31, 10, tzinfo=UTC)
    second = datetime(2026, 8, 31, 11, tzinfo=UTC)
    connection.fetch.return_value = [
        {"id": "00000000-0000-0000-0000-000000000001", "content": "Một", "topics": [], "updated_at": first},
        {"id": "00000000-0000-0000-0000-000000000002", "content": "Hai", "topics": ["tech"], "updated_at": second},
    ]
    repository = AsyncpgFeatureRepository(connection)

    records, cursor = await repository.fetch_batch(None, 2)
    assert len(records) == 2
    assert cursor is not None

    connection.fetch.return_value = []
    records, next_cursor = await repository.fetch_batch(cursor, 2)
    assert records == []
    assert next_cursor is None
    second_call = connection.fetch.await_args_list[1].args
    assert second_call[1] == second
    assert second_call[2] == "00000000-0000-0000-0000-000000000002"
