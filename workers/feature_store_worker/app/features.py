from __future__ import annotations

WEIGHTS: dict[str, float] = {
    "liked": 1.5,
    "unliked": -1.5,
    "saved": 2.5,
    "unsaved": -2.5,
    "shared": 2.5,
    "unshared": -2.5,
    "hidden": -2.0,
    "reported": -5.0,
    "commented": 1.0,
    "comment_replied": 0.7,
}


def apply_topic_delta(
    vec: dict[str, float], topics: list[str], event_type: str
) -> dict[str, float]:
    """Pure: apply a single interaction's delta across topics. Splits the
    weight evenly across topics so a multi-topic post doesn't oversample."""
    if not topics:
        topics = ["general"]
    delta = WEIGHTS.get(event_type, 0.0) / len(topics)
    if delta == 0.0:
        return dict(vec)
    out = dict(vec)
    for topic in topics:
        out[topic] = round(out.get(topic, 0.0) + delta, 4)
    return out
