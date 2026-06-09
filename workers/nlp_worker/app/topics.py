"""Single source of truth for the topic vocabulary (analysis side).

Canonical slugs are the *preferred* labels — they drive the picker, display
labels, and recommendation topic vectors. Classification is **dynamic**: the
LLM may emit a topic outside this list, and `normalize_topic` keeps it (as a
clean slug) rather than dropping it. The canonical list + aliases only steer the
model toward consistent slugs and collapse common variants, to limit topic-space
fragmentation.

Keep the slugs here in sync with frontend/src/lib/topics.ts (same slug set).
"""
from __future__ import annotations

import re

# slug -> human label (English; the frontend owns localized labels).
CANONICAL_TOPICS: dict[str, str] = {
    "tech": "Technology",
    "science": "Science",
    "sports": "Sports",
    "politics": "Politics",
    "entertainment": "Entertainment",
    "health": "Health",
    "business": "Business",
    "culture": "Culture",
    "education": "Education",
    "environment": "Environment",
    "ai": "AI & Machine Learning",
    "music": "Music",
    "news": "News",
    "general": "General",
}

# Common variants → canonical slug. Collapses fragmentation from the keyword
# analyzer (singular "sport") and free-form LLM output.
ALIASES: dict[str, str] = {
    "sport": "sports",
    "technology": "tech",
    "tec": "tech",
    "artificial-intelligence": "ai",
    "machine-learning": "ai",
    "ml": "ai",
    "deep-learning": "ai",
    "entertain": "entertainment",
    "movies": "entertainment",
    "film": "entertainment",
    "edu": "education",
    "biz": "business",
    "economy": "business",
    "economics": "business",
    "politic": "politics",
    "healthcare": "health",
    "enviroment": "environment",  # common misspelling
}

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def normalize_topic(raw: str) -> str | None:
    """Lowercase + slugify + apply aliases. Returns None for empty/garbage so
    callers can drop it. Unknown-but-valid slugs are kept (dynamic vocabulary)."""
    if not raw:
        return None
    slug = _SLUG_RE.sub("-", raw.strip().lower()).strip("-")
    if not slug:
        return None
    return ALIASES.get(slug, slug)


def normalize_topics(raw: list[str], *, limit: int = 3) -> list[str]:
    """Normalize, dedupe (order-preserving), and cap a list of topics."""
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        slug = normalize_topic(item)
        if slug and slug not in seen:
            seen.add(slug)
            out.append(slug)
        if len(out) >= limit:
            break
    return out
