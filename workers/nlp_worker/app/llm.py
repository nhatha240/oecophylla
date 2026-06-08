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

from .keywords import TOPIC_KEYWORDS_EN, TOPIC_KEYWORDS_VI
from .settings import Settings

logger = logging.getLogger("nlp_worker.llm")

# Constrain the model to the same topic vocabulary the keyword analyzer uses,
# so downstream ranking/feed code sees a consistent label space.
ALLOWED_TOPICS = sorted(set(TOPIC_KEYWORDS_EN) | set(TOPIC_KEYWORDS_VI))

SYSTEM_PROMPT = (
    "You are a content classifier for a Vietnamese/English social platform. "
    "Given a post, return STRICT JSON with two keys:\n"
    '  "topics": an array of 1-3 labels chosen ONLY from this list: '
    f"{ALLOWED_TOPICS}. Use [\"general\"] if none fit.\n"
    '  "safety_score": a float in [0,1] where 1.0 is completely safe and 0.0 is '
    "severely unsafe (hate, violence, explicit, scams). "
    "Return ONLY the JSON object, no prose."
)


def _coerce(raw: dict) -> dict | None:
    """Validate and normalize the model's JSON into {topics, safety_score}."""
    topics = raw.get("topics")
    if not isinstance(topics, list):
        return None
    allowed = set(ALLOWED_TOPICS) | {"general"}
    clean = [t for t in topics if isinstance(t, str) and t in allowed]
    if not clean:
        clean = ["general"]

    score = raw.get("safety_score", 1.0)
    try:
        score = float(score)
    except (TypeError, ValueError):
        score = 1.0
    score = max(0.0, min(1.0, score))

    # Dedup while preserving order, cap at 3.
    seen: set[str] = set()
    topics_out = [t for t in clean if not (t in seen or seen.add(t))][:3]
    return {"topics": topics_out, "safety_score": round(score, 3)}


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
