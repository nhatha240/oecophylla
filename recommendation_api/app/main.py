from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID

from fastapi import FastAPI, HTTPException
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from .db import DB, RedisCli, fetch_declared_topics, fetch_user_vector
from .evaluate import evaluate
from .features import (
    aggregate_topic_weights,
    all_user_ids_with_interactions,
    gather_candidates,
    upsert_user_vector,
    utc_now,
)
from .model_ranker import RankerRuntime
from .ranking import (
    HEURISTIC_MODEL_VERSION,
    build_rank_feature_snapshot,
    diversity_rerank,
)
from .schemas import (
    EvaluateResponse,
    RebuildRequest,
    RebuildResponse,
    RecommendationItem,
    RecommendFeedRequest,
    RecommendFeedResponse,
)
from .settings import settings as load_settings
from .serving_context import load_author_context, load_nrms_records


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = load_settings()
    db = DB(cfg.database_url)
    redis = RedisCli(cfg.redis_url)
    await db.start()
    await redis.start()
    app.state.db = db
    app.state.redis = redis
    app.state.cfg = cfg
    app.state.ranker = RankerRuntime.initialize(
        cfg.ranker_mode, cfg.model_artifact_path
    )
    try:
        yield
    finally:
        await redis.stop()
        await db.stop()


app = FastAPI(title="Oecophylla Recommendation API", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/recommend/feed/{user_id}", response_model=RecommendFeedResponse)
async def recommend_feed(
    user_id: UUID, body: RecommendFeedRequest
) -> RecommendFeedResponse:
    db: DB = app.state.db
    redis: RedisCli = app.state.redis
    cfg = app.state.cfg

    observed_at = utc_now()
    user_vec = await fetch_user_vector(db, redis, user_id, config=cfg)
    candidates = await gather_candidates(
        db,
        user_id,
        user_vec,
        pool_size=body.candidate_pool or cfg.feed_candidate_pool,
        seen_cooldown_days=cfg.seen_cooldown_days,
    )
    excluded = set(body.exclude_post_ids)
    candidates = [c for c in candidates if c.id not in excluded]
    if not candidates:
        return RecommendFeedResponse(
            items=[],
            model_version=HEURISTIC_MODEL_VERSION,
            generated_at=utc_now(),
        )

    declared_topics = await fetch_declared_topics(db, user_id)
    try:
        author_context = await asyncio.wait_for(
            load_author_context(
                db, user_id, list({c.author_id for c in candidates}), observed_at
            ),
            timeout=getattr(cfg, "model_timeout_ms", 150) / 1000,
        )
    except Exception as error:
        logging.getLogger(__name__).warning(
            "author_context_unavailable", extra={"error_type": type(error).__name__}
        )
        author_context = {}
    scored = []
    for candidate in candidates:
        features = build_rank_feature_snapshot(
            user_vec,
            candidate,
            half_life_hours=cfg.half_life_hours,
            declared_topics=declared_topics,
            observed_at=observed_at,
        )
        followed, affinity = author_context.get(candidate.author_id, (None, None))
        features = features.model_copy(
            update={"is_followed_author": followed, "author_affinity": affinity}
        )
        assert features.heuristic_score is not None
        scored.append(
            RecommendationItem(
                post_id=candidate.id,
                score=features.heuristic_score,
                source=candidate.source,
                reason=f"score={candidate.source}",
                features=features,
            )
        )
    runtime: RankerRuntime = getattr(
        app.state, "ranker", RankerRuntime(mode="heuristic")
    )
    budget = getattr(cfg, "model_timeout_ms", 150) / 1000
    started = time.monotonic()
    records = None
    context_failed = False
    if runtime.mode != "heuristic" and getattr(
        runtime.predictor, "requires_context", False
    ):
        try:
            records = await asyncio.wait_for(
                load_nrms_records(
                    db=db,
                    redis=redis,
                    user_id=user_id,
                    candidates=candidates,
                    observed_at=observed_at,
                    encoder_version=runtime.predictor.encoder_version,
                    dimension=runtime.predictor.dimension,
                    config=cfg,
                ),
                timeout=budget,
            )
        except Exception as error:
            logging.getLogger(__name__).warning(
                "nrms_context_unavailable", extra={"error_type": type(error).__name__}
            )
            context_failed = True
    decision = (
        runtime.fallback(scored, "context_error")
        if context_failed
        else await runtime.score_async(
            scored,
            records=records,
            timeout_seconds=max(0.001, budget - (time.monotonic() - started)),
        )
    )
    primary = {str(c.id): c.primary_topic for c in candidates}
    author = {str(c.id): str(c.author_id) for c in candidates}
    top = diversity_rerank(
        decision.items, primary_topic=primary, author_id=author, limit=body.limit
    )
    return RecommendFeedResponse(
        items=top,
        model_version=decision.model_version,
        generated_at=utc_now(),
    )


@app.post("/recommend/features/rebuild", response_model=RebuildResponse)
async def rebuild_features(body: RebuildRequest) -> RebuildResponse:
    db: DB = app.state.db
    redis: RedisCli = app.state.redis

    started = time.perf_counter()
    targets = (
        [body.user_id] if body.user_id else await all_user_ids_with_interactions(db)
    )
    if not targets:
        return RebuildResponse(users_processed=0, duration_ms=0)

    for uid in targets:
        weights = await aggregate_topic_weights(db, uid)
        await upsert_user_vector(db, uid, weights)
        await redis.cli.setex(f"pref:{uid}", 1800, json.dumps(weights))

    duration_ms = int((time.perf_counter() - started) * 1000)
    return RebuildResponse(users_processed=len(targets), duration_ms=duration_ms)


@app.post("/recommend/evaluate", response_model=EvaluateResponse)
async def evaluate_endpoint(
    user_id: UUID,
    k: int = 10,
    cutoff_at: datetime | None = None,
    label_window_hours: int = 24,
) -> EvaluateResponse:
    if k < 1 or k > 100:
        raise HTTPException(status_code=400, detail="k must be in [1,100]")
    if label_window_hours < 1 or label_window_hours > 720:
        raise HTTPException(
            status_code=400, detail="label_window_hours must be in [1,720]"
        )
    if cutoff_at is not None and cutoff_at.tzinfo is None:
        raise HTTPException(status_code=400, detail="cutoff_at must include a timezone")
    db: DB = app.state.db
    redis: RedisCli = app.state.redis
    cfg = app.state.cfg
    return await evaluate(
        db,
        redis,
        user_id,
        k,
        cutoff_at=cutoff_at,
        label_window_hours=label_window_hours,
        recommendation_label_version=cfg.recommendation_label_version,
        qualified_read_ms=cfg.qualified_read_ms,
    )
