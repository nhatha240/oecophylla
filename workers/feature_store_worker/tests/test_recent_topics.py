from datetime import datetime, timedelta, timezone

from app.features import PreferenceEvent
from app.recent_topics import ranked_view_topics


NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)


def _event(post_id: str, topics: tuple[str, ...], days_ago: float, event_type="view"):
    return PreferenceEvent(
        event_id=f"{post_id}-{event_type}",
        post_id=post_id,
        impression_id=None,
        session_id=None,
        visit_id=None,
        event_type=event_type,
        dwell_ms=None,
        read_trigger=None,
        occurred_at=NOW - timedelta(days=days_ago),
        topics=topics,
    )


def test_recent_views_rank_topics_and_deduplicate_post_read_events():
    events = [
        _event("a", ("ai",), 1),
        _event("a", ("ai",), 1, "dwell"),
        _event("b", ("science",), 2),
        _event("c", ("ai",), 3),
        _event("d", ("old",), 22),
        _event("e", ("general",), 0),
        _event("f", ("future",), -1),
    ]

    assert ranked_view_topics(events, at=NOW) == ["ai", "science"]


def test_views_expire_after_three_weeks():
    assert ranked_view_topics([_event("a", ("ai",), 20)], at=NOW) == ["ai"]
    assert ranked_view_topics([_event("a", ("ai",), 20)], at=NOW + timedelta(days=2)) == []
