import unicodedata
from .keywords import TOPIC_KEYWORDS_EN, TOPIC_KEYWORDS_VI
from .topics import normalize_topic


def infer_topics(content: str) -> list[str]:
    """Return sorted list of matched topic slugs, normalized to the canonical
    vocabulary (e.g. keyword key "sport" → "sports"). Falls back to ["general"]."""
    normalized = unicodedata.normalize("NFKC", content).lower()
    matched = set()
    for topic, keywords in TOPIC_KEYWORDS_EN.items():
        if any(kw in normalized for kw in keywords):
            matched.add(topic)
    for topic, keywords in TOPIC_KEYWORDS_VI.items():
        if any(kw in normalized for kw in keywords):
            matched.add(topic)
    if not matched:
        return ["general"]
    return sorted({normalize_topic(t) or t for t in matched})
