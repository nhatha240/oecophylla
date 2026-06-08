from app.features import apply_topic_delta


def test_apply_liked_splits_evenly_across_topics():
    out = apply_topic_delta({}, ["ai", "tech"], "liked")
    # 1.5 / 2 = 0.75
    assert out == {"ai": 0.75, "tech": 0.75}


def test_apply_reported_decrements():
    out = apply_topic_delta({"ai": 1.0}, ["ai"], "reported")
    assert out["ai"] == round(1.0 - 5.0, 4)


def test_unknown_event_no_op():
    base = {"ai": 0.5}
    assert apply_topic_delta(base, ["ai"], "unknown_event") == base


def test_apply_viewed_adds_small_signal():
    out = apply_topic_delta({}, ["ai", "tech"], "viewed")
    # 0.5 / 2 = 0.25
    assert out == {"ai": 0.25, "tech": 0.25}


def test_empty_topics_falls_back_to_general():
    out = apply_topic_delta({}, [], "liked")
    assert out == {"general": 1.5}


def test_does_not_mutate_input():
    base = {"ai": 0.5}
    apply_topic_delta(base, ["ai"], "liked")
    assert base == {"ai": 0.5}
