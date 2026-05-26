from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.ranking import freshness_decay, relevance, score_post
from app.schemas import CandidatePost


def test_freshness_decay_now_is_one():
    assert freshness_decay(datetime.now(timezone.utc)) > 0.99


def test_freshness_decay_old_is_small():
    old = datetime.now(timezone.utc) - timedelta(hours=72)
    assert freshness_decay(old) < 0.5


def test_relevance_with_overlap():
    user_vec = {"ai": 1.0, "tech": 0.5}
    assert relevance(user_vec, ["ai", "other"]) > 0.0


def test_relevance_zero_when_no_overlap():
    user_vec = {"ai": 1.0}
    assert relevance(user_vec, ["sports"]) == 0.0


def test_score_post_combines_signals():
    post = CandidatePost(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        author_id=uuid4(),
        topics=["ai"],
        safety_score=1.0,
        created_at=datetime.now(timezone.utc),
        source="topic",
    )
    assert score_post({"ai": 1.0}, post) > 0.0
