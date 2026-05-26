from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID

from .db import DB
from .schemas import CandidatePost


async def candidates_from_followed(
    db: DB, user_id: UUID, limit: int
) -> list[CandidatePost]:
    rows = await db.pool.fetch(
        """
        SELECT p.id, p.author_id, p.topics, p.safety_score, p.created_at
        FROM posts p
        JOIN follows f ON f.followee_id = p.author_id
        WHERE f.follower_id = $1
          AND p.status = 'published'
        ORDER BY p.created_at DESC
        LIMIT $2
        """,
        user_id,
        limit,
    )
    return [
        CandidatePost(
            id=r["id"],
            author_id=r["author_id"],
            topics=list(r["topics"] or []),
            safety_score=float(r["safety_score"]),
            created_at=r["created_at"],
            source="follow",
        )
        for r in rows
    ]


async def candidates_from_topics(
    db: DB, topics: Iterable[str], limit: int
) -> list[CandidatePost]:
    topic_list = [t for t in topics if t]
    if not topic_list:
        return []
    rows = await db.pool.fetch(
        """
        SELECT id, author_id, topics, safety_score, created_at
        FROM posts
        WHERE status = 'published'
          AND topics && $1::text[]
        ORDER BY created_at DESC
        LIMIT $2
        """,
        topic_list,
        limit,
    )
    return [
        CandidatePost(
            id=r["id"],
            author_id=r["author_id"],
            topics=list(r["topics"] or []),
            safety_score=float(r["safety_score"]),
            created_at=r["created_at"],
            source="topic",
        )
        for r in rows
    ]


async def candidates_recent(db: DB, limit: int) -> list[CandidatePost]:
    rows = await db.pool.fetch(
        """
        SELECT id, author_id, topics, safety_score, created_at
        FROM posts
        WHERE status = 'published'
        ORDER BY created_at DESC
        LIMIT $1
        """,
        limit,
    )
    return [
        CandidatePost(
            id=r["id"],
            author_id=r["author_id"],
            topics=list(r["topics"] or []),
            safety_score=float(r["safety_score"]),
            created_at=r["created_at"],
            source="recent",
        )
        for r in rows
    ]


async def candidates_for_ids(
    db: DB, ids: list[UUID], source: str
) -> list[CandidatePost]:
    if not ids:
        return []
    rows = await db.pool.fetch(
        """
        SELECT id, author_id, topics, safety_score, created_at
        FROM posts
        WHERE id = ANY($1::uuid[])
          AND status = 'published'
        """,
        ids,
    )
    return [
        CandidatePost(
            id=r["id"],
            author_id=r["author_id"],
            topics=list(r["topics"] or []),
            safety_score=float(r["safety_score"]),
            created_at=r["created_at"],
            source=source,
        )
        for r in rows
    ]


async def gather_candidates(
    db: DB, user_id: UUID, user_vec: dict[str, float], pool_size: int
) -> list[CandidatePost]:
    follow_n = max(1, pool_size // 3)
    topic_n = max(1, pool_size // 3)
    recent_n = max(1, pool_size - follow_n - topic_n)

    by_id: dict[UUID, CandidatePost] = {}
    for batch in (
        await candidates_from_followed(db, user_id, follow_n),
        await candidates_from_topics(
            db, sorted(user_vec, key=user_vec.get, reverse=True)[:5], topic_n
        ),
        await candidates_recent(db, recent_n),
    ):
        for c in batch:
            # First seen wins so the higher-quality source ("follow" > "topic" > "recent") sticks.
            by_id.setdefault(c.id, c)
    return list(by_id.values())


async def upsert_user_vector(db: DB, user_id: UUID, weights: dict[str, float]) -> None:
    import json as _json

    await db.pool.execute(
        """
        INSERT INTO user_preference_vectors (user_id, topic_weights, updated_at)
        VALUES ($1, $2::jsonb, now())
        ON CONFLICT (user_id) DO UPDATE
        SET topic_weights = EXCLUDED.topic_weights, updated_at = now()
        """,
        user_id,
        _json.dumps(weights),
    )


async def aggregate_topic_weights(
    db: DB, user_id: UUID
) -> dict[str, float]:
    """Sum interaction-weighted post topics → user vector."""
    rows = await db.pool.fetch(
        """
        SELECT i.weight, p.topics
        FROM interactions i
        JOIN posts p ON p.id = i.post_id
        WHERE i.user_id = $1
        """,
        user_id,
    )
    out: dict[str, float] = {}
    for r in rows:
        topics = [t for t in (r["topics"] or []) if t]
        if not topics:
            topics = ["general"]
        share = float(r["weight"]) / len(topics)
        for t in topics:
            out[t] = round(out.get(t, 0.0) + share, 4)
    return out


async def all_user_ids_with_interactions(db: DB) -> list[UUID]:
    rows = await db.pool.fetch(
        "SELECT DISTINCT user_id FROM interactions"
    )
    return [r["user_id"] for r in rows]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
