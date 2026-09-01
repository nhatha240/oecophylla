from __future__ import annotations

import base64
import json
from datetime import datetime

from .embedding_worker import PostFeature, PostRecord


class AsyncpgFeatureRepository:
    def __init__(self, connection) -> None:
        self.connection = connection

    async def get_post(self, post_id: str) -> PostRecord | None:
        row = await self.connection.fetchrow(
            "SELECT id, content, topics, updated_at FROM posts WHERE id = $1",
            post_id,
        )
        if row is None:
            return None
        return PostRecord(
            post_id=str(row["id"]),
            content=row["content"] or "",
            topics=list(row["topics"] or []),
            updated_at=row["updated_at"],
        )

    async def feature_exists(
        self, post_id: str, encoder_version: str, digest: str
    ) -> bool:
        return bool(
            await self.connection.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM post_content_features
                    WHERE post_id = $1 AND encoder_version = $2 AND content_hash = $3
                )
                """,
                post_id,
                encoder_version,
                digest,
            )
        )

    async def insert_feature(self, feature: PostFeature) -> bool:
        inserted_id = await self.connection.fetchval(
            """
            INSERT INTO post_content_features (
                post_id, encoder_version, embedding, normalized_topics,
                content_hash, source_updated_at, computed_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (post_id, encoder_version, content_hash) DO NOTHING
            RETURNING id
            """,
            feature.post_id,
            feature.encoder_version,
            feature.embedding,
            feature.normalized_topics,
            feature.content_hash,
            feature.source_updated_at,
            feature.computed_at,
        )
        return inserted_id is not None

    async def ensure_topics(self, post_id: str, topics: list[str]) -> None:
        await self.connection.execute(
            """
            UPDATE posts SET topics = $1
            WHERE id = $2 AND coalesce(cardinality(topics), 0) = 0
            """,
            topics,
            post_id,
        )

    async def fetch_batch(
        self, cursor: str | None, limit: int
    ) -> tuple[list[PostRecord], str | None]:
        timestamp, post_id = _decode_cursor(cursor)
        rows = await self.connection.fetch(
            """
            SELECT id, content, topics, updated_at
            FROM posts
            WHERE status = 'published'
              AND ($1::timestamptz IS NULL OR (updated_at, id) > ($1, $2::uuid))
            ORDER BY updated_at, id
            LIMIT $3
            """,
            timestamp,
            post_id,
            limit,
        )
        posts = [
            PostRecord(str(row["id"]), row["content"] or "", list(row["topics"] or []), row["updated_at"])
            for row in rows
        ]
        if not rows:
            return posts, None
        last = rows[-1]
        return posts, _encode_cursor(last["updated_at"], str(last["id"]))


def _encode_cursor(timestamp: datetime, post_id: str) -> str:
    payload = json.dumps(
        {"updated_at": timestamp.isoformat(), "post_id": post_id},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode()


def _decode_cursor(cursor: str | None) -> tuple[datetime | None, str | None]:
    if not cursor:
        return None, None
    payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
    return datetime.fromisoformat(payload["updated_at"]), payload["post_id"]
