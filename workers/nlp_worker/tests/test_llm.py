from app.llm import _coerce
from app.topics import normalize_topic, normalize_topics


def test_coerce_keeps_canonical_and_aliases_collapse():
    out = _coerce({"topics": ["ai", "Sport", "Machine Learning"], "safety_score": 0.9})
    assert out is not None
    # "Sport" -> "sports", "Machine Learning" -> ml alias -> "ai" (dedup keeps one)
    assert out["topics"] == ["ai", "sports"]
    assert out["safety_score"] == 0.9


def test_coerce_keeps_dynamic_unknown_topic_as_slug():
    # Dynamic vocabulary: an unseen topic is kept (slugified), not dropped.
    out = _coerce({"topics": ["Space Travel"], "safety_score": 0.5})
    assert out == {"topics": ["space-travel"], "safety_score": 0.5}


def test_coerce_caps_at_three_and_dedupes():
    out = _coerce({"topics": ["tech", "tech", "ai", "health", "music"], "safety_score": 1})
    assert out["topics"] == ["tech", "ai", "health"]


def test_coerce_defaults_to_general_when_empty():
    assert _coerce({"topics": [], "safety_score": 1})["topics"] == ["general"]
    assert _coerce({"topics": ["   ", "!!!"], "safety_score": 1})["topics"] == ["general"]


def test_coerce_clamps_and_defaults_score():
    assert _coerce({"topics": ["health"], "safety_score": 5})["safety_score"] == 1.0
    assert _coerce({"topics": ["health"], "safety_score": -2})["safety_score"] == 0.0
    assert _coerce({"topics": ["health"], "safety_score": "bad"})["safety_score"] == 1.0


def test_coerce_rejects_non_list_topics():
    assert _coerce({"topics": "ai"}) is None


def test_normalize_topic_slugifies_and_aliases():
    assert normalize_topic("Sport") == "sports"
    assert normalize_topic("  AI  ") == "ai"
    assert normalize_topic("machine learning") == "ai"
    assert normalize_topic("Space Travel") == "space-travel"
    assert normalize_topic("!!!") is None
    assert normalize_topics(["tech", "tech", "Sport"]) == ["tech", "sports"]
