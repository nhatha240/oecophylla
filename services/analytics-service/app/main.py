from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import os

DB_URL = os.environ.get("DATABASE_URL", "postgres://oecophylla:secret@postgres:5432/oecophylla")
pool: asyncpg.Pool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(DB_URL, min_size=2, max_size=5)
    yield
    await pool.close()


app = FastAPI(title="analytics-service", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/admin/dashboard")
async def dashboard():
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
        "top_topics": [{"topic": r["topic"], "count": r["cnt"]} for r in top_topics],
    }
