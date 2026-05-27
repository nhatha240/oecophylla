import asyncio
import json
import logging
import unicodedata
from aiokafka import AIOKafkaConsumer
import asyncpg
from .settings import Settings
from .infer import infer_topics

logger = logging.getLogger("nlp_worker.consumer")


async def run_consumer(cfg: Settings) -> None:
    """
    Consumes oecophylla.content.created, infers topics, updates posts.topics.
    Idempotent: skip if topics already non-empty.
    Micro-batch: flush every cfg.flush_interval_seconds OR cfg.flush_batch_size events.
    """
    conn = await asyncpg.connect(cfg.database_url)
    consumer = AIOKafkaConsumer(
        cfg.content_created_topic,
        bootstrap_servers=cfg.kafka_brokers,
        group_id=cfg.consumer_group,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda b: json.loads(b.decode()),
    )
    await consumer.start()
    logger.info("nlp-worker consumer started")
    try:
        batch = []
        last_flush = asyncio.get_event_loop().time()
        async for msg in consumer:
            batch.append(msg)
            elapsed = asyncio.get_event_loop().time() - last_flush
            if len(batch) >= cfg.flush_batch_size or elapsed >= cfg.flush_interval_seconds:
                await _process_batch(conn, batch)
                batch.clear()
                last_flush = asyncio.get_event_loop().time()
    finally:
        if batch:
            await _process_batch(conn, batch)
        await consumer.stop()
        await conn.close()


async def _process_batch(conn: asyncpg.Connection, messages: list) -> None:
    for msg in messages:
        try:
            await _process_one(conn, msg.value)
        except Exception as e:
            logger.error("Failed to process message: %s", e, exc_info=True)


async def _process_one(conn: asyncpg.Connection, envelope: dict) -> None:
    data = envelope.get("data", {})
    post_id = data.get("post_id")
    if not post_id:
        return

    # Idempotency check: skip if topics already set
    row = await conn.fetchrow(
        "SELECT content, topics FROM posts WHERE id = $1",
        post_id,
    )
    if row is None:
        logger.warning("Post %s not found, skipping", post_id)
        return

    existing_topics = row["topics"] or []
    if existing_topics:
        logger.debug("Post %s already has topics %s, skipping", post_id, existing_topics)
        return

    content = row["content"] or ""
    topics = infer_topics(content)

    # Update only if topics still empty (race-safe via WHERE clause)
    result = await conn.execute(
        "UPDATE posts SET topics = $1 WHERE id = $2 AND coalesce(cardinality(topics), 0) = 0",
        topics,
        post_id,
    )
    logger.info("Post %s → topics %s (result=%s)", post_id, topics, result)
