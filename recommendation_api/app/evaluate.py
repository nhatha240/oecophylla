from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import fmean
from uuid import UUID

from recommendation_label import (
    QUALIFIED_READ_MS,
    LabelVersion,
    derive_label,
    event_label_version,
)

from .db import DB, RedisCli
from .metrics import (
    catalog_coverage,
    hit_rate_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    topic_diversity,
)
from .schemas import EvaluateResponse

@dataclass(frozen=True)
class ImpressionRecord:
    id: UUID
    request_id: UUID
    user_id: UUID
    post_id: UUID
    position: int
    feed_source: str
    topics: tuple[str, ...]
    served_at: datetime


@dataclass(frozen=True)
class BehaviorRecord:
    impression_id: UUID | None
    user_id: UUID
    post_id: UUID
    event_type: str
    occurred_at: datetime
    dwell_ms: int | None = None
    metadata: dict[str, object] | None = None
    event_id: UUID | None = None
    ingested_at: datetime | None = None
    event_version: LabelVersion | None = None


@dataclass(frozen=True)
class TemporalSplit:
    training_events: tuple[BehaviorRecord, ...]
    validation_impressions: tuple[ImpressionRecord, ...]
    label_events_by_impression: dict[UUID, tuple[BehaviorRecord, ...]]


def _aware_utc(value: datetime, name: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return value.astimezone(timezone.utc)


def build_temporal_split(
    impressions: list[ImpressionRecord],
    events: list[BehaviorRecord],
    *,
    cutoff_at: datetime,
    label_window_hours: int,
    as_of: datetime,
) -> TemporalSplit:
    """Create a leakage-safe split and finalize only elapsed label windows."""
    if label_window_hours <= 0:
        raise ValueError("label_window_hours must be positive")
    cutoff = _aware_utc(cutoff_at, "cutoff_at")
    evaluation_time = _aware_utc(as_of, "as_of")
    if cutoff >= evaluation_time:
        raise ValueError("cutoff_at must be before as_of")

    window = timedelta(hours=label_window_hours)
    finalized_before = evaluation_time - window
    training_events = tuple(
        event
        for event in events
        if _aware_utc(event.occurred_at, "event.occurred_at") < cutoff
        and (
            event.ingested_at is None
            or _aware_utc(event.ingested_at, "event.ingested_at") < cutoff
        )
    )
    validation_impressions = tuple(
        sorted(
            (
                impression
                for impression in impressions
                if cutoff
                <= _aware_utc(impression.served_at, "impression.served_at")
                <= finalized_before
            ),
            key=lambda impression: (
                impression.user_id,
                impression.request_id,
                impression.position,
            ),
        )
    )

    by_id = {impression.id: impression for impression in validation_impressions}
    labels: dict[UUID, list[BehaviorRecord]] = defaultdict(list)
    for event in events:
        if event.impression_id not in by_id:
            continue
        impression = by_id[event.impression_id]
        occurred_at = _aware_utc(event.occurred_at, "event.occurred_at")
        ingested_at = (
            _aware_utc(event.ingested_at, "event.ingested_at")
            if event.ingested_at is not None
            else occurred_at
        )
        served_at = _aware_utc(impression.served_at, "impression.served_at")
        if (
            event.user_id == impression.user_id
            and event.post_id == impression.post_id
            and served_at <= occurred_at <= served_at + window
            and occurred_at <= evaluation_time
            and ingested_at <= evaluation_time
        ):
            labels[impression.id].append(event)

    return TemporalSplit(
        training_events=training_events,
        validation_impressions=validation_impressions,
        label_events_by_impression={
            impression_id: tuple(label_events)
            for impression_id, label_events in labels.items()
        },
    )


def _rounded(value: float) -> float:
    return round(value, 4)


def evaluate_records(
    impressions: list[ImpressionRecord],
    events: list[BehaviorRecord],
    *,
    cutoff_at: datetime,
    label_window_hours: int,
    as_of: datetime,
    k: int,
    catalog_size: int,
    recommendation_label_version: LabelVersion = "v1",
    qualified_read_ms: int = QUALIFIED_READ_MS,
) -> EvaluateResponse:
    """Evaluate historical serving decisions against finalized observed labels."""
    if k <= 0:
        raise ValueError("k must be positive")
    split = build_temporal_split(
        impressions,
        events,
        cutoff_at=cutoff_at,
        label_window_hours=label_window_hours,
        as_of=as_of,
    )
    finalized = split.validation_impressions
    if not finalized:
        return EvaluateResponse(
            status="insufficient_data",
            sample_users=0,
            sample_impressions=0,
            cutoff_at=cutoff_at,
            label_window_hours=label_window_hours,
        )

    requests: dict[tuple[UUID, UUID], list[ImpressionRecord]] = defaultdict(list)
    for impression in finalized:
        requests[(impression.user_id, impression.request_id)].append(impression)

    precision_values: list[float] = []
    recall_values: list[float] = []
    ndcg_values: list[float] = []
    hit_rate_values: list[float] = []
    diversity_values: list[float] = []
    recommendation_lists: list[list[UUID]] = []

    for request_impressions in requests.values():
        ranked_impressions = sorted(
            request_impressions, key=lambda impression: impression.position
        )
        ranked_ids = [impression.post_id for impression in ranked_impressions]
        relevant_ids: set[UUID] = set()
        for impression in ranked_impressions:
            label_events = split.label_events_by_impression.get(impression.id, ())
            persisted_versions = {event_label_version(event) for event in label_events}
            if len(persisted_versions) > 1:
                raise ValueError("mixed persisted label versions within one impression")
            persisted_version: LabelVersion = (
                persisted_versions.pop()
                if persisted_versions
                else recommendation_label_version
            )
            label = derive_label(
                label_events,
                label_version=persisted_version,
                qualified_read_ms=qualified_read_ms,
                label_window_closed=True,
                v1_any_view_positive=persisted_version == "v1",
            )
            if label.training_target == 1:
                relevant_ids.add(impression.post_id)
        top_impressions = ranked_impressions[:k]
        recommendation_lists.append([item.post_id for item in top_impressions])
        precision_values.append(precision_at_k(ranked_ids, relevant_ids, k=k))
        recall_values.append(recall_at_k(ranked_ids, relevant_ids, k=k))
        ndcg_values.append(ndcg_at_k(ranked_ids, relevant_ids, k=k))
        hit_rate_values.append(hit_rate_at_k(ranked_ids, relevant_ids, k=k))
        diversity_values.append(
            topic_diversity([item.topics for item in top_impressions])
        )

    clicked_impressions = {
        impression.id
        for impression in finalized
        if any(
            event.event_type == "click"
            for event in split.label_events_by_impression.get(impression.id, ())
        )
    }
    fallback_impressions = sum(
        impression.feed_source == "fallback" for impression in finalized
    )
    observed_diversity = _rounded(fmean(diversity_values))

    return EvaluateResponse(
        status="ok",
        precision_at_k=_rounded(fmean(precision_values)),
        recall_at_k=_rounded(fmean(recall_values)),
        ndcg_at_k=_rounded(fmean(ndcg_values)),
        hit_rate=_rounded(fmean(hit_rate_values)),
        catalog_coverage=_rounded(
            catalog_coverage(recommendation_lists, catalog_size=catalog_size)
        ),
        topic_diversity=observed_diversity,
        ctr_observed=_rounded(len(clicked_impressions) / len(finalized)),
        fallback_rate=_rounded(fallback_impressions / len(finalized)),
        sample_users=len({impression.user_id for impression in finalized}),
        sample_impressions=len(finalized),
        cutoff_at=cutoff_at,
        label_window_hours=label_window_hours,
        ctr_simulation=None,
        diversity=observed_diversity,
    )


async def evaluate(
    db: DB,
    _redis: RedisCli,
    user_id: UUID,
    k: int,
    *,
    cutoff_at: datetime | None = None,
    label_window_hours: int = 24,
    as_of: datetime | None = None,
    recommendation_label_version: LabelVersion = "v1",
    qualified_read_ms: int = QUALIFIED_READ_MS,
) -> EvaluateResponse:
    """Evaluate persisted serving snapshots; never rebuild ranks with future state."""
    evaluation_time = as_of or datetime.now(timezone.utc)
    cutoff = cutoff_at or evaluation_time - timedelta(days=7)

    impression_rows = await db.pool.fetch(
        """
        SELECT
            ri.id,
            ri.request_id,
            ri.user_id,
            ri.post_id,
            ri.position,
            ri.feed_source,
            p.topics,
            ri.served_at
        FROM recommendation_impressions ri
        JOIN posts p ON p.id = ri.post_id
        WHERE ri.user_id = $1
          AND ri.served_at >= $2
          AND ri.served_at <= $3
        ORDER BY ri.request_id, ri.position
        """,
        user_id,
        cutoff,
        evaluation_time,
    )
    event_rows = await db.pool.fetch(
        """
        SELECT id, impression_id, user_id, post_id, event_type, dwell_ms,
               metadata, occurred_at, ingested_at
        FROM behavior_events
        WHERE user_id = $1
          AND occurred_at <= $2
          AND ingested_at <= $2
        ORDER BY occurred_at
        """,
        user_id,
        evaluation_time,
    )
    catalog_size = int(
        await db.pool.fetchval("SELECT count(*) FROM posts WHERE status = 'published'")
        or 0
    )

    impressions = [
        ImpressionRecord(
            id=row["id"],
            request_id=row["request_id"],
            user_id=row["user_id"],
            post_id=row["post_id"],
            position=int(row["position"]),
            feed_source=str(row["feed_source"]),
            topics=tuple(row["topics"] or ()),
            served_at=row["served_at"],
        )
        for row in impression_rows
    ]
    events = [
        BehaviorRecord(
            impression_id=row["impression_id"],
            user_id=row["user_id"],
            post_id=row["post_id"],
            event_type=str(row["event_type"]),
            occurred_at=row["occurred_at"],
            dwell_ms=(int(row["dwell_ms"]) if row["dwell_ms"] is not None else None),
            metadata=dict(row["metadata"] or {}),
            event_id=row["id"],
            ingested_at=row["ingested_at"],
            event_version=(
                str((row["metadata"] or {}).get("event_version", "v1"))
            ),
        )
        for row in event_rows
    ]
    return evaluate_records(
        impressions,
        events,
        cutoff_at=cutoff,
        label_window_hours=label_window_hours,
        as_of=evaluation_time,
        k=k,
        catalog_size=catalog_size,
        recommendation_label_version=recommendation_label_version,
        qualified_read_ms=qualified_read_ms,
    )
