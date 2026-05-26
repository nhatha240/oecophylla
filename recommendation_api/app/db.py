from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from uuid import UUID

import asyncpg
import redis.asyncio as redis_async


class DB:
    """Lightweight pgpool wrapper. Created at startup, closed at shutdown."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: Optional[asyncpg.Pool] = None

    async def start(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=8)

    async def stop(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("DB pool not started")
        return self._pool


class RedisCli:
    def __init__(self, url: str) -> None:
        self._url = url
        self._cli: Optional[redis_async.Redis] = None

    async def start(self) -> None:
        self._cli = redis_async.from_url(self._url, decode_responses=True)
        await self._cli.ping()

    async def stop(self) -> None:
        if self._cli is not None:
            await self._cli.close()
            self._cli = None

    @property
    def cli(self) -> redis_async.Redis:
        if self._cli is None:
            raise RuntimeError("Redis client not started")
        return self._cli


async def fetch_user_vector(
    db: DB, redis: RedisCli, user_id: UUID
) -> dict[str, float]:
    """Hot path: Redis pref:{user_id}. Cold path: PG user_preference_vectors.
    Final fallback: users.topic_prefs (declared interests, weight 1.0 each)."""
    raw = await redis.cli.get(f"pref:{user_id}")
    if raw:
        try:
            import json as _json

            return {k: float(v) for k, v in _json.loads(raw).items()}
        except Exception:  # noqa: BLE001
            pass
    row = await db.pool.fetchrow(
        "SELECT topic_weights FROM user_preference_vectors WHERE user_id=$1",
        user_id,
    )
    if row and row["topic_weights"]:
        import json as _json

        return {k: float(v) for k, v in _json.loads(row["topic_weights"]).items()}
    declared = await db.pool.fetchrow(
        "SELECT topic_prefs FROM users WHERE id=$1", user_id
    )
    if declared and declared["topic_prefs"]:
        return {t: 1.0 for t in declared["topic_prefs"]}
    return {}


@asynccontextmanager
async def lifespan(db: DB, redis: RedisCli) -> AsyncIterator[None]:
    await db.start()
    await redis.start()
    try:
        yield
    finally:
        await redis.stop()
        await db.stop()
