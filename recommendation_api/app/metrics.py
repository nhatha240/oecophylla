"""Pure recommendation metrics with no database or serving dependencies."""

from __future__ import annotations

from collections.abc import Collection, Hashable, Iterable, Sequence
from math import log2
from typing import TypeVar

Item = TypeVar("Item", bound=Hashable)


def _validate_k(k: int) -> None:
    if k <= 0:
        raise ValueError("k must be positive")


def precision_at_k(
    ranked_items: Sequence[Item], relevant_items: Collection[Item], *, k: int
) -> float:
    """Return relevant items in the first ``k`` positions divided by ``k``."""
    _validate_k(k)
    relevant = set(relevant_items)
    hits = sum(item in relevant for item in ranked_items[:k])
    return hits / k


def recall_at_k(
    ranked_items: Sequence[Item], relevant_items: Collection[Item], *, k: int
) -> float:
    """Return the fraction of all relevant items recovered in the first ``k``."""
    _validate_k(k)
    relevant = set(relevant_items)
    if not relevant:
        return 0.0
    hits = len(set(ranked_items[:k]) & relevant)
    return hits / len(relevant)


def ndcg_at_k(
    ranked_items: Sequence[Item], relevant_items: Collection[Item], *, k: int
) -> float:
    """Return binary normalized discounted cumulative gain at ``k``."""
    _validate_k(k)
    relevant = set(relevant_items)
    if not relevant:
        return 0.0
    dcg = sum(
        1.0 / log2(rank + 2)
        for rank, item in enumerate(ranked_items[:k])
        if item in relevant
    )
    ideal_hits = min(k, len(relevant))
    ideal_dcg = sum(1.0 / log2(rank + 2) for rank in range(ideal_hits))
    return dcg / ideal_dcg if ideal_dcg else 0.0


def hit_rate_at_k(
    ranked_items: Sequence[Item], relevant_items: Collection[Item], *, k: int
) -> float:
    """Return one when at least one relevant item appears in the first ``k``."""
    _validate_k(k)
    relevant = set(relevant_items)
    return float(any(item in relevant for item in ranked_items[:k]))


def reciprocal_rank(
    ranked_items: Sequence[Item], relevant_items: Collection[Item]
) -> float:
    """Return the reciprocal rank of the first relevant item, or zero."""
    relevant = set(relevant_items)
    for rank, item in enumerate(ranked_items, start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def impression_auc(
    scores: Sequence[float], binary_labels: Sequence[int]
) -> float | None:
    """Return pairwise AUC for one impression, excluding single-class groups."""
    if len(scores) != len(binary_labels):
        raise ValueError("scores and labels must have the same length")
    if any(label not in (0, 1) for label in binary_labels):
        raise ValueError("impression AUC labels must be binary")
    positives = [score for score, label in zip(scores, binary_labels) if label == 1]
    negatives = [score for score, label in zip(scores, binary_labels) if label == 0]
    if not positives or not negatives:
        return None
    pairwise_credit = sum(
        1.0 if positive > negative else (0.5 if positive == negative else 0.0)
        for positive in positives
        for negative in negatives
    )
    return pairwise_credit / (len(positives) * len(negatives))


def catalog_coverage(
    recommendation_lists: Iterable[Iterable[Item]], *, catalog_size: int
) -> float:
    """Return the unique recommended-item share of the eligible catalog."""
    if catalog_size <= 0:
        return 0.0
    recommended = {item for ranking in recommendation_lists for item in ranking}
    return min(1.0, len(recommended) / catalog_size)


def topic_diversity(item_topics: Sequence[Iterable[str]]) -> float:
    """Return unique non-empty topics per recommended item, capped at one."""
    if not item_topics:
        return 0.0
    topics = {
        topic for topics_for_item in item_topics for topic in topics_for_item if topic
    }
    return min(1.0, len(topics) / len(item_topics))


def topic_precision_at_k(
    ranked_topics: Sequence[Iterable[str]],
    positive_topics: Collection[str],
    *,
    k: int,
) -> float:
    """Compatibility topic proxy that compares whole topic names, never chars."""
    _validate_k(k)
    positive = {topic for topic in positive_topics if topic}
    matches = sum(
        bool(positive & {topic for topic in topics if topic})
        for topics in ranked_topics[:k]
    )
    return matches / k
