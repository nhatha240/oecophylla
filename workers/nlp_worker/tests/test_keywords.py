from app.infer import infer_topics


def test_en_ai_and_tech():
    result = infer_topics("I love AI and coding")
    assert "ai" in result
    assert "tech" in result


def test_vi_music():
    result = infer_topics("Bài hát mới của ca sĩ X rất hay")
    assert "music" in result


def test_mixed_language():
    result = infer_topics("AI models and công nghệ phần mềm")
    assert "ai" in result
    assert "tech" in result


def test_empty_content_returns_general():
    result = infer_topics("")
    assert result == ["general"]


def test_unrelated_content_returns_general():
    result = infer_topics("hello world blah blah xyz")
    assert result == ["general"]
