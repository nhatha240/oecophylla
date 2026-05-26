from __future__ import annotations

from datetime import datetime, timezone
from math import exp
from typing import Iterable

from .schemas import CandidatePost, RecommendationItem


def freshness_decay(created_at: datetime, half_life_hours: float = 36.0) -> float:
    age_hours = max(
        0.0, (datetime.now(timezone.utc) - created_at).total_seconds() / 3600.0
    )
    return exp(-age_hours / half_life_hours)


def relevance(user_vec: dict[str, float], post_topics: Iterable[str]) -> float:
    topics = [t for t in post_topics if t]
    if not user_vec or not topics:
        return 0.0
    total = sum(abs(v) for v in user_vec.values()) or 1.0
    return sum(max(user_vec.get(t, 0.0), 0.0) for t in topics) / total


def score_post(
    user_vec: dict[str, float],
    post: CandidatePost,
    *,
    weights: tuple[float, float, float, float] = (0.5, 0.2, 0.1, 0.2),
    diversity_boost: float = 1.0,
    half_life_hours: float = 36.0,
) -> float:
    w1, w2, w3, w4 = weights
    return (
        w1 * relevance(user_vec, post.topics)
        + w2 * freshness_decay(post.created_at, half_life_hours)
        + w3 * float(post.safety_score)
        - w4 * (1.0 - diversity_boost)
    )


def diversity_rerank(
    items: list[RecommendationItem],
    *,
    primary_topic: dict[str, str | None],
    author_id: dict[str, str],
    limit: int,
) -> list[RecommendationItem]:
    """Greedy MMR-ish rerank: penalize same-author and same-topic streaks.
    `primary_topic` and `author_id` are keyed by str(post_id).
    """
    selected: list[RecommendationItem] = []
    remaining = sorted(items, key=lambda x: x.score, reverse=True)
    while remaining and len(selected) < limit:

        def adjusted(item: RecommendationItem) -> float:
            penalty = 0.0
            pid = str(item.post_id)
            if selected:
                last = selected[-1]
                if author_id.get(pid) == author_id.get(str(last.post_id)):
                    penalty += 0.08
                if primary_topic.get(pid) == primary_topic.get(str(last.post_id)):
                    penalty += 0.05
            seen_topics = {primary_topic.get(str(s.post_id)) for s in selected}
            if primary_topic.get(pid) in seen_topics and len(seen_topics) < 3:
                penalty += 0.04
            return item.score - penalty

        best = max(remaining, key=adjusted)
        remaining.remove(best)
        selected.append(best)
    return selected
