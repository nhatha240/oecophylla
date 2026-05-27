import unicodedata
from .keywords import TOPIC_KEYWORDS_EN, TOPIC_KEYWORDS_VI


def infer_topics(content: str) -> list[str]:
    """Return sorted list of matched topic keys. Falls back to ["general"] if no match."""
    normalized = unicodedata.normalize("NFKC", content).lower()
    matched = set()
    for topic, keywords in TOPIC_KEYWORDS_EN.items():
        if any(kw in normalized for kw in keywords):
            matched.add(topic)
    for topic, keywords in TOPIC_KEYWORDS_VI.items():
        if any(kw in normalized for kw in keywords):
            matched.add(topic)
    return sorted(matched) if matched else ["general"]
