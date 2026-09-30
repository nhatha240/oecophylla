"""One-shot replay of canonical behavior into preference vectors v2.

Run this with the feature worker stopped so a concurrent consumer cannot
overwrite a replayed vector with an older snapshot.
"""

from __future__ import annotations

import argparse
import asyncio
from uuid import UUID

import asyncpg
import redis.asyncio as redis_async

from .main import Worker


PAGE_USERS_SQL = """
    SELECT user_id
    FROM (
        SELECT user_id FROM preference_vector_v2_backfill_users
        UNION
        SELECT user_id FROM user_preference_vectors_v2
    ) AS users
    WHERE ($1::uuid IS NULL OR user_id > $1::uuid)
    ORDER BY user_id
    LIMIT $2
"""

SOURCE_STATUS_SQL = """
    SELECT
        EXISTS (SELECT 1 FROM behavior_events WHERE user_id = $1::uuid) AS has_source,
        EXISTS (SELECT 1 FROM user_preference_vectors_v2 WHERE user_id = $1::uuid)
            AS has_existing_vector
"""

HAS_EXISTING_VECTORS_SQL = """
    SELECT EXISTS (SELECT 1 FROM user_preference_vectors_v2)
"""


async def replay_user(
    worker: Worker, user_id: UUID, *, replace_existing_vectors: bool = False
) -> None:
    """Replay one user after explicit approval to replace an existing vector.

    A surviving behavior row does not prove that retention preserved the full
    history used to build a prior vector. The caller must check that separately.
    """
    assert worker.pool is not None
    async with worker.pool.acquire() as conn:
        status = await conn.fetchrow(SOURCE_STATUS_SQL, user_id)
    if not status["has_source"]:
        raise RuntimeError(f"no canonical behavior_events remain for user {user_id}")
    if status["has_existing_vector"] and not replace_existing_vectors:
        raise RuntimeError(
            f"user {user_id} already has a v2 vector; verify the retained "
            "source history before using --replace-existing-vectors"
        )
    await worker._rebuild_v2_for_user(str(user_id))


async def replay_all(
    worker: Worker, batch_size: int, *, replace_existing_vectors: bool = False
) -> int:
    """Keyset-page through every current or previously built v2 user."""
    assert worker.pool is not None
    if not replace_existing_vectors:
        async with worker.pool.acquire() as conn:
            has_existing_vectors = await conn.fetchval(HAS_EXISTING_VECTORS_SQL)
        if has_existing_vectors:
            raise RuntimeError(
                "v2 vectors already exist; verify the retained source history "
                "before using --replace-existing-vectors"
            )
    cursor: UUID | None = None
    rebuilt = 0
    while True:
        async with worker.pool.acquire() as conn:
            page = await conn.fetch(PAGE_USERS_SQL, cursor, batch_size)
        if not page:
            return rebuilt
        for row in page:
            user_id = UUID(str(row["user_id"]))
            await replay_user(
                worker, user_id, replace_existing_vectors=replace_existing_vectors
            )
            cursor = user_id
            rebuilt += 1


async def run_rebuild(
    user_id: UUID | None,
    all_users: bool,
    batch_size: int,
    *,
    replace_existing_vectors: bool = False,
) -> int:
    if not all_users and user_id is None:
        raise ValueError("choose --all or --user-id")
    if batch_size <= 0:
        raise ValueError("batch size must be positive")

    worker = Worker()
    worker.pool = await asyncpg.create_pool(
        worker.cfg.database_url, min_size=1, max_size=2
    )
    try:
        worker.redis = redis_async.from_url(worker.cfg.redis_url, decode_responses=True)
        if all_users:
            return await replay_all(
                worker, batch_size, replace_existing_vectors=replace_existing_vectors
            )
        assert user_id is not None
        await replay_user(
            worker, user_id, replace_existing_vectors=replace_existing_vectors
        )
        return 1
    finally:
        if worker.redis is not None:
            await worker.redis.close()
        await worker.pool.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--all", action="store_true", help="replay every vector")
    target.add_argument("--user-id", type=UUID, help="replay one user's vector")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--replace-existing-vectors",
        action="store_true",
        help="permit replacing existing v2 vectors after checking source completeness",
    )
    args = parser.parse_args()
    rebuilt = asyncio.run(
        run_rebuild(
            args.user_id,
            args.all,
            args.batch_size,
            replace_existing_vectors=args.replace_existing_vectors,
        )
    )
    print(f"rebuilt {rebuilt} preference vector(s) v2")


if __name__ == "__main__":
    main()
