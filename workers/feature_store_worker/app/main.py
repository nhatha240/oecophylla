from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from collections import defaultdict
from typing import Any

import asyncpg
import redis.asyncio as redis_async
from aiokafka import AIOKafkaConsumer

from .features import apply_topic_delta
from .settings import settings as load_settings

logger = logging.getLogger("feature_store_worker")

UUID_KEYS = ("user_id", "reporter_id", "commenter_id")


class Worker:
    def __init__(self) -> None:
        self.cfg = load_settings()
        self.pool: asyncpg.Pool | None = None
        self.redis: redis_async.Redis | None = None
        self.consumer: AIOKafkaConsumer | None = None
        self._buffer: list[dict[str, Any]] = []
        self._last_flush = time.monotonic()

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
        logger.info("worker started")

    async def stop(self) -> None:
        if self.consumer is not None:
            await self.consumer.stop()
        if self.redis is not None:
            await self.redis.close()
        if self.pool is not None:
            await self.pool.close()

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
                    await self._flush()
                    await self.consumer.commit()
        except asyncio.CancelledError:
            await self._flush()
            with contextlib.suppress(Exception):
                await self.consumer.commit()
            raise

    def _should_flush(self) -> bool:
        return (
            len(self._buffer) >= self.cfg.flush_batch_size
            or (time.monotonic() - self._last_flush) >= self.cfg.flush_interval_seconds
        )

    async def _flush(self) -> None:
        if not self._buffer:
            self._last_flush = time.monotonic()
            return
        events = self._buffer
        self._buffer = []
        self._last_flush = time.monotonic()

        per_user = defaultdict(list)
        for env in events:
            user = _extract_user(env)
            if not user:
                continue
            per_user[user].append(env)

        if per_user:
            assert self.pool is not None
            assert self.redis is not None
            for user_id, user_events in per_user.items():
                try:
                    await self._apply_for_user(user_id, user_events)
                except Exception:  # noqa: BLE001
                    logger.exception("failed to apply features for %s", user_id)

        # Trending sorted set: every event lightly bumps the post regardless of
        # which user produced it.
        try:
            await self._update_trending(events)
        except Exception:  # noqa: BLE001
            logger.exception("failed to update trending")

    async def _apply_for_user(self, user_id: str, events: list[dict]) -> None:
        assert self.pool is not None
        assert self.redis is not None

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT topic_weights FROM user_preference_vectors WHERE user_id=$1",
                user_id,
            )
            vec: dict[str, float] = (
                {k: float(v) for k, v in json.loads(row["topic_weights"]).items()}
                if row
                else {}
            )

            post_ids = {env.get("data", {}).get("post_id") for env in events}
            post_ids = {p for p in post_ids if p}
            topics_by_post: dict[str, list[str]] = {}
            if post_ids:
                rows = await conn.fetch(
                    "SELECT id, topics, tags FROM posts WHERE id = ANY($1::uuid[])",
                    list(post_ids),
                )
                for r in rows:
                    raw_topics: list[str] = list(r["topics"] or [])
                    meaningful = [t for t in raw_topics if t and t != "general"]
                    if meaningful:
                        resolved = raw_topics
                    else:
                        tags: list[str] = list(r["tags"] or [])
                        resolved = tags if tags else raw_topics
                    topics_by_post[str(r["id"])] = resolved

            for env in events:
                etype = env.get("event_type") or env.get("type") or ""
                pid = env.get("data", {}).get("post_id")
                topics = topics_by_post.get(str(pid), [])
                vec = apply_topic_delta(vec, topics, etype)

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

        await self.redis.setex(
            f"pref:{user_id}", self.cfg.pref_ttl_seconds, json.dumps(vec)
        )

    async def _update_trending(self, events: list[dict]) -> None:
        assert self.redis is not None
        score_by_post: dict[str, float] = defaultdict(float)
        for env in events:
            etype = env.get("event_type") or env.get("type") or ""
            pid = env.get("data", {}).get("post_id")
            if not pid:
                continue
            # Map back to interaction weight; negative events erode trending.
            from .features import WEIGHTS

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
