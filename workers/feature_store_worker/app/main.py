from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import asyncpg
import redis.asyncio as redis_async
from aiokafka import AIOKafkaConsumer
from prometheus_client import Counter, start_http_server

from .features import WEIGHTS, apply_topic_delta
from .settings import settings as load_settings

logger = logging.getLogger("feature_store_worker")

UUID_KEYS = ("user_id", "reporter_id", "commenter_id")
IGNORED_EVENT_TYPES = frozenset({"visible", "dwell"})

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
    applied_events: list[dict[str, Any]]
    duplicate_events: list[dict[str, Any]]
    ignored_events: list[dict[str, Any]]


class Worker:
    def __init__(self) -> None:
        self.cfg = load_settings()
        self.pool: asyncpg.Pool | None = None
        self.redis: redis_async.Redis | None = None
        self.consumer: AIOKafkaConsumer | None = None
        self._buffer: list[dict[str, Any]] = []
        self._last_flush = time.monotonic()
        self._metrics_server: Any | None = None

    async def start(self) -> None:
        self.pool = await asyncpg.create_pool(
            self.cfg.database_url, min_size=1, max_size=8
        )
        self.redis = redis_async.from_url(self.cfg.redis_url, decode_responses=True)
        self.consumer = AIOKafkaConsumer(
            self.cfg.interactions_topic,
            bootstrap_servers=self.cfg.kafka_brokers,
            group_id=self.cfg.consumer_group,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
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
                msgs = await self.consumer.getmany(
                    timeout_ms=int(self.cfg.flush_interval_seconds * 1000),
                    max_records=self.cfg.flush_batch_size,
                )
                for tp, batch in msgs.items():
                    for record in batch:
                        if record.value:
                            self._buffer.append(record.value)
                if self._should_flush():
                    ok = await self._flush()
                    # Only advance the committed offset when every user's
                    # features applied cleanly. On a transient failure the
                    # offending events are re-queued and the offset is left
                    # uncommitted so the batch is retried instead of lost.
                    if ok:
                        await self.consumer.commit()
        except asyncio.CancelledError:
            ok = await self._flush()
            if ok:
                with contextlib.suppress(Exception):
                    await self.consumer.commit()
            raise

    def _should_flush(self) -> bool:
        return (
            len(self._buffer) >= self.cfg.flush_batch_size
            or (time.monotonic() - self._last_flush) >= self.cfg.flush_interval_seconds
        )

    async def _flush(self) -> bool:
        """Apply buffered events. Returns True if every user's features were
        applied; on partial failure the failed users' events are re-queued and
        False is returned so the caller leaves the Kafka offset uncommitted."""
        if not self._buffer:
            self._last_flush = time.monotonic()
            return True
        events = self._buffer
        self._buffer = []
        self._last_flush = time.monotonic()

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
            if not user or _event_id(env) is None:
                _record_outcome("unknown", event_type)
                continue
            per_user[user].append(env)

        failed_events: list[dict[str, Any]] = []
        if per_user:
            assert self.pool is not None
            assert self.redis is not None
            for user_id, user_events in per_user.items():
                try:
                    result = await self._apply_for_user(user_id, user_events)
                    for env in result.applied_events:
                        _record_outcome("applied", _event_type(env))
                    for env in result.duplicate_events:
                        _record_outcome("duplicate", _event_type(env))
                    for env in result.ignored_events:
                        _record_outcome("ignored", _event_type(env))
                except Exception:  # noqa: BLE001
                    logger.exception("failed to apply features for %s", user_id)
                    failed_events.extend(user_events)

        # Trending is deliberately approximate and is not receipt-deduplicated.
        # It must never be treated as a ground-truth training label. A failure
        # here is logged but does not block the Kafka offset commit.
        try:
            await self._update_trending(events)
        except Exception:  # noqa: BLE001
            logger.exception("failed to update trending")

        if failed_events:
            # Re-queue for the next flush so the events are retried rather than
            # silently dropped along with the committed offset.
            self._buffer = failed_events + self._buffer
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

        async with self.pool.acquire() as conn:
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
                    env for env in unique_events if str(_event_id(env)) not in claimed_ids
                )

                row = await conn.fetchrow(
                    """
                    SELECT
                        EXISTS(SELECT 1 FROM users WHERE id=$1::uuid) AS user_exists,
                        (SELECT topic_weights
                         FROM user_preference_vectors
                         WHERE user_id=$1::uuid) AS topic_weights
                    """,
                    user_id,
                )
                user_exists = bool(row["user_exists"])
                vec = _decode_weights(row["topic_weights"])
                ignored_events: list[dict[str, Any]] = []
                if not user_exists:
                    ignored_events = applied_events
                    applied_events = []

                if applied_events:
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

        if user_exists:
            await self.redis.setex(
                f"pref:{user_id}", self.cfg.pref_ttl_seconds, json.dumps(vec)
            )
        return ApplyResult(vec, applied_events, duplicate_events, ignored_events)

    async def _update_trending(self, events: list[dict]) -> None:
        assert self.redis is not None
        score_by_post: dict[str, float] = defaultdict(float)
        for env in events:
            etype = _event_type(env)
            pid = env.get("data", {}).get("post_id")
            if not pid:
                continue
            score_by_post[str(pid)] += WEIGHTS.get(etype, 0.0)
        if not score_by_post:
            return
        async with self.redis.pipeline() as pipe:
            for pid, delta in score_by_post.items():
                if delta != 0.0:
                    pipe.zincrby("trending:24h", delta, pid)
            pipe.expire("trending:24h", self.cfg.trending_ttl_seconds)
            await pipe.execute()


def _extract_user(env: dict[str, Any]) -> str | None:
    data = env.get("data") or {}
    for key in UUID_KEYS:
        if data.get(key):
            return str(data[key])
    return None


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
        return version in (2, "2", "v2") and isinstance(duration, int) and duration >= qualified_read_ms
    return True


def _occurred_at(env: dict[str, Any]) -> datetime:
    raw = env.get("occurred_at")
    if isinstance(raw, str):
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _decode_weights(raw: Any) -> dict[str, float]:
    value = json.loads(raw) if isinstance(raw, str) else raw
    return {str(key): float(weight) for key, weight in (value or {}).items()}


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
