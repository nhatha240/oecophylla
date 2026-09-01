from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from math import exp2
from typing import Any, AsyncIterator, Optional
from uuid import UUID

import asyncpg
import redis.asyncio as redis_async

from .settings import settings as load_settings


PREFERENCE_SCHEMA_V2 = "preference-vector-v2"


class DB:
    """Lightweight pgpool wrapper. Created at startup, closed at shutdown."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: Optional[asyncpg.Pool] = None

    async def start(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=8)

    async def stop(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("DB pool not started")
        return self._pool


class RedisCli:
    def __init__(self, url: str) -> None:
        self._url = url
        self._cli: Optional[redis_async.Redis] = None

    async def start(self) -> None:
        self._cli = redis_async.from_url(self._url, decode_responses=True)
        await self._cli.ping()

    async def stop(self) -> None:
        if self._cli is not None:
            await self._cli.close()
            self._cli = None

    @property
    def cli(self) -> redis_async.Redis:
        if self._cli is None:
            raise RuntimeError("Redis client not started")
        return self._cli


async def fetch_user_vector(
    db: DB, redis: RedisCli, user_id: UUID, *, config: Any | None = None
) -> dict[str, float]:
    """Load the active preference schema with immediate, non-mixed v1 fallback."""
    import json as _json

    cfg = config or load_settings()
    if cfg.preference_schema_version == "v2":
        raw_v2 = await redis.cli.get(f"pref:v2:{user_id}")
        payload = _decode_v2_payload(raw_v2)
        if payload is not None:
            declared = await _fetch_declared_topics(db, user_id)
            return _merge_with_config(payload, declared, cfg)

        for key in (f"pref:v1:{user_id}", f"pref:{user_id}"):
            raw_v1 = await redis.cli.get(key)
            decoded_v1 = _decode_v1(raw_v1)
            if decoded_v1 is not None:
                return decoded_v1

        row_v2 = await db.pool.fetchrow(
            """
            SELECT schema_version, positive_weights, negative_weights,
                   reference_at, source_event_count
            FROM user_preference_vectors_v2 WHERE user_id=$1
            """,
            user_id,
        )
        payload = _v2_row_payload(row_v2)
        if payload is not None:
            declared = await _fetch_declared_topics(db, user_id)
            return _merge_with_config(payload, declared, cfg)

    else:
        for key in (f"pref:v1:{user_id}", f"pref:{user_id}"):
            raw_v1 = await redis.cli.get(key)
            decoded_v1 = _decode_v1(raw_v1)
            if decoded_v1 is not None:
                return decoded_v1

    row = await db.pool.fetchrow(
        "SELECT topic_weights FROM user_preference_vectors WHERE user_id=$1",
        user_id,
    )
    if row and row["topic_weights"]:
        decoded = _decode_v1(row["topic_weights"])
        if decoded is not None:
            return decoded
    declared = await db.pool.fetchrow(
        "SELECT topic_prefs FROM users WHERE id=$1", user_id
    )
    if declared and declared["topic_prefs"]:
        return {t: 1.0 for t in declared["topic_prefs"]}
    return {}


def merge_preference_vector_v2(
    payload: dict[str, Any],
    declared_topics: list[str],
    *,
    at: datetime | None = None,
    half_life_hours: float,
    behavior_coefficient: float,
    declared_coefficient: float,
    evidence_saturation: float,
) -> dict[str, float]:
    """Project stored event-time channels to serving time and blend sources."""
    if payload.get("schema_version") != PREFERENCE_SCHEMA_V2:
        raise ValueError("unsupported preference schema")
    if half_life_hours <= 0 or evidence_saturation <= 0:
        raise ValueError("decay and saturation values must be positive")
    if behavior_coefficient < 0 or declared_coefficient < 0:
        raise ValueError("blend coefficients must be non-negative")

    reference_at = _parse_timestamp(payload.get("reference_at"))
    serving_at = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    age_hours = max(0.0, (serving_at - reference_at).total_seconds() / 3600.0)
    factor = exp2(-age_hours / half_life_hours)
    positive = {k: v * factor for k, v in _numeric_channel(payload.get("positive")).items()}
    negative = {k: v * factor for k, v in _numeric_channel(payload.get("negative")).items()}

    evidence = max(sum(positive.values()), sum(negative.values()))
    confidence = min(1.0, evidence / evidence_saturation)
    coefficient_total = behavior_coefficient + declared_coefficient
    if coefficient_total <= 0:
        return {}
    behavior_coefficient /= coefficient_total
    declared_coefficient /= coefficient_total

    positive_norm = _normalize(positive)
    negative_norm = _normalize(negative)
    declared = sorted({topic for topic in declared_topics if topic})
    declared_norm = {topic: 1.0 / len(declared) for topic in declared} if declared else {}
    merged: dict[str, float] = {}
    for topic, value in positive_norm.items():
        merged[topic] = merged.get(topic, 0.0) + behavior_coefficient * confidence * value
    for topic, value in negative_norm.items():
        merged[topic] = merged.get(topic, 0.0) - behavior_coefficient * confidence * value
    for topic, value in declared_norm.items():
        merged[topic] = merged.get(topic, 0.0) + declared_coefficient * value
    return {topic: round(value, 10) for topic, value in sorted(merged.items()) if value != 0}


def _merge_with_config(payload: dict[str, Any], declared: list[str], cfg: Any) -> dict[str, float]:
    return merge_preference_vector_v2(
        payload,
        declared,
        half_life_hours=cfg.preference_half_life_hours,
        behavior_coefficient=cfg.preference_behavior_coefficient,
        declared_coefficient=cfg.preference_declared_coefficient,
        evidence_saturation=cfg.preference_evidence_saturation,
    )


async def _fetch_declared_topics(db: DB, user_id: UUID) -> list[str]:
    row = await db.pool.fetchrow("SELECT topic_prefs FROM users WHERE id=$1", user_id)
    return list(row["topic_prefs"] or []) if row else []


def _decode_v1(raw: Any) -> dict[str, float] | None:
    if raw is None:
        return None
    import json as _json

    try:
        value = _json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(value, dict):
            return None
        return {str(key): float(weight) for key, weight in value.items()}
    except (TypeError, ValueError, _json.JSONDecodeError):
        return None


def _decode_v2_payload(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    import json as _json

    try:
        value = _json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(value, dict) or value.get("schema_version") != PREFERENCE_SCHEMA_V2:
            return None
        _numeric_channel(value.get("positive"))
        _numeric_channel(value.get("negative"))
        _parse_timestamp(value.get("reference_at"))
        return value
    except (TypeError, ValueError, _json.JSONDecodeError):
        return None


def _v2_row_payload(row: Any) -> dict[str, Any] | None:
    if not row or row["schema_version"] != PREFERENCE_SCHEMA_V2:
        return None
    return _decode_v2_payload(
        {
            "schema_version": row["schema_version"],
            "positive": row["positive_weights"],
            "negative": row["negative_weights"],
            "reference_at": row["reference_at"].isoformat(),
            "source_event_count": row["source_event_count"],
        }
    )


def _numeric_channel(value: Any) -> dict[str, float]:
    import json as _json

    if isinstance(value, str):
        value = _json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("preference channel must be an object")
    channel = {str(key): float(weight) for key, weight in value.items()}
    if any(weight < 0 or weight > 10 for weight in channel.values()):
        raise ValueError("preference channel value out of bounds")
    return channel


def _normalize(channel: dict[str, float]) -> dict[str, float]:
    total = sum(channel.values())
    return {key: value / total for key, value in channel.items()} if total > 0 else {}


def _parse_timestamp(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        value = raw
    elif isinstance(raw, str):
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    else:
        raise ValueError("reference_at is required")
    if value.tzinfo is None:
        raise ValueError("reference_at must include timezone")
    return value.astimezone(timezone.utc)


@asynccontextmanager
async def lifespan(db: DB, redis: RedisCli) -> AsyncIterator[None]:
    await db.start()
    await redis.start()
    try:
        yield
    finally:
        await redis.stop()
        await db.stop()
