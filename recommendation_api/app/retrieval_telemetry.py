"""Sample candidate pools separately from served impressions; never label them."""

from __future__ import annotations

import hashlib
from uuid import UUID
from prometheus_client import Counter

TELEMETRY_WRITES = Counter(
    "recommendation_candidate_telemetry_total",
    "Candidate telemetry batches",
    ["status"],
)


def sampled(request_id: UUID, rate: float) -> bool:
    if not 0 <= rate <= 1:
        raise ValueError("sample rate must be in [0, 1]")
    value = int.from_bytes(hashlib.sha256(request_id.bytes).digest()[:8], "big")
    return value / (1 << 64) < rate


async def record_pool(
    db, request_id: UUID, candidates, *, model_version: str, sample_rate: float
):
    if not candidates or not sampled(request_id, sample_rate):
        return
    await db.pool.executemany(
        """
        INSERT INTO recommendation_candidate_events
            (retrieval_request_id, post_id, stage, source, retrieval_score,
             eligibility_reason, model_version, retrieval_version)
        VALUES ($1, $2, 'eligible', $3, $4, 'passed_candidate_policy', $5, 'hybrid-candidates-v1')
        ON CONFLICT (retrieval_request_id, post_id, stage) DO NOTHING
        """,
        [
            (request_id, c.id, c.source, c.retrieval_score, model_version)
            for c in candidates
        ],
    )
    TELEMETRY_WRITES.labels(status="success").inc()
