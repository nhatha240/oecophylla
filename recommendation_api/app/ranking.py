from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from math import exp

from .schemas import CandidatePost, RankFeatureSnapshot, RecommendationItem

RANK_FEATURE_SCHEMA_VERSION = "rank-features-v1"
HEURISTIC_MODEL_VERSION = "heuristic-v1"


def freshness_decay(created_at: datetime, half_life_hours: float = 36.0) -> float:
    age_hours = max(
        0.0, (datetime.now(timezone.utc) - created_at).total_seconds() / 3600.0
    )
    return exp(-age_hours / half_life_hours)


def relevance(user_vec: dict[str, float], post_topics: Iterable[str]) -> float:
    topics = [t for t in post_topics if t]
    if not user_vec or not topics:
        return 0.0
    positive_total = sum(max(value, 0.0) for value in user_vec.values())
    negative_total = sum(max(-value, 0.0) for value in user_vec.values())
    positive = (
        sum(max(user_vec.get(topic, 0.0), 0.0) for topic in topics) / positive_total
        if positive_total > 0
        else 0.0
    )
    negative = (
        sum(max(-user_vec.get(topic, 0.0), 0.0) for topic in topics) / negative_total
        if negative_total > 0
        else 0.0
    )
    return positive - negative


def build_rank_feature_snapshot(
    user_vec: dict[str, float],
    post: CandidatePost,
    *,
    weights: tuple[float, float, float, float] = (0.5, 0.2, 0.1, 0.2),
    diversity_boost: float = 1.0,
    half_life_hours: float = 36.0,
) -> RankFeatureSnapshot:
    """Compute the heuristic components once and preserve the exact inputs used."""
    topic_relevance = relevance(user_vec, post.topics)
    freshness = freshness_decay(post.created_at, half_life_hours)
    safety_score = float(post.safety_score)
    w1, w2, w3, w4 = weights
    heuristic_score = (
        w1 * topic_relevance
        + w2 * freshness
        + w3 * safety_score
        - w4 * (1.0 - diversity_boost)
    )
    return RankFeatureSnapshot(
        schema_version=RANK_FEATURE_SCHEMA_VERSION,
        topic_relevance=topic_relevance,
        freshness=freshness,
        safety_score=safety_score,
        candidate_source=post.source,
        is_followed_author=None,
        author_affinity=None,
        heuristic_score=heuristic_score,
        ml_score=None,
    )


def score_post(
    user_vec: dict[str, float],
    post: CandidatePost,
    *,
    weights: tuple[float, float, float, float] = (0.5, 0.2, 0.1, 0.2),
    diversity_boost: float = 1.0,
    half_life_hours: float = 36.0,
) -> float:
    snapshot = build_rank_feature_snapshot(
        user_vec,
        post,
        weights=weights,
        diversity_boost=diversity_boost,
        half_life_hours=half_life_hours,
    )
    assert snapshot.heuristic_score is not None
    return snapshot.heuristic_score


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
