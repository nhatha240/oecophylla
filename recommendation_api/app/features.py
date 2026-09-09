from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID

from prometheus_client import Counter, Histogram

from .db import DB
from .schemas import CandidatePost


POOL_SIZE = Histogram(
    "recommendation_candidate_pool_size",
    "Final eligible deduplicated pool size",
    buckets=(0, 10, 50, 100, 200, 300, 600, 1000),
)
POOL_DEDUP = Counter(
    "recommendation_candidate_deduplicated_total",
    "Candidates removed by cross-source deduplication",
)
POOL_BACKFILL = Counter(
    "recommendation_candidate_backfilled_total",
    "Candidates added after source underfill",
)

CANDIDATE_SOURCE_REQUESTS = Counter(
    "recommendation_candidate_source_requests_total",
    "Candidate retrieval queries by source.",
    ("source",),
)
CANDIDATE_SOURCE_RESULTS = Counter(
    "recommendation_candidate_source_results_total",
    "Eligible candidates returned by each retrieval source.",
    ("source",),
)
CANDIDATE_EXCLUSIONS = Counter(
    "recommendation_candidate_exclusions_total",
    "User-specific candidate exclusions by reason; 'any' is the unique total.",
    ("reason",),
)


# Keep viewer/cooldown as the first two bind parameters in every candidate query.
# This makes the policy reusable for new retrieval sources and ensures filtering
# happens in PostgreSQL before each source's LIMIT.
_CANDIDATE_EXCLUSION_SQL = """
  AND NOT EXISTS (
      SELECT 1
      FROM interactions i
      WHERE i.user_id = $1
        AND i.post_id = p.id
        AND i.type = 'hide'::interaction_type
  )
  AND NOT EXISTS (
      SELECT 1
      FROM reports r
      WHERE r.reporter_id = $1
        AND r.post_id = p.id
  )
  AND (
      $2 = 0
      OR NOT EXISTS (
          SELECT 1
          FROM behavior_events b
          WHERE b.user_id = $1
            AND b.post_id = p.id
            AND b.event_type IN ('visible', 'view')
            AND b.occurred_at >= now() - make_interval(days => $2)
      )
  )
"""


def _to_candidates(rows: Iterable[object], source: str) -> list[CandidatePost]:
    return [
        CandidatePost(
            id=r["id"],
            author_id=r["author_id"],
            topics=list(r["topics"] or []),
            safety_score=float(r["safety_score"]),
            created_at=r["created_at"],
            source=source,
            content=r.get("content", ""),
        )
        for r in rows
    ]


def _record_source(source: str, candidates: list[CandidatePost]) -> None:
    CANDIDATE_SOURCE_REQUESTS.labels(source=source).inc()
    CANDIDATE_SOURCE_RESULTS.labels(source=source).inc(len(candidates))


async def candidates_from_followed(
    db: DB,
    user_id: UUID,
    limit: int,
    *,
    seen_cooldown_days: int,
) -> list[CandidatePost]:
    rows = await db.pool.fetch(
        f"""
        SELECT p.id, p.author_id, p.topics, p.safety_score, p.created_at, p.content
        FROM posts p
        JOIN follows f ON f.followee_id = p.author_id
        JOIN users author ON author.id = p.author_id AND author.is_active = true
        WHERE f.follower_id = $1
          AND p.status = 'published'
          {_CANDIDATE_EXCLUSION_SQL}
        ORDER BY p.created_at DESC
        LIMIT $3
        """,
        user_id,
        seen_cooldown_days,
        limit,
    )
    candidates = _to_candidates(rows, "follow")
    _record_source("follow", candidates)
    return candidates


async def candidates_from_topics(
    db: DB,
    user_id: UUID,
    topics: Iterable[str],
    limit: int,
    *,
    seen_cooldown_days: int,
) -> list[CandidatePost]:
    topic_list = [t for t in topics if t]
    if not topic_list:
        return []
    rows = await db.pool.fetch(
        f"""
        SELECT p.id, p.author_id, p.topics, p.safety_score, p.created_at, p.content
        FROM posts p
        JOIN users author ON author.id = p.author_id AND author.is_active = true
        WHERE p.status = 'published'
          AND p.topics && $3::text[]
          {_CANDIDATE_EXCLUSION_SQL}
        ORDER BY p.created_at DESC
        LIMIT $4
        """,
        user_id,
        seen_cooldown_days,
        topic_list,
        limit,
    )
    candidates = _to_candidates(rows, "topic")
    _record_source("topic", candidates)
    return candidates


async def candidates_recent(
    db: DB,
    user_id: UUID,
    limit: int,
    *,
    seen_cooldown_days: int,
) -> list[CandidatePost]:
    rows = await db.pool.fetch(
        f"""
        SELECT p.id, p.author_id, p.topics, p.safety_score, p.created_at, p.content
        FROM posts p
        JOIN users author ON author.id = p.author_id AND author.is_active = true
        WHERE p.status = 'published'
          {_CANDIDATE_EXCLUSION_SQL}
        ORDER BY p.created_at DESC
        LIMIT $3
        """,
        user_id,
        seen_cooldown_days,
        limit,
    )
    candidates = _to_candidates(rows, "recent")
    _record_source("recent", candidates)
    return candidates


async def candidates_for_ids(
    db: DB,
    user_id: UUID,
    ids: list[UUID],
    source: str,
    *,
    seen_cooldown_days: int,
) -> list[CandidatePost]:
    if not ids:
        return []
    rows = await db.pool.fetch(
        f"""
        SELECT p.id, p.author_id, p.topics, p.safety_score, p.created_at, p.content
        FROM posts p
        JOIN users author ON author.id = p.author_id AND author.is_active = true
        WHERE p.id = ANY($3::uuid[])
          AND p.status = 'published'
          {_CANDIDATE_EXCLUSION_SQL}
        LIMIT $4
        """,
        user_id,
        seen_cooldown_days,
        ids,
        len(ids),
    )
    candidates = _to_candidates(rows, source)
    _record_source(source, candidates)
    return candidates


async def record_candidate_exclusions(
    db: DB, user_id: UUID, seen_cooldown_days: int
) -> None:
    """Count user-scoped exclusions once per pool build for Prometheus."""
    rows = await db.pool.fetch(
        """
        WITH exclusion_reasons AS (
            SELECT i.post_id, 'hide'::text AS reason
            FROM interactions i
            WHERE i.user_id = $1
              AND i.type = 'hide'::interaction_type

            UNION ALL

            SELECT r.post_id, 'report'::text AS reason
            FROM reports r
            WHERE r.reporter_id = $1

            UNION ALL

            SELECT b.post_id, 'seen'::text AS reason
            FROM behavior_events b
            WHERE $2 > 0
              AND b.user_id = $1
              AND b.event_type IN ('visible', 'view')
              AND b.occurred_at >= now() - make_interval(days => $2)
        ), eligible_exclusions AS (
            SELECT DISTINCT e.post_id, e.reason
            FROM exclusion_reasons e
            JOIN posts p ON p.id = e.post_id AND p.status = 'published'
            JOIN users author ON author.id = p.author_id AND author.is_active = true
        ), measured AS (
            SELECT reason, count(*)::bigint AS excluded
            FROM eligible_exclusions
            GROUP BY reason

            UNION ALL

            SELECT 'any'::text, count(DISTINCT post_id)::bigint
            FROM eligible_exclusions
        )
        SELECT reason, excluded
        FROM measured
        """,
        user_id,
        seen_cooldown_days,
    )
    for row in rows:
        CANDIDATE_EXCLUSIONS.labels(reason=row["reason"]).inc(row["excluded"])


async def gather_candidates(
    db: DB,
    user_id: UUID,
    user_vec: dict[str, float],
    pool_size: int,
    *,
    seen_cooldown_days: int,
    exclude_post_ids: Iterable[UUID] = (),
    semantic_candidates: Iterable[CandidatePost] = (),
) -> list[CandidatePost]:
    excluded = set(exclude_post_ids)
    if pool_size <= 0:
        return []
    follow_n = max(1, pool_size // 3)
    topic_n = max(1, pool_size // 3)
    recent_n = max(1, pool_size - follow_n - topic_n)

    await record_candidate_exclusions(db, user_id, seen_cooldown_days)

    by_id: dict[UUID, CandidatePost] = {}
    for batch in (
        list(semantic_candidates)[: pool_size // 4],
        await candidates_from_followed(
            db,
            user_id,
            follow_n,
            seen_cooldown_days=seen_cooldown_days,
        ),
        await candidates_from_topics(
            db,
            user_id,
            sorted(user_vec, key=user_vec.get, reverse=True)[:5],
            topic_n,
            seen_cooldown_days=seen_cooldown_days,
        ),
        await candidates_recent(
            db,
            user_id,
            recent_n,
            seen_cooldown_days=seen_cooldown_days,
        ),
    ):
        for c in batch:
            # First seen wins so the higher-quality source ("follow" > "topic" > "recent") sticks.
            if c.id in excluded:
                continue
            if c.id in by_id:
                POOL_DEDUP.inc()
            by_id.setdefault(c.id, c)
    # Over-fetch by the unique existing/excluded IDs so overlaps cannot underfill
    # the requested size when that many eligible recent posts exist.
    if len(by_id) < pool_size:
        backfill = await candidates_recent(
            db,
            user_id,
            pool_size + len(by_id) + len(excluded),
            seen_cooldown_days=seen_cooldown_days,
        )
        for c in backfill:
            if c.id not in excluded and c.id not in by_id:
                by_id[c.id] = c
                POOL_BACKFILL.inc()
            if len(by_id) >= pool_size:
                break
    result = list(by_id.values())[:pool_size]
    POOL_SIZE.observe(len(result))
    return result


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


async def aggregate_topic_weights(db: DB, user_id: UUID) -> dict[str, float]:
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
    rows = await db.pool.fetch("SELECT DISTINCT user_id FROM interactions")
    return [r["user_id"] for r in rows]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def candidates_semantic(db, redis, user_id, *, config, observed_at):
    """Exact cosine search over a bounded recent eligible window (no pgvector).

    It is deliberately a supplemental source, not a full-catalog ANN claim.
    Current content hashes and encoder version must match before scoring.
    """
    import math
    import numpy as np
    from workers.nlp_worker.app.content_features import ENCODER_VERSION, content_hash
    from .db import fetch_user_history
    from .serving_context import _embedding

    snapshot = await fetch_user_history(
        db, redis, user_id, at=observed_at, config=config
    )
    vectors = [
        _embedding(e.embedding, 384)
        for e in snapshot.entries
        if e.encoder_version == ENCODER_VERSION
    ]
    if not vectors:
        return []
    query = np.mean(vectors, axis=0)
    norm = float(np.linalg.norm(query))
    if not math.isfinite(norm) or norm == 0:
        return []
    query /= norm
    rows = await db.pool.fetch(
        f"""
        WITH eligible AS (
            SELECT p.id, p.author_id, p.topics, p.safety_score, p.created_at, p.content
            FROM posts p
            JOIN users author ON author.id = p.author_id AND author.is_active = true
            WHERE p.status = 'published' AND p.created_at <= $4
              {_CANDIDATE_EXCLUSION_SQL}
            ORDER BY p.created_at DESC, p.id LIMIT 2000
        )
        SELECT p.*, f.embedding, f.content_hash
        FROM eligible p
        JOIN LATERAL (
            SELECT embedding, content_hash FROM post_content_features
            WHERE post_id = p.id AND encoder_version = $3
              AND source_updated_at <= $4 AND computed_at <= $4
            ORDER BY source_updated_at DESC, computed_at DESC, id DESC LIMIT 1
        ) f ON true
        """,
        user_id,
        config.seen_cooldown_days,
        ENCODER_VERSION,
        observed_at,
    )
    candidates = []
    for row in rows:
        try:
            if row["content_hash"] != content_hash(row["content"]):
                continue
            vector = _embedding(row["embedding"], 384)
        except (ValueError, TypeError):
            continue
        candidate = _to_candidates([row], "semantic")[0]
        candidate.retrieval_score = float(np.dot(query, vector))
        candidates.append(candidate)
    candidates.sort(key=lambda c: (-c.retrieval_score, str(c.id)))
    result = candidates[: config.feed_candidate_pool // 4]
    _record_source("semantic", result)
    return result
