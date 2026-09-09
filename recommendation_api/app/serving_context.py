"""Batched, as-of NRMS context; missing/stale features fail the entire batch."""

from __future__ import annotations

import math
from datetime import datetime
from uuid import UUID

from workers.nlp_worker.app.content_features import content_hash

from .db import DB, RedisCli, fetch_user_history
from .schemas import CandidatePost


def _embedding(value, dimension: int) -> list[float]:
    result = [float(v) for v in value]
    if len(result) != dimension or not all(math.isfinite(v) for v in result):
        raise ValueError("invalid feature embedding")
    if abs(math.sqrt(sum(v * v for v in result)) - 1) > 0.001:
        raise ValueError("unnormalized feature embedding")
    return result


async def load_nrms_records(
    *,
    db: DB,
    redis: RedisCli,
    user_id: UUID,
    candidates: list[CandidatePost],
    observed_at: datetime,
    encoder_version: str,
    dimension: int,
    config,
) -> list[dict]:
    rows = await db.pool.fetch(
        """
        SELECT post_id, encoder_version, content_hash, embedding, source_updated_at, computed_at
        FROM post_content_features
        WHERE post_id = ANY($1::uuid[])
          AND encoder_version = $2 AND source_updated_at <= $3 AND computed_at <= $3
        ORDER BY post_id, source_updated_at DESC, computed_at DESC, id DESC
        """,
        [c.id for c in candidates],
        encoder_version,
        observed_at,
    )
    features = {}
    for row in rows:
        if (
            row["encoder_version"] == encoder_version
            and row["source_updated_at"] <= row["computed_at"] <= observed_at
        ):
            features.setdefault((row["post_id"], row["content_hash"]), row)
    snapshot = await fetch_user_history(
        db, redis, user_id, at=observed_at, config=config
    )
    history = []
    for entry in snapshot.entries:
        if (
            entry.encoder_version != encoder_version
            or entry.engaged_at >= observed_at
            or entry.feature_computed_at > observed_at
            or entry.feature_source_updated_at > entry.feature_computed_at
        ):
            raise ValueError("incompatible history feature")
        history.append(
            dict(
                ordinal=len(history),
                engaged_at=entry.engaged_at.isoformat(),
                article=dict(embedding=_embedding(entry.embedding, dimension)),
            )
        )
    records = []
    for candidate in candidates:
        feature = features.get((candidate.id, content_hash(candidate.content)))
        if feature is None:
            raise ValueError("missing current candidate feature")
        records.append(
            dict(
                article=dict(embedding=_embedding(feature["embedding"], dimension)),
                history=history,
            )
        )
    return records


async def load_author_context(
    db: DB, user_id: UUID, author_ids: list[UUID], observed_at: datetime
):
    """Affinity = fraction of prior 30-day clicks attributed to this author."""
    rows = await db.pool.fetch(
        """
        WITH prior AS (
            SELECT p.author_id, count(*)::float AS clicks
            FROM behavior_events b JOIN posts p ON p.id = b.post_id
            WHERE b.user_id = $1 AND b.event_type = 'click'
              AND b.occurred_at < $3 AND b.ingested_at <= $3
              AND b.occurred_at >= $3 - interval '30 days'
              AND coalesce(b.event_version, b.metadata->>'event_version') = 'v2'
            GROUP BY p.author_id
        )
        SELECT a.id AS author_id,
               EXISTS (SELECT 1 FROM follows f WHERE f.follower_id = $1
                       AND f.followee_id = a.id AND f.created_at <= $3) AS is_followed,
               coalesce(prior.clicks / nullif((SELECT sum(clicks) FROM prior), 0), 0) AS affinity
        FROM users a LEFT JOIN prior ON prior.author_id = a.id
        WHERE a.id = ANY($2::uuid[])
        """,
        user_id,
        author_ids,
        observed_at,
    )
    return {r["author_id"]: (r["is_followed"], float(r["affinity"])) for r in rows}
