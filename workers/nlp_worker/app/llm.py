"""Optional LLM-backed content analysis via LM Studio (OpenAI-compatible API).

When enabled, this classifies a post into the project's fixed topic set and
assigns a safety score in [0,1]. Every failure path returns ``None`` so the
caller falls back to the deterministic keyword analyzer — the ingestion
pipeline must never block on, or be broken by, the LLM.
"""
from __future__ import annotations

import json
import logging

import httpx

from .settings import Settings
from .topics import CANONICAL_TOPICS, normalize_topics

logger = logging.getLogger("nlp_worker.llm")

# Canonical slugs are a *preference*, not a hard whitelist — classification is
# dynamic, so the model may introduce a new concise slug when nothing fits.
_PREFERRED = ", ".join(CANONICAL_TOPICS.keys())

SYSTEM_PROMPT = (
    "You are a content classifier for a Vietnamese/English social platform. "
    "Given a post, return STRICT JSON with two keys:\n"
    '  "topics": an array of 1-3 short lowercase topic slugs. PREFER these '
    f"existing slugs when they fit: {_PREFERRED}. If none fit, you MAY coin a "
    "new concise slug in lowercase-hyphenated English (e.g. \"space-travel\"). "
    'Use ["general"] only when the post has no clear topic.\n'
    '  "safety_score": a float in [0,1] where 1.0 is completely safe and 0.0 is '
    "severely unsafe (hate, violence, explicit, scams). "
    "Return ONLY the JSON object, no prose."
)


def _coerce(raw: dict) -> dict | None:
    """Validate and normalize the model's JSON into {topics, safety_score}.

    Topics are slugified + alias-collapsed (dynamic vocabulary) rather than
    whitelisted, so emergent topics survive while staying well-formed."""
    topics = raw.get("topics")
    if not isinstance(topics, list):
        return None
    clean = normalize_topics(topics, limit=3)
    if not clean:
        clean = ["general"]

    score = raw.get("safety_score", 1.0)
    try:
        score = float(score)
    except (TypeError, ValueError):
        score = 1.0
    score = max(0.0, min(1.0, score))

    return {"topics": clean, "safety_score": round(score, 3)}


async def analyze(cfg: Settings, content: str) -> dict | None:
    """Call LM Studio to classify `content`. Returns {topics, safety_score} or
    None on any error/timeout/malformed response."""
    if not content.strip():
        return None
    url = cfg.nlp_llm_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": cfg.nlp_llm_model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content[:4000]},
        ],
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {cfg.nlp_llm_api_key}"}
    try:
        async with httpx.AsyncClient(timeout=cfg.nlp_llm_timeout_seconds) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            body = resp.json()
        text = body["choices"][0]["message"]["content"]
        parsed = json.loads(text)
        result = _coerce(parsed)
        if result is None:
            logger.warning("LLM returned unusable JSON: %s", text[:200])
        return result
    except Exception as exc:  # noqa: BLE001 — any failure → keyword fallback
        logger.warning("LLM analysis failed (%s); falling back to keywords", exc)
        return None
