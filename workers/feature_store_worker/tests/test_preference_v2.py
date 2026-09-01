from datetime import datetime, timedelta, timezone

import pytest
from app.features import (
    PREFERENCE_SCHEMA_V2,
    PreferenceEvent,
    blend_preference_channels,
    build_preference_vector_v2,
    decay_preference_vector,
)

NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


def _event(
    event_id: str,
    event_type: str,
    *,
    hours_ago: float = 0,
    topics: tuple[str, ...] = ("ai",),
    post_id: str = "post-1",
    impression_id: str | None = None,
    dwell_ms: int | None = None,
) -> PreferenceEvent:
    return PreferenceEvent(
        event_id=event_id,
        post_id=post_id,
        event_type=event_type,
        topics=topics,
        occurred_at=NOW - timedelta(hours=hours_ago),
        impression_id=impression_id,
        dwell_ms=dwell_ms,
    )


def test_replay_is_deterministic_for_ordered_out_of_order_and_duplicate_events():
    events = [
        _event("b", "like", hours_ago=24),
        _event("a", "click", hours_ago=48),
        _event("c", "hide", hours_ago=12, topics=("politics",), post_id="post-2"),
    ]

    ordered = build_preference_vector_v2(events, reference_at=NOW, half_life_hours=24)
    shuffled = build_preference_vector_v2(
        [events[2], events[0], events[1], events[0]],
        reference_at=NOW,
        half_life_hours=24,
    )

    assert ordered == shuffled
    assert ordered.schema_version == PREFERENCE_SCHEMA_V2
    assert ordered.source_event_count == 3


def test_undo_removes_active_positive_and_negative_state_instead_of_inverting_it():
    vector = build_preference_vector_v2(
        [
            _event("1", "like", hours_ago=4),
            _event("2", "unlike", hours_ago=3),
            _event("3", "hide", hours_ago=2),
            _event("4", "unhide", hours_ago=1),
        ],
        reference_at=NOW,
    )

    assert vector.positive == {}
    assert vector.negative == {}


def test_qualified_view_and_dwell_for_one_impression_apply_exactly_once():
    vector = build_preference_vector_v2(
        [
            _event("view", "view", impression_id="imp-1", dwell_ms=10_000),
            _event("dwell", "dwell", impression_id="imp-1", dwell_ms=20_000),
        ],
        reference_at=NOW,
        qualified_read_ms=10_000,
    )

    assert vector.positive == {"ai": pytest.approx(0.5)}
    assert vector.source_event_count == 1


def test_long_inactivity_decays_stale_behavior_without_delivery_time_mutation():
    original = build_preference_vector_v2(
        [_event("1", "save")], reference_at=NOW, half_life_hours=24
    )
    decayed = decay_preference_vector(
        original, at=NOW + timedelta(hours=240), half_life_hours=24
    )

    assert decayed.positive["ai"] == pytest.approx(original.positive["ai"] / 1024)
    assert decayed.reference_at == NOW + timedelta(hours=240)
    assert original.reference_at == NOW


def test_channels_are_explicit_and_bounded_under_spam_and_negative_feedback():
    events = [_event(f"click-{i}", "click") for i in range(100)] + [
        _event(f"report-{i}", "report", topics=("politics",), post_id=f"p-{i}")
        for i in range(100)
    ]
    vector = build_preference_vector_v2(events, reference_at=NOW, channel_bound=10.0)

    assert vector.positive == {"ai": 10.0}
    assert vector.negative == {"politics": 10.0}


def test_behavior_and_declared_topics_are_normalized_separately_then_blended():
    merged = blend_preference_channels(
        positive={"ai": 8.0},
        negative={"politics": 20.0},
        declared_topics=["sports", "science"],
        behavior_coefficient=0.75,
        declared_coefficient=0.25,
        behavior_confidence=1.0,
    )

    assert merged["ai"] == pytest.approx(0.75)
    assert merged["politics"] == pytest.approx(-0.75)
    assert merged["sports"] == pytest.approx(0.125)
    assert merged["science"] == pytest.approx(0.125)
