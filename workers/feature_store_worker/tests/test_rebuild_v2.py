from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest

from app import rebuild_v2


class FakeConnection:
    def __init__(
        self,
        user_ids: list[UUID],
        source_ids: set[UUID],
        existing_vector_ids: set[UUID] | None = None,
    ) -> None:
        self.user_ids = user_ids
        self.source_ids = source_ids
        self.existing_vector_ids = existing_vector_ids or set()
        self.pages: list[tuple[UUID | None, int]] = []

    async def fetch(self, sql: str, cursor: UUID | None, limit: int):
        assert sql == rebuild_v2.PAGE_USERS_SQL
        self.pages.append((cursor, limit))
        remaining = [user for user in self.user_ids if cursor is None or user > cursor]
        return [{"user_id": user} for user in remaining[:limit]]

    async def fetchrow(self, sql: str, user_id: UUID):
        assert sql == rebuild_v2.SOURCE_STATUS_SQL
        return {
            "has_source": user_id in self.source_ids,
            "has_existing_vector": user_id in self.existing_vector_ids,
        }

    async def fetchval(self, sql: str):
        assert sql == rebuild_v2.HAS_EXISTING_VECTORS_SQL
        return bool(self.existing_vector_ids)


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection
        self.close = AsyncMock()

    def acquire(self):
        pool = self

        class Acquisition:
            async def __aenter__(self):
                return pool.connection

            async def __aexit__(self, *_args):
                return False

        return Acquisition()


@pytest.mark.asyncio
async def test_replay_all_keyset_pages_and_rebuilds_existing_vectors():
    users = [UUID(int=value) for value in (1, 2, 3)]
    connection = FakeConnection(users, set(users), set(users))
    worker = SimpleNamespace(
        pool=FakePool(connection), _rebuild_v2_for_user=AsyncMock()
    )

    rebuilt = await rebuild_v2.replay_all(
        worker, batch_size=2, replace_existing_vectors=True
    )

    assert rebuilt == 3
    assert connection.pages == [(None, 2), (users[1], 2), (users[2], 2)]
    assert [call.args[0] for call in worker._rebuild_v2_for_user.await_args_list] == [
        str(user) for user in users
    ]


@pytest.mark.asyncio
async def test_replay_refuses_to_leave_a_stale_vector_without_source():
    user_id = UUID(int=4)
    worker = SimpleNamespace(
        pool=FakePool(FakeConnection([user_id], set())),
        _rebuild_v2_for_user=AsyncMock(),
    )

    with pytest.raises(RuntimeError, match="no canonical behavior_events"):
        await rebuild_v2.replay_user(worker, user_id)

    worker._rebuild_v2_for_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_replay_refuses_to_replace_existing_vector_without_source_review():
    user_id = UUID(int=6)
    worker = SimpleNamespace(
        pool=FakePool(FakeConnection([user_id], {user_id}, {user_id})),
        _rebuild_v2_for_user=AsyncMock(),
    )

    with pytest.raises(RuntimeError, match="--replace-existing-vectors"):
        await rebuild_v2.replay_user(worker, user_id)

    worker._rebuild_v2_for_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_replay_all_checks_existing_vectors_before_writing_any_user():
    users = [UUID(int=7), UUID(int=8)]
    connection = FakeConnection(users, set(users), {users[1]})
    worker = SimpleNamespace(
        pool=FakePool(connection), _rebuild_v2_for_user=AsyncMock()
    )

    with pytest.raises(RuntimeError, match="--replace-existing-vectors"):
        await rebuild_v2.replay_all(worker, batch_size=1)

    assert connection.pages == []
    worker._rebuild_v2_for_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_rebuild_opens_only_database_and_redis_and_closes_both(monkeypatch):
    user_id = UUID(int=5)
    pool = FakePool(FakeConnection([user_id], {user_id}))
    redis = SimpleNamespace(close=AsyncMock())
    worker = SimpleNamespace(
        cfg=SimpleNamespace(database_url="postgres://test", redis_url="redis://test"),
        pool=None,
        redis=None,
        _rebuild_v2_for_user=AsyncMock(),
    )
    create_pool = AsyncMock(return_value=pool)
    from_url = Mock(return_value=redis)
    monkeypatch.setattr(rebuild_v2, "Worker", Mock(return_value=worker))
    monkeypatch.setattr(rebuild_v2.asyncpg, "create_pool", create_pool)
    monkeypatch.setattr(rebuild_v2.redis_async, "from_url", from_url)

    rebuilt = await rebuild_v2.run_rebuild(user_id, all_users=False, batch_size=2)

    assert rebuilt == 1
    worker._rebuild_v2_for_user.assert_awaited_once_with(str(user_id))
    create_pool.assert_awaited_once_with("postgres://test", min_size=1, max_size=2)
    from_url.assert_called_once_with("redis://test", decode_responses=True)
    redis.close.assert_awaited_once()
    pool.close.assert_awaited_once()
