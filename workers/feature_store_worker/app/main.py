from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import asyncpg
import redis.asyncio as redis_async
from prometheus_client import Counter, start_http_server
from oecophylla_worker_common.kafka import MicroBatchBuffer, build_json_consumer

from .features import (
    PREFERENCE_SCHEMA_V2,
    WEIGHTS,
    PreferenceEvent,
    PreferenceVectorV2,
    apply_topic_delta,
    build_preference_vector_v2,
)
from .recent_topics import WINDOW_DAYS, ranked_view_topics
from .settings import settings as load_settings

logger = logging.getLogger("feature_store_worker")

UUID_KEYS = ("user_id", "reporter_id", "commenter_id")
IGNORED_EVENT_TYPES = frozenset({"visible"})

FEATURE_EVENT_OUTCOMES = Counter(
    "feature_worker_events_total",
    "Kafka feature events by processing outcome and event type.",
    ("outcome", "event_type"),
)

CLAIM_RECEIPTS_SQL = """
    WITH incoming AS (
        SELECT *
        FROM unnest($1::uuid[], $2::text[], $3::timestamptz[])
             AS batch(event_id, event_type, occurred_at)
    )
    INSERT INTO feature_event_receipts (event_id, user_id, event_type, occurred_at)
    SELECT batch.event_id, $4::uuid, batch.event_type, batch.occurred_at
    FROM incoming AS batch
    ON CONFLICT (event_id) DO NOTHING
    RETURNING event_id
"""


@dataclass(frozen=True)
class ApplyResult:
    vector: dict[str, float]
    vector_v2: PreferenceVectorV2 | None
    applied_events: list[dict[str, Any]]
    duplicate_events: list[dict[str, Any]]
    ignored_events: list[dict[str, Any]]


class Worker:
    def __init__(self) -> None:
        self.cfg = load_settings()
        self.pool: asyncpg.Pool | None = None
        self.redis: redis_async.Redis | None = None
        self.consumer: Any | None = None
        self._batch = MicroBatchBuffer(
            batch_size=self.cfg.flush_batch_size,
            flush_interval_seconds=self.cfg.flush_interval_seconds,
        )
        self._metrics_server: Any | None = None
        self._last_recent_refresh = datetime.min.replace(tzinfo=timezone.utc)

    @property
    def _buffer(self) -> list[dict[str, Any]]:
        return self._batch.values

    @_buffer.setter
    def _buffer(self, values: list[dict[str, Any]]) -> None:
        self._batch.replace(values)

    async def start(self) -> None:
        self.pool = await asyncpg.create_pool(
            self.cfg.database_url, min_size=1, max_size=8
        )
        self.redis = redis_async.from_url(self.cfg.redis_url, decode_responses=True)
        if self.cfg.preference_backfill_on_start:
            await self._backfill_v2()
        await self._refresh_due_recent_topics()
        self.consumer = build_json_consumer(
            topic=self.cfg.interactions_topic,
            brokers=self.cfg.kafka_brokers,
            group_id=self.cfg.consumer_group,
            enable_auto_commit=False,
        )
        await self.consumer.start()
        self._metrics_server, _thread = start_http_server(self.cfg.metrics_port)
        logger.info("worker started")

    async def stop(self) -> None:
        if self.consumer is not None:
            await self.consumer.stop()
        if self.redis is not None:
            await self.redis.close()
        if self.pool is not None:
            await self.pool.close()
        if self._metrics_server is not None:
            self._metrics_server.shutdown()
            self._metrics_server.server_close()

    async def run(self) -> None:
        assert self.consumer is not None
        try:
            while True:
                # Wait up to flush_interval for new messages, then flush even
                # if we didn't hit batch size — keeps preference vectors warm
                # under low traffic.
                records = await self.consumer.getmany(
                    timeout_ms=self._batch.timeout_ms,
                    max_records=self.cfg.flush_batch_size,
                )
                self._batch.extend_records(records)
                if self._should_flush():
                    ok = await self._flush()
                    # Only advance the committed offset when every user's
                    # features applied cleanly. On a transient failure the
                    # offending events are re-queued and the offset is left
                    # uncommitted so the batch is retried instead of lost.
                    if ok:
                        await self.consumer.commit()
                if datetime.now(timezone.utc) - self._last_recent_refresh >= timedelta(minutes=1):
                    await self._refresh_due_recent_topics()
        except asyncio.CancelledError:
            ok = await self._flush()
            if ok:
                with contextlib.suppress(Exception):
                    await self.consumer.commit()
            raise

    def _should_flush(self) -> bool:
        return self._batch.ready()

    async def _flush(self) -> bool:
        """Apply buffered events. Returns True if every user's features were
        applied; on partial failure the failed users' events are re-queued and
        False is returned so the caller leaves the Kafka offset uncommitted."""
        if not self._buffer:
            self._batch.touch()
            return True
        events = self._batch.drain()

        per_user = defaultdict(list)
        for env in events:
            event_type = _event_type(env)
            if event_type in IGNORED_EVENT_TYPES:
                _record_outcome("ignored", event_type)
                continue
            if event_type not in WEIGHTS:
                _record_outcome("unknown", event_type or "missing")
                continue
            if not _valid_feature_event(env, self.cfg.qualified_read_ms):
                _record_outcome("invalid", event_type)
                continue
            user = _extract_user(env)
            if user is None:
                outcome = "invalid" if _identity_field_is_present(env) else "unknown"
                _record_outcome(outcome, event_type)
                continue
            if _event_id(env) is None:
                _record_outcome("unknown", event_type)
                continue
            per_user[user].append(env)

        failed_events: list[dict[str, Any]] = []
        trending_events: list[dict[str, Any]] = []
        if per_user:
            assert self.pool is not None
            assert self.redis is not None
            for user_id, user_events in per_user.items():
                try:
                    result = await self._apply_for_user(user_id, user_events)
                    trending_events.extend(result.applied_events)
                    for env in result.applied_events:
                        _record_outcome("applied", _event_type(env))
                    for env in result.duplicate_events:
                        _record_outcome("duplicate", _event_type(env))
                    for env in result.ignored_events:
                        _record_outcome("ignored", _event_type(env))
                except Exception:
                    logger.exception("failed to apply preference features")
                    failed_events.extend(user_events)

        # Only count events whose receipts and features committed. Trending is
        # still approximate: if Redis fails after the receipt commits, a replay
        # cannot recover the missed increment. Trending failures are logged but
        # do not block the Kafka offset commit or retry an uncertain increment.
        if trending_events:
            try:
                await self._update_trending(trending_events)
            except Exception:
                logger.exception("failed to update trending")

        if failed_events:
            # Re-queue for the next flush so the events are retried rather than
            # silently dropped along with the committed offset.
            self._batch.prepend(failed_events)
            return False
        return True

    async def _apply_for_user(
        self, user_id: str, events: list[dict[str, Any]]
    ) -> ApplyResult:
        assert self.pool is not None
        assert self.redis is not None

        unique_events: list[dict[str, Any]] = []
        duplicate_events: list[dict[str, Any]] = []
        seen_ids: set[UUID] = set()
        for env in events:
            event_id = _event_id(env)
            if event_id is None:
                continue
            if event_id in seen_ids:
                duplicate_events.append(env)
            else:
                seen_ids.add(event_id)
                unique_events.append(env)

        async with self.pool.acquire() as conn:  # noqa: SIM117
            async with conn.transaction():
                claimed_rows = await conn.fetch(
                    CLAIM_RECEIPTS_SQL,
                    [_event_id(env) for env in unique_events],
                    [_event_type(env) for env in unique_events],
                    [_occurred_at(env) for env in unique_events],
                    UUID(user_id),
                )
                claimed_ids = {str(row["event_id"]) for row in claimed_rows}
                applied_events = [
                    env for env in unique_events if str(_event_id(env)) in claimed_ids
                ]
                duplicate_events.extend(
                    env
                    for env in unique_events
                    if str(_event_id(env)) not in claimed_ids
                )

                row = await conn.fetchrow(
                    """
                    SELECT
                        EXISTS(SELECT 1 FROM users WHERE id=$1::uuid) AS user_exists,
                        (SELECT topic_weights
                         FROM user_preference_vectors
                         WHERE user_id=$1::uuid) AS topic_weights,
                        (SELECT jsonb_build_object(
                            'schema_version', schema_version,
                            'positive', positive_weights,
                            'negative', negative_weights,
                            'reference_at', reference_at,
                            'source_event_count', source_event_count
                         )
                         FROM user_preference_vectors_v2
                         WHERE user_id=$1::uuid) AS vector_v2
                    """,
                    user_id,
                )
                user_exists = bool(row["user_exists"])
                vec = _decode_weights(row["topic_weights"])
                vector_v2 = _decode_vector_v2(row.get("vector_v2"))
                ignored_events: list[dict[str, Any]] = []
                if not user_exists:
                    ignored_events = applied_events
                    applied_events = []

                if any(_event_type(env) != "view_observed" for env in applied_events):
                    post_ids = {
                        env.get("data", {}).get("post_id") for env in applied_events
                    }
                    post_ids = {post_id for post_id in post_ids if post_id}
                    topics_by_post: dict[str, list[str]] = {}
                    if post_ids:
                        rows = await conn.fetch(
                            "SELECT id, topics, tags FROM posts WHERE id = ANY($1::uuid[])",
                            list(post_ids),
                        )
                        for post in rows:
                            raw_topics: list[str] = list(post["topics"] or [])
                            meaningful = [
                                topic
                                for topic in raw_topics
                                if topic and topic != "general"
                            ]
                            if meaningful:
                                resolved = raw_topics
                            else:
                                tags: list[str] = list(post["tags"] or [])
                                resolved = tags if tags else raw_topics
                            topics_by_post[str(post["id"])] = resolved

                    for env in applied_events:
                        event_type = _event_type(env)
                        post_id = env.get("data", {}).get("post_id")
                        topics = topics_by_post.get(str(post_id), [])
                        vec = apply_topic_delta(vec, topics, event_type)

                    canonical_rows = await conn.fetch(
                        """
                        SELECT
                            event.id::text AS event_id,
                            event.post_id::text AS post_id,
                            event.impression_id::text AS impression_id,
                            event.session_id::text AS session_id,
                            event.event_type,
                            event.dwell_ms,
                            event.metadata ->> 'trigger' AS read_trigger,
                            event.metadata ->> 'visit_id' AS visit_id,
                            event.topic_snapshot,
                            event.occurred_at,
                            post.topics,
                            post.tags
                        FROM behavior_events AS event
                        JOIN posts AS post ON post.id = event.post_id
                        WHERE event.user_id = $1::uuid
                        ORDER BY event.occurred_at, event.id
                        """,
                        user_id,
                    )
                    canonical_events = _canonical_preference_events(canonical_rows)
                    if canonical_events:
                        # The reference clock comes only from event timestamps,
                        # never Kafka delivery/worker wall time.
                        vector_v2 = build_preference_vector_v2(
                            canonical_events,
                            half_life_hours=self.cfg.preference_half_life_hours,
                            channel_bound=self.cfg.preference_channel_bound,
                            qualified_read_ms=self.cfg.qualified_read_ms,
                        )

                    await conn.execute(
                        """
                        INSERT INTO user_preference_vectors (user_id, topic_weights, updated_at)
                        VALUES ($1, $2::jsonb, now())
                        ON CONFLICT (user_id) DO UPDATE
                        SET topic_weights = EXCLUDED.topic_weights, updated_at = now()
                        """,
                        user_id,
                        json.dumps(vec),
                    )
                    if vector_v2 is not None:
                        await _upsert_vector_v2(conn, user_id, vector_v2)
                if any(
                    _event_type(env)
                    in {"viewed", "view_observed", "qualified_read", "dwell"}
                    for env in applied_events
                ):
                    await _refresh_recent_topics_for_user(conn, user_id)

        if user_exists:
            await _refresh_preference_cache(
                self.redis,
                user_id,
                vec,
                vector_v2,
                self.cfg.pref_ttl_seconds,
            )
        return ApplyResult(
            vec, vector_v2, applied_events, duplicate_events, ignored_events
        )

    async def _backfill_v2(self) -> None:
        """Replay canonical behavior rows for users not yet on v2.

        The view and v2 table make this restart-safe. A partial run simply
        resumes with the remaining users on the next worker start.
        """
        assert self.pool is not None
        assert self.redis is not None
        while True:
            rows = await self.pool.fetch(
                """
                SELECT queue.user_id::text AS user_id
                FROM preference_vector_v2_backfill_users AS queue
                LEFT JOIN user_preference_vectors_v2 AS vector
                  ON vector.user_id = queue.user_id
                WHERE vector.user_id IS NULL
                ORDER BY queue.last_event_at, queue.user_id
                LIMIT $1
                """,
                self.cfg.preference_backfill_batch_size,
            )
            if not rows:
                return
            for row in rows:
                await self._rebuild_v2_for_user(str(row["user_id"]))

    async def _rebuild_v2_for_user(self, user_id: str) -> None:
        assert self.pool is not None
        assert self.redis is not None
        async with self.pool.acquire() as conn:  # noqa: SIM117
            async with conn.transaction():
                rows = await conn.fetch(
                    """
                    SELECT
                        event.id::text AS event_id,
                        event.post_id::text AS post_id,
                        event.impression_id::text AS impression_id,
                        event.session_id::text AS session_id,
                        event.event_type,
                        event.dwell_ms,
                        event.metadata ->> 'trigger' AS read_trigger,
                        event.metadata ->> 'visit_id' AS visit_id,
                        event.topic_snapshot,
                        event.occurred_at,
                        post.topics,
                        post.tags
                    FROM behavior_events AS event
                    JOIN posts AS post ON post.id = event.post_id
                    WHERE event.user_id = $1::uuid
                    ORDER BY event.occurred_at, event.id
                    """,
                    user_id,
                )
                events = _canonical_preference_events(rows)
                if not events:
                    return
                vector = build_preference_vector_v2(
                    events,
                    half_life_hours=self.cfg.preference_half_life_hours,
                    channel_bound=self.cfg.preference_channel_bound,
                    qualified_read_ms=self.cfg.qualified_read_ms,
                )
                await _upsert_vector_v2(conn, user_id, vector)
        await self.redis.delete(*preference_cache_keys(user_id))

    async def _update_trending(self, events: list[dict]) -> None:
        assert self.redis is not None
        score_by_post: dict[str, float] = defaultdict(float)
        for env in events:
            etype = _event_type(env)
            pid = env.get("data", {}).get("post_id")
            delta = WEIGHTS.get(etype, 0.0)
            if not pid or delta == 0.0:
                continue
            score_by_post[str(pid)] += delta
        if not score_by_post:
            return
        async with self.redis.pipeline() as pipe:
            for pid, delta in score_by_post.items():
                if delta != 0.0:
                    pipe.zincrby("trending:24h", delta, pid)
            pipe.expire("trending:24h", self.cfg.trending_ttl_seconds)
            await pipe.execute()

    async def _refresh_due_recent_topics(self) -> None:
        """Expire old inferred topics even when the user generates no new events."""
        assert self.pool is not None
        assert self.redis is not None
        self._last_recent_refresh = datetime.now(timezone.utc)
        rows = await self.pool.fetch(
            """
            SELECT user_id::text AS user_id
            FROM user_recent_topic_preferences
            WHERE next_refresh_at <= now()
            ORDER BY next_refresh_at, user_id
            LIMIT 100
            """
        )
        for row in rows:
            user_id = str(row["user_id"])
            async with self.pool.acquire() as conn:  # noqa: SIM117
                async with conn.transaction():
                    tracked = await conn.fetchrow(
                        "SELECT user_id FROM user_recent_topic_preferences "
                        "WHERE user_id=$1::uuid FOR UPDATE",
                        user_id,
                    )
                    if tracked is None:
                        continue
                    await _refresh_recent_topics_for_user(conn, user_id)
            try:
                await self.redis.delete(*preference_cache_keys(user_id))
            except Exception:
                logger.exception("failed to invalidate refreshed topic preferences")
                await self.pool.execute(
                    "UPDATE user_recent_topic_preferences "
                    "SET next_refresh_at=now() WHERE user_id=$1::uuid",
                    user_id,
                )


def _extract_user(env: dict[str, Any]) -> str | None:
    data = env.get("data")
    if not isinstance(data, dict):
        return None
    for key in UUID_KEYS:
        if key not in data:
            continue
        try:
            return str(UUID(str(data[key])))
        except (TypeError, ValueError, AttributeError):
            return None
    return None


def _identity_field_is_present(env: dict[str, Any]) -> bool:
    data = env.get("data")
    return isinstance(data, dict) and any(key in data for key in UUID_KEYS)


def _event_type(env: dict[str, Any]) -> str:
    return str(env.get("event_type") or env.get("type") or "")


def _event_id(env: dict[str, Any]) -> UUID | None:
    try:
        return UUID(str(env.get("event_id")))
    except (TypeError, ValueError, AttributeError):
        return None


def _valid_feature_event(env: dict[str, Any], qualified_read_ms: int) -> bool:
    event_type = _event_type(env)
    version = env.get("event_version")
    if event_type == "viewed":
        return version in (None, 1, "1", "v1")
    if event_type == "qualified_read":
        duration = (env.get("data") or {}).get("duration_ms")
        return (
            version in (2, "2", "v2")
            and isinstance(duration, int)
            and duration >= qualified_read_ms
        )
    return True


def _occurred_at(env: dict[str, Any]) -> datetime:
    raw = env.get("occurred_at")
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return (
                parsed
                if parsed.tzinfo is not None
                else parsed.replace(tzinfo=timezone.utc)
            )
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _decode_weights(raw: Any) -> dict[str, float]:
    value = json.loads(raw) if isinstance(raw, str) else raw
    return {str(key): float(weight) for key, weight in (value or {}).items()}


def _decode_vector_v2(raw: Any) -> PreferenceVectorV2 | None:
    value = json.loads(raw) if isinstance(raw, str) else raw
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != PREFERENCE_SCHEMA_V2
    ):
        return None
    reference_at = value.get("reference_at")
    if isinstance(reference_at, str):
        reference_at = datetime.fromisoformat(reference_at.replace("Z", "+00:00"))
    if not isinstance(reference_at, datetime) or reference_at.tzinfo is None:
        return None
    return PreferenceVectorV2(
        positive=_decode_weights(value.get("positive")),
        negative=_decode_weights(value.get("negative")),
        reference_at=reference_at,
        source_event_count=int(value.get("source_event_count", 0)),
    )


def _canonical_preference_events(rows: list[Any]) -> list[PreferenceEvent]:
    events: list[PreferenceEvent] = []
    for row in rows:
        topic_snapshot = row.get("topic_snapshot")
        if topic_snapshot is not None:
            # Snapshots are event-time evidence. An empty snapshot is still
            # authoritative and resolves to general in the vector builder.
            topics = [topic for topic in topic_snapshot if topic]
        else:
            # Historical rows predate snapshots and can only use current post
            # classification as a best-effort fallback.
            topics = [
                topic for topic in (row["topics"] or []) if topic and topic != "general"
            ]
            if not topics:
                topics = [tag for tag in (row["tags"] or []) if tag] or ["general"]
        events.append(
            PreferenceEvent(
                event_id=str(row["event_id"]),
                post_id=str(row["post_id"]),
                impression_id=(
                    str(row["impression_id"]) if row["impression_id"] else None
                ),
                session_id=(
                    str(row.get("session_id")) if row.get("session_id") else None
                ),
                visit_id=row.get("visit_id"),
                event_type=str(row["event_type"]),
                dwell_ms=row["dwell_ms"],
                read_trigger=row.get("read_trigger"),
                occurred_at=row["occurred_at"],
                topics=tuple(topics),
            )
        )
    return events


async def _refresh_recent_topics_for_user(
    conn: Any, user_id: str, *, at: datetime | None = None
) -> list[str]:
    """Replace inferred topic_prefs from the current three-week view window."""
    now = at or datetime.now(timezone.utc)
    rows = await conn.fetch(
        """
        SELECT
            event.id::text AS event_id,
            event.post_id::text AS post_id,
            event.impression_id::text AS impression_id,
            event.session_id::text AS session_id,
            event.event_type,
            event.dwell_ms,
            event.metadata ->> 'trigger' AS read_trigger,
            event.metadata ->> 'visit_id' AS visit_id,
            event.topic_snapshot,
            event.occurred_at,
            post.topics,
            post.tags
        FROM behavior_events AS event
        JOIN posts AS post ON post.id = event.post_id
        WHERE event.user_id = $1::uuid
          AND event.event_type IN ('view', 'dwell')
          AND event.occurred_at >= $2
          AND event.occurred_at <= $3
        ORDER BY event.occurred_at, event.id
        """,
        user_id,
        now - timedelta(days=WINDOW_DAYS),
        now,
    )
    topics = ranked_view_topics(_canonical_preference_events(rows), at=now)
    await conn.execute(
        "UPDATE users SET topic_prefs=$2::text[] "
        "WHERE id=$1::uuid AND topic_prefs IS DISTINCT FROM $2::text[]",
        user_id,
        topics,
    )
    await conn.execute(
        """
        INSERT INTO user_recent_topic_preferences
            (user_id, refreshed_at, next_refresh_at)
        VALUES (
            $1::uuid, $2,
            CASE WHEN $3::boolean THEN $2::timestamptz + interval '1 hour'
                 ELSE 'infinity'::timestamptz END
        )
        ON CONFLICT (user_id) DO UPDATE SET
            refreshed_at=EXCLUDED.refreshed_at,
            next_refresh_at=EXCLUDED.next_refresh_at
        """,
        user_id,
        now,
        bool(topics),
    )
    return topics


async def _upsert_vector_v2(
    conn: Any, user_id: str, vector: PreferenceVectorV2
) -> None:
    await conn.execute(
        """
        INSERT INTO user_preference_vectors_v2 (
            user_id, schema_version, positive_weights, negative_weights,
            reference_at, source_event_count, updated_at
        ) VALUES ($1, $2, $3::jsonb, $4::jsonb, $5, $6, now())
        ON CONFLICT (user_id) DO UPDATE SET
            schema_version = EXCLUDED.schema_version,
            positive_weights = EXCLUDED.positive_weights,
            negative_weights = EXCLUDED.negative_weights,
            reference_at = EXCLUDED.reference_at,
            source_event_count = EXCLUDED.source_event_count,
            updated_at = now()
        """,
        user_id,
        vector.schema_version,
        json.dumps(vector.positive),
        json.dumps(vector.negative),
        vector.reference_at,
        vector.source_event_count,
    )


def preference_cache_keys(user_id: str) -> list[str]:
    return [
        f"pref:{user_id}",
        f"pref:v1:{user_id}",
        f"pref:v2:{user_id}",
        f"history:v1:{user_id}",
        f"history:v2:{user_id}",
        f"feed:{user_id}",
        f"feed:v1:{user_id}",
        f"feed:v2:{user_id}",
    ]


async def _refresh_preference_cache(
    redis: Any,
    user_id: str,
    vector_v1: dict[str, float],
    vector_v2: PreferenceVectorV2 | None,
    ttl_seconds: int,
) -> None:
    await redis.delete(*preference_cache_keys(user_id))
    encoded_v1 = json.dumps(vector_v1)
    await redis.setex(f"pref:{user_id}", ttl_seconds, encoded_v1)
    await redis.setex(f"pref:v1:{user_id}", ttl_seconds, encoded_v1)
    if vector_v2 is not None:
        await redis.setex(
            f"pref:v2:{user_id}", ttl_seconds, json.dumps(vector_v2.as_payload())
        )


def _record_outcome(outcome: str, event_type: str) -> None:
    FEATURE_EVENT_OUTCOMES.labels(outcome=outcome, event_type=event_type).inc()


async def _main() -> None:
    logging.basicConfig(level=logging.INFO)
    worker = Worker()
    await worker.start()
    try:
        await worker.run()
    finally:
        await worker.stop()


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
