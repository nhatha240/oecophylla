from __future__ import annotations

from collections import Counter
from uuid import UUID

from .db import DB, fetch_user_vector, RedisCli
from .features import gather_candidates
from .ranking import diversity_rerank, score_post
from .schemas import EvaluateResponse, RecommendationItem


async def evaluate(
    db: DB, redis: RedisCli, user_id: UUID, k: int
) -> EvaluateResponse:
    """MVP online evaluation: compute a fresh top-K for the user and report
    coarse quality signals against the user's positive topic vector. Uses the
    same retrieval+scoring path as the live endpoint so the numbers reflect what
    users would see.

    Relevance proxy: a candidate is "relevant" when any of its topics is one the
    user has a positive preference weight for. Precision@K is over the served
    top-K; Recall@K is over all relevant candidates in the retrieved pool.

    For a held-out, interaction-based offline evaluation (the canonical
    Precision/Recall/CTR/diversity numbers) see scripts/evaluate.py.
    """
    user_vec = await fetch_user_vector(db, redis, user_id)
    candidates = await gather_candidates(db, user_id, user_vec, pool_size=300)
    if not candidates:
        return EvaluateResponse(
            precision_at_k=0.0,
            recall_at_k=0.0,
            ctr_simulation=0.0,
            diversity=0.0,
            fallback_rate=1.0,
        )

    scored = [
        RecommendationItem(
            post_id=c.id,
            score=score_post(user_vec, c),
            source=c.source,
            reason="evaluate",
        )
        for c in candidates
    ]
    primary = {str(c.id): c.primary_topic for c in candidates}
    author = {str(c.id): str(c.author_id) for c in candidates}
    # Full topic set per post — used for the relevance test. (The previous
    # implementation intersected against set(primary_topic), which compared
    # topic names against individual characters and never matched.)
    post_topics = {str(c.id): set(t for t in c.topics if t) for c in candidates}
    top = diversity_rerank(scored, primary_topic=primary, author_id=author, limit=k)

    positive_topics = {t for t, w in user_vec.items() if w > 0}

    def is_relevant(post_id: str) -> bool:
        return bool(positive_topics & post_topics.get(post_id, set()))

    matched = sum(1 for it in top if is_relevant(str(it.post_id)))
    total_relevant = sum(1 for pid in post_topics if is_relevant(pid))

    precision_at_k = matched / max(1, len(top))
    recall_at_k = matched / max(1, total_relevant)

    max_score = max((it.score for it in top), default=1.0) or 1.0
    ctr = sum(it.score for it in top) / (max_score * max(1, len(top)))

    topic_counts = Counter(primary.get(str(it.post_id)) for it in top)
    diversity = len([t for t in topic_counts if t]) / max(1, len(top))

    return EvaluateResponse(
        precision_at_k=round(precision_at_k, 4),
        recall_at_k=round(recall_at_k, 4),
        ctr_simulation=round(ctr, 4),
        diversity=round(diversity, 4),
        fallback_rate=0.0,
    )
