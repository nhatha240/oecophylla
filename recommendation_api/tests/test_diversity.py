from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.ranking import diversity_rerank
from app.schemas import RankFeatureSnapshot, RecommendationItem


def _item(score: float, post_id: UUID) -> RecommendationItem:
    return RecommendationItem(
        post_id=post_id,
        score=score,
        source="topic",
        reason="t",
        features=RankFeatureSnapshot(
            schema_version="rank-features-v1",
            topic_relevance=None,
            freshness=None,
            safety_score=None,
            candidate_source="topic",
            is_followed_author=None,
            author_affinity=None,
            heuristic_score=score,
            ml_score=None,
        ),
    )


def test_diversity_rerank_spreads_topics():
    same_topic_ids = [uuid4() for _ in range(10)]
    other_topic_ids = [uuid4() for _ in range(3)]
    items = (
        [_item(1.0 - i * 0.01, pid) for i, pid in enumerate(same_topic_ids)]
        + [_item(0.95, pid) for pid in other_topic_ids]
    )
    primary = {str(pid): "ai" for pid in same_topic_ids}
    primary.update({str(pid): "sports" for pid in other_topic_ids})
    author = {str(pid): str(uuid4()) for pid in same_topic_ids + other_topic_ids}

    top5 = diversity_rerank(items, primary_topic=primary, author_id=author, limit=5)
    topics = {primary[str(it.post_id)] for it in top5}
    assert len(topics) >= 2, f"expected >=2 topics in top-5, got {topics}"
