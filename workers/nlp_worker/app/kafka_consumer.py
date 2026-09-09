import asyncio
import json
import logging

import asyncpg
from aiokafka import AIOKafkaConsumer
from oecophylla_worker_common.kafka import MicroBatchBuffer

from .infer import infer_topics
from .runtime import build_service
from .settings import Settings

logger = logging.getLogger("nlp_worker.consumer")

# Backoff between reconnect attempts when Kafka/Postgres is briefly unavailable
# (e.g. a broker restart). Keeps the worker alive and self-healing instead of
# dying permanently on the first connection error.
RECONNECT_DELAY_SECONDS = 5.0


async def run_consumer(cfg: Settings) -> None:
    """Run the consume loop, reconnecting on transient failures.

    A single ``consumer.start()`` that throws (Kafka not yet reachable) used to
    kill the worker for good; now we retry with backoff so a broker restart
    self-heals. Cancellation (graceful shutdown) propagates out cleanly.
    """
    while True:
        try:
            await _run_once(cfg)
            return  # clean completion (only happens if the loop is broken out of)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "nlp-worker consumer error; reconnecting in %ss",
                RECONNECT_DELAY_SECONDS,
            )
            await asyncio.sleep(RECONNECT_DELAY_SECONDS)


async def _run_once(cfg: Settings) -> None:
    """One connect → consume → cleanup cycle.

    Consumes oecophylla.content.created, infers topics, updates posts.topics.
    Idempotent: skip if topics already non-empty.
    Micro-batch: flush every cfg.flush_interval_seconds OR cfg.flush_batch_size events.
    """
    conn = await asyncpg.connect(cfg.database_url)
    consumer = None
    try:
        consumer = AIOKafkaConsumer(
            cfg.content_created_topic,
            cfg.content_updated_topic,
            bootstrap_servers=cfg.kafka_brokers,
            group_id=cfg.consumer_group,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            value_deserializer=lambda b: json.loads(b.decode()),
        )
        await consumer.start()
        logger.info("nlp-worker consumer started")
        embedding_service, repository = build_service(conn, cfg)
        batch = MicroBatchBuffer(
            batch_size=cfg.flush_batch_size,
            flush_interval_seconds=cfg.flush_interval_seconds,
        )
        while True:
            messages = await consumer.getmany(
                timeout_ms=batch.timeout_ms,
                max_records=cfg.flush_batch_size,
            )
            batch.extend_records(messages)
            if batch.ready():
                await _process_batch(
                    conn, batch.drain(), embedding_service, repository
                )
                # If commit fails, Kafka replays this idempotent batch after
                # reconnect. Never process it again during resource cleanup.
                await consumer.commit()
    finally:
        try:
            if consumer is not None:
                await consumer.stop()
        finally:
            await conn.close()


async def _process_batch(
    conn: asyncpg.Connection,
    messages: list,
    embedding_service=None,
    repository=None,
) -> None:
    for msg in messages:
        # Let unexpected failures reach the reconnect loop. With manual Kafka
        # commits this replays the whole micro-batch; feature writes are
        # idempotent, so no event is acknowledged before processing succeeds.
        envelope = getattr(msg, "value", msg)
        await _process_one(conn, envelope, embedding_service, repository)


async def _process_one(
    conn: asyncpg.Connection,
    envelope: dict,
    embedding_service=None,
    repository=None,
) -> None:
    data = envelope.get("data", {})
    post_id = data.get("post_id")
    if not post_id:
        return

    if embedding_service is not None and repository is not None:
        record = await repository.get_post(post_id)
        if record is None:
            logger.warning("content event references a missing post")
            return
        result = await embedding_service.process(record)
        logger.info("content feature processing completed with outcome=%s", result.status)
        return

    # Idempotency check: skip if topics already set
    row = await conn.fetchrow(
        "SELECT content, topics FROM posts WHERE id = $1",
        post_id,
    )
    if row is None:
        logger.warning("content event references a missing post")
        return

    existing_topics = row["topics"] or []
    if existing_topics:
        logger.debug("post already has keyword topics; skipping legacy topic inference")
        return

    content = row["content"] or ""
    topics = infer_topics(content)

    # Update only if topics still empty (race-safe via WHERE clause)
    result = await conn.execute(
        "UPDATE posts SET topics = $1 WHERE id = $2 AND coalesce(cardinality(topics), 0) = 0",
        topics,
        post_id,
    )
    logger.info("legacy keyword topic inference completed (result=%s)", result)
