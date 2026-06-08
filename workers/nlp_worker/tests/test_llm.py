from app.llm import _coerce, ALLOWED_TOPICS


def test_coerce_filters_unknown_topics_and_caps_at_three():
    out = _coerce({"topics": ["ai", "tech", "science", "bogus"], "safety_score": 0.9})
    assert out is not None
    assert all(t in set(ALLOWED_TOPICS) | {"general"} for t in out["topics"])
    assert "bogus" not in out["topics"]
    assert len(out["topics"]) <= 3
    assert out["safety_score"] == 0.9


def test_coerce_defaults_to_general_when_no_valid_topic():
    out = _coerce({"topics": ["nope"], "safety_score": 0.5})
    assert out == {"topics": ["general"], "safety_score": 0.5}


def test_coerce_clamps_and_defaults_score():
    assert _coerce({"topics": ["health"], "safety_score": 5})["safety_score"] == 1.0
    assert _coerce({"topics": ["health"], "safety_score": -2})["safety_score"] == 0.0
    assert _coerce({"topics": ["health"], "safety_score": "bad"})["safety_score"] == 1.0


def test_coerce_rejects_non_list_topics():
    assert _coerce({"topics": "ai"}) is None
