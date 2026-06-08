from contextlib import asynccontextmanager

import asyncpg
import jwt
from fastapi import Depends, FastAPI, HTTPException, Request, status
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import os

DB_URL = os.environ.get("DATABASE_URL", "postgres://oecophylla:secret@postgres:5432/oecophylla")
JWT_SECRET = os.environ.get("JWT_SECRET", "")
ACCESS_COOKIE = "oec_access"
pool: asyncpg.Pool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=5)
    yield
    await pool.close()


app = FastAPI(title="analytics-service", lifespan=lifespan)


def require_admin(request: Request) -> dict:
    """Validate the oec_access HS256 JWT and require the admin role.

    Mirrors the Rust services' cookie auth (oec_access, HS256, role claim). The
    dashboard exposes platform-wide metrics, so it must never be world-readable.
    """
    if not JWT_SECRET:
        # Fail closed: a missing secret means we cannot authenticate anyone.
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="auth not configured")
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing token")
    try:
        claims = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")
    if claims.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    return claims


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/admin/dashboard")
async def dashboard(_admin: dict = Depends(require_admin)):
    async with pool.acquire() as conn:
        total_users = await conn.fetchval("SELECT count(*) FROM users")
        total_posts = await conn.fetchval("SELECT count(*) FROM posts")
        total_interactions = await conn.fetchval("SELECT count(*) FROM interactions")
        posts_24h = await conn.fetchval(
            "SELECT count(*) FROM posts WHERE created_at > now() - interval '24 hours'"
        )
        posts_7d = await conn.fetchval(
            "SELECT count(*) FROM posts WHERE created_at > now() - interval '7 days'"
        )
        active_users_24h = await conn.fetchval(
            "SELECT count(DISTINCT user_id) FROM interactions WHERE created_at > now() - interval '24 hours'"
        )
        pending_reports = await conn.fetchval(
            "SELECT count(*) FROM reports WHERE status = 'pending'"
        )
        # Recommender CTR over the last 24h: clicked impressions / total served.
        ctr_row = await conn.fetchrow(
            """
            SELECT count(*) AS served,
                   count(clicked_at) AS clicked
            FROM recommendations
            WHERE served_at > now() - interval '24 hours'
            """
        )
        served = ctr_row["served"] or 0
        clicked = ctr_row["clicked"] or 0
        recommender_ctr_24h = round(clicked / served, 4) if served else 0.0
        top_topics = await conn.fetch(
            """
            SELECT unnest(topics) AS topic, count(*) AS cnt
            FROM posts WHERE topics IS NOT NULL AND array_length(topics, 1) > 0
            GROUP BY topic ORDER BY cnt DESC LIMIT 5
            """
        )
    return {
        "total_users": total_users,
        "total_posts": total_posts,
        "total_interactions": total_interactions,
        "posts_last_24h": posts_24h,
        "posts_last_7d": posts_7d,
        "active_users_24h": active_users_24h,
        "pending_reports": pending_reports,
        "recommender_impressions_24h": served,
        "recommender_clicks_24h": clicked,
        "recommender_ctr_24h": recommender_ctr_24h,
        "top_topics": [{"topic": r["topic"], "count": r["cnt"]} for r in top_topics],
    }
