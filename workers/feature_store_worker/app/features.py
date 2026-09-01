from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from math import exp2

PREFERENCE_SCHEMA_V2 = "preference-vector-v2"
DEFAULT_PREFERENCE_HALF_LIFE_HOURS = 24.0 * 30.0
DEFAULT_CHANNEL_BOUND = 10.0


@dataclass(frozen=True)
class PreferenceEvent:
    event_id: str
    post_id: str
    event_type: str
    topics: tuple[str, ...]
    occurred_at: datetime
    impression_id: str | None = None
    dwell_ms: int | None = None


@dataclass(frozen=True)
class PreferenceVectorV2:
    positive: dict[str, float]
    negative: dict[str, float]
    reference_at: datetime
    source_event_count: int
    schema_version: str = PREFERENCE_SCHEMA_V2

    def as_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "positive": self.positive,
            "negative": self.negative,
            "reference_at": self.reference_at.isoformat(),
            "source_event_count": self.source_event_count,
        }


WEIGHTS: dict[str, float] = {
    "viewed": 0.5,
    "qualified_read": 0.5,
    "liked": 1.5,
    "unliked": -1.5,
    "saved": 2.5,
    "unsaved": -2.5,
    "shared": 2.5,
    "unshared": -2.5,
    "hidden": -2.0,
    "reported": -5.0,
    "commented": 1.0,
    "comment_replied": 0.7,
}

# Canonical behavior_events semantics. Reversal events remove active state;
# they never become negative feedback of their own.
CANONICAL_WEIGHTS: dict[str, float] = {
    "click": 1.0,
    "qualified_read": 0.5,
    "like": 1.5,
    "save": 2.5,
    "share": 2.5,
    "hide": -2.0,
    "report": -5.0,
    "comment": 1.0,
}
REVERSALS = {"unlike": "like", "unsave": "save", "unshare": "share", "unhide": "hide"}
STATEFUL_EVENTS = frozenset({"like", "save", "share", "hide"})


def apply_topic_delta(
    vec: dict[str, float], topics: list[str], event_type: str
) -> dict[str, float]:
    """Pure: apply a single interaction's delta across topics. Splits the
    weight evenly across topics so a multi-topic post doesn't oversample."""
    if not topics:
        topics = ["general"]
    delta = WEIGHTS.get(event_type, 0.0) / len(topics)
    if delta == 0.0:
        return dict(vec)
    out = dict(vec)
    for topic in topics:
        out[topic] = round(out.get(topic, 0.0) + delta, 4)
    return out


def build_preference_vector_v2(
    events: Iterable[PreferenceEvent],
    *,
    reference_at: datetime | None = None,
    half_life_hours: float = DEFAULT_PREFERENCE_HALF_LIFE_HOURS,
    channel_bound: float = DEFAULT_CHANNEL_BOUND,
    qualified_read_ms: int = 10_000,
) -> PreferenceVectorV2:
    """Replay canonical events into bounded, event-time-decayed channels.

    Sorting and replaying the immutable event set makes the result independent
    of Kafka delivery order. Only events at or before ``reference_at`` are
    eligible, preventing a rebuild from introducing future state.
    """
    if half_life_hours <= 0 or channel_bound <= 0:
        raise ValueError("half_life_hours and channel_bound must be positive")

    materialized = list(events)
    if reference_at is None:
        reference_at = max(
            (event.occurred_at for event in materialized),
            default=datetime.now(timezone.utc),
        )
    reference_at = _aware_utc(reference_at)

    # Stable sort also gives deterministic behavior for an invalid conflicting
    # duplicate ID. The canonical table rejects such conflicts, but rebuilds
    # remain deterministic when fed synthetic/audit data.
    ordered = sorted(
        materialized,
        key=lambda event: (
            _aware_utc(event.occurred_at),
            event.event_id,
            event.post_id,
            event.event_type,
            event.topics,
        ),
    )
    unique: list[PreferenceEvent] = []
    seen_ids: set[str] = set()
    for event in ordered:
        if event.event_id in seen_ids or _aware_utc(event.occurred_at) > reference_at:
            continue
        seen_ids.add(event.event_id)
        unique.append(event)

    active: dict[tuple[str, str], PreferenceEvent] = {}
    additive: list[tuple[PreferenceEvent, str]] = []
    seen_reads: set[str] = set()
    for event in unique:
        event_type = event.event_type
        if event_type in ("view", "dwell"):
            if event.dwell_ms is None or event.dwell_ms < qualified_read_ms:
                continue
            read_identity = event.impression_id or event.event_id
            if read_identity in seen_reads:
                continue
            seen_reads.add(read_identity)
            additive.append((event, "qualified_read"))
            continue
        if event_type in STATEFUL_EVENTS:
            active[(event.post_id, event_type)] = event
            continue
        reversed_type = REVERSALS.get(event_type)
        if reversed_type is not None:
            active.pop((event.post_id, reversed_type), None)
            continue
        if event_type in CANONICAL_WEIGHTS:
            additive.append((event, event_type))

    contributions = additive + [
        (event, event_type) for (_, event_type), event in active.items()
    ]
    positive: dict[str, float] = {}
    negative: dict[str, float] = {}
    for event, event_type in contributions:
        weight = CANONICAL_WEIGHTS[event_type]
        age_hours = max(
            0.0,
            (reference_at - _aware_utc(event.occurred_at)).total_seconds() / 3600.0,
        )
        decayed = weight * exp2(-age_hours / half_life_hours)
        topics = tuple(topic for topic in event.topics if topic) or ("general",)
        channel = positive if decayed > 0 else negative
        share = abs(decayed) / len(topics)
        for topic in topics:
            channel[topic] = min(channel_bound, channel.get(topic, 0.0) + share)

    return PreferenceVectorV2(
        positive=_rounded_channel(positive),
        negative=_rounded_channel(negative),
        reference_at=reference_at,
        source_event_count=len(contributions),
    )


def decay_preference_vector(
    vector: PreferenceVectorV2,
    *,
    at: datetime,
    half_life_hours: float = DEFAULT_PREFERENCE_HALF_LIFE_HOURS,
) -> PreferenceVectorV2:
    """Project a stored vector forward without mutating its original clock."""
    if half_life_hours <= 0:
        raise ValueError("half_life_hours must be positive")
    at = _aware_utc(at)
    reference_at = _aware_utc(vector.reference_at)
    factor = exp2(
        -max(0.0, (at - reference_at).total_seconds() / 3600.0) / half_life_hours
    )
    return PreferenceVectorV2(
        positive=_rounded_channel({k: v * factor for k, v in vector.positive.items()}),
        negative=_rounded_channel({k: v * factor for k, v in vector.negative.items()}),
        reference_at=max(at, reference_at),
        source_event_count=vector.source_event_count,
    )


def blend_preference_channels(
    *,
    positive: dict[str, float],
    negative: dict[str, float],
    declared_topics: Iterable[str],
    behavior_coefficient: float,
    declared_coefficient: float,
    behavior_confidence: float = 1.0,
) -> dict[str, float]:
    """Normalize behavior channels and declared interests independently."""
    if behavior_coefficient < 0 or declared_coefficient < 0:
        raise ValueError("blend coefficients must be non-negative")
    coefficient_total = behavior_coefficient + declared_coefficient
    if coefficient_total <= 0:
        return {}
    behavior_coefficient /= coefficient_total
    declared_coefficient /= coefficient_total
    confidence = min(1.0, max(0.0, behavior_confidence))

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
    return _rounded_channel(merged, retain_negative=True)


def _normalize(channel: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, value) for value in channel.values())
    if total <= 0:
        return {}
    return {
        topic: max(0.0, value) / total for topic, value in channel.items() if value > 0
    }


def _rounded_channel(
    channel: dict[str, float], *, retain_negative: bool = False
) -> dict[str, float]:
    result: dict[str, float] = {}
    for topic, value in sorted(channel.items()):
        rounded = round(float(value), 10)
        if abs(rounded) > 1e-12 and (retain_negative or rounded > 0):
            result[topic] = rounded
    return result


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("event timestamps must include a timezone")
    return value.astimezone(timezone.utc)
