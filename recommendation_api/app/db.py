from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from math import exp2
from typing import Any
from uuid import UUID

import asyncpg
import redis.asyncio as redis_async

from ai_pipeline.build_dataset import build_history_snapshot
from ai_pipeline.schemas import ArticleFeatureRecord, BehaviorEvent
from .settings import settings as load_settings
from .schemas import HistoryEntryPayload, UserHistorySnapshotPayload

PREFERENCE_SCHEMA_V2 = "preference-vector-v2"
HISTORY_SCHEMA_VERSION = "user-history-snapshot-v1"


class DB:
    """Lightweight pgpool wrapper. Created at startup, closed at shutdown."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

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
        self._cli: redis_async.Redis | None = None

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


async def fetch_user_history(
    db: DB,
    redis: RedisCli,
    user_id: UUID,
    *,
    at: datetime | None = None,
    config: Any | None = None,
) -> UserHistorySnapshotPayload:
    cfg = config or load_settings()
    reference_at = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cache_key = f"history:v2:{user_id}"

    if at is None:
        cached = await redis.cli.get(cache_key)
        payload = await _history_from_cache(
            db,
            user_id,
            reference_at,
            cached,
        )
        if payload is not None:
            return payload

    total_limit = max(
        1,
        int(cfg.history_recent_limit) + int(cfg.history_long_term_limit),
    )
    lookup_limit = total_limit + max(0, int(getattr(cfg, "history_lookup_slack", total_limit)))
    event_rows = await db.pool.fetch(
        """
        SELECT id, impression_id, user_id, post_id, event_type, dwell_ms,
               occurred_at, ingested_at, event_version, metadata
        FROM behavior_events
        WHERE user_id = $1
          AND event_type = 'click'
          AND occurred_at < $2
          AND ingested_at <= $2
          AND coalesce(event_version, metadata->>'event_version') = 'v2'
        ORDER BY occurred_at DESC, id DESC
        LIMIT $3
        """,
        user_id,
        reference_at,
        lookup_limit,
    )
    events = [BehaviorEvent.from_mapping(row) for row in event_rows]
    post_ids = sorted({event.post_id for event in events})
    feature_rows = (
        await db.pool.fetch(
            """
            SELECT id, post_id, encoder_version, content_hash, embedding,
                   source_updated_at, computed_at
            FROM post_content_features
            WHERE post_id = ANY($1::uuid[])
              AND source_updated_at <= $2
              AND computed_at <= $2
            ORDER BY post_id, source_updated_at DESC, computed_at DESC, id DESC
            """,
            post_ids,
            reference_at,
        )
        if post_ids
        else []
    )
    snapshot = build_history_snapshot(
        user_id,
        reference_at,
        events,
        [ArticleFeatureRecord.from_mapping(row) for row in feature_rows],
        cfg,
    )
    payload = UserHistorySnapshotPayload(
        schema_version=HISTORY_SCHEMA_VERSION,
        user_id=user_id,
        reference_at=reference_at,
        entries=[
            HistoryEntryPayload(
                event_id=entry.event_id,
                post_id=entry.post_id,
                event_type=entry.event_type,
                engaged_at=entry.engaged_at,
                encoder_version=entry.encoder_version,
                content_hash=entry.content_hash,
                feature_source_updated_at=entry.feature_source_updated_at,
                feature_computed_at=entry.feature_computed_at,
                embedding=list(entry.embedding),
            )
            for entry in snapshot.entries
        ],
    )
    if at is None:
        import json as _json

        await redis.cli.setex(
            cache_key,
            int(cfg.history_cache_ttl_seconds),
            _json.dumps(payload.to_cache_payload(), sort_keys=True),
        )
    return payload


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
    positive = {
        k: v * factor for k, v in _numeric_channel(payload.get("positive")).items()
    }
    negative = {
        k: v * factor for k, v in _numeric_channel(payload.get("negative")).items()
    }

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
    declared_norm = (
        {topic: 1.0 / len(declared) for topic in declared} if declared else {}
    )
    merged: dict[str, float] = {}
    for topic, value in positive_norm.items():
        merged[topic] = (
            merged.get(topic, 0.0) + behavior_coefficient * confidence * value
        )
    for topic, value in negative_norm.items():
        merged[topic] = (
            merged.get(topic, 0.0) - behavior_coefficient * confidence * value
        )
    for topic, value in declared_norm.items():
        merged[topic] = merged.get(topic, 0.0) + declared_coefficient * value
    return {
        topic: round(value, 10) for topic, value in sorted(merged.items()) if value != 0
    }


def _merge_with_config(
    payload: dict[str, Any], declared: list[str], cfg: Any
) -> dict[str, float]:
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
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != PREFERENCE_SCHEMA_V2
        ):
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
        raise TypeError("preference channel must be an object")
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
        raise TypeError("reference_at is required")
    if value.tzinfo is None:
        raise ValueError("reference_at must include timezone")
    return value.astimezone(timezone.utc)


async def _history_from_cache(
    db: DB,
    user_id: UUID,
    reference_at: datetime,
    raw: Any,
) -> UserHistorySnapshotPayload | None:
    if raw is None:
        return None
    import json as _json

    try:
        payload = _json.loads(raw) if isinstance(raw, str) else raw
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != HISTORY_SCHEMA_VERSION
        ):
            return None
        entries = payload.get("entries")
        if not isinstance(entries, list):
            return None
    except (TypeError, ValueError, _json.JSONDecodeError):
        return None

    try:
        post_ids = [UUID(str(entry["post_id"])) for entry in entries]
    except (KeyError, TypeError, ValueError):
        return None

    feature_rows = (
        await db.pool.fetch(
            """
            SELECT id, post_id, encoder_version, content_hash, embedding,
                   source_updated_at, computed_at
            FROM post_content_features
            WHERE post_id = ANY($1::uuid[])
            ORDER BY post_id, source_updated_at DESC, computed_at DESC, id DESC
            """,
            post_ids,
        )
        if entries
        else []
    )
    features = {
        (
            str(row["post_id"]),
            str(row["encoder_version"]),
            str(row["content_hash"]),
        ): ArticleFeatureRecord.from_mapping(row)
        for row in feature_rows
    }
    try:
        rebuilt_entries: list[HistoryEntryPayload] = []
        for entry in entries:
            key = (
                str(entry["post_id"]),
                str(entry["encoder_version"]),
                str(entry["content_hash"]),
            )
            feature = features.get(key)
            if feature is None:
                continue
            rebuilt_entries.append(
                HistoryEntryPayload(
                    post_id=UUID(str(entry["post_id"])),
                    event_id=UUID(str(entry["event_id"])),
                    event_type="click",
                    engaged_at=_parse_timestamp(entry["engaged_at"]),
                    encoder_version=str(entry["encoder_version"]),
                    content_hash=str(entry["content_hash"]),
                    feature_source_updated_at=_parse_timestamp(
                        entry["feature_source_updated_at"]
                    ),
                    feature_computed_at=_parse_timestamp(entry["feature_computed_at"]),
                    embedding=list(feature.embedding),
                )
            )
    except (KeyError, TypeError, ValueError):
        return None
    return UserHistorySnapshotPayload(
        schema_version=HISTORY_SCHEMA_VERSION,
        user_id=user_id,
        reference_at=reference_at,
        entries=rebuilt_entries,
    )


@asynccontextmanager
async def lifespan(db: DB, redis: RedisCli) -> AsyncIterator[None]:
    await db.start()
    await redis.start()
    try:
        yield
    finally:
        await redis.stop()
        await db.stop()
