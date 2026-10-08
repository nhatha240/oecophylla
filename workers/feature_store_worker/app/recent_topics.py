"""Infer a small, ordered topic list from the user's recent article views."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import exp2
from typing import Iterable

from .features import PreferenceEvent

WINDOW_DAYS = 21
MAX_TOPICS = 5
HALF_LIFE_DAYS = 7


def ranked_view_topics(
    events: Iterable[PreferenceEvent], *, at: datetime | None = None
) -> list[str]:
    """Rank topics from distinct viewed posts in the last three weeks.

    One post contributes once even if view and dwell telemetry are both sent.
    Recency breaks ties without letting an old burst dominate newer reading.
    """
    now = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = now - timedelta(days=WINDOW_DAYS)
    latest_by_post: dict[str, PreferenceEvent] = {}
    for event in events:
        if event.event_type not in {"view", "dwell"}:
            continue
        occurred_at = event.occurred_at.astimezone(timezone.utc)
        if not cutoff <= occurred_at <= now:
            continue
        previous = latest_by_post.get(event.post_id)
        if previous is None or occurred_at > previous.occurred_at:
            latest_by_post[event.post_id] = event

    scores: dict[str, float] = {}
    for event in latest_by_post.values():
        topics = sorted({topic for topic in event.topics if topic and topic != "general"})
        if not topics:
            continue
        age_days = (now - event.occurred_at).total_seconds() / 86_400
        contribution = exp2(-age_days / HALF_LIFE_DAYS) / len(topics)
        for topic in topics:
            scores[topic] = scores.get(topic, 0.0) + contribution
    return sorted(scores, key=lambda topic: (-scores[topic], topic))[:MAX_TOPICS]
