#!/usr/bin/env python3
"""Seed mock data for local development.

Generates, per the project spec:
  - 500 users (mix of user / creator / admin)
  - 2000 posts across 10 topics, all `published`
  - 50,000 unique interactions (like / save / share / hide / report) with a
    realistic skew toward likes
  - 200 follows (social graph)
  - 50 reports (mix of pending / resolved)

Idempotency: the script aborts if the DB already holds seeded users (username
prefix ``seed_user_``) unless ``--force`` is passed. Re-running with ``--force``
adds another batch rather than wiping — use ``make clean`` to reset volumes.

Run:  docker compose run --rm scripts seed.py
      python scripts/seed.py            # with DATABASE_URL set
"""
from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys

import asyncpg
from argon2 import PasswordHasher

# Canonical topic slugs — keep in sync with workers/nlp_worker/app/topics.py
# and frontend/src/lib/topics.ts ("general" is the no-topic fallback, not seeded).
TOPICS = [
    "tech", "science", "sports", "politics", "entertainment",
    "health", "business", "culture", "education", "environment",
    "ai", "music", "news",
]

# Interaction signal weights (Bảng 2.2). `view`/`comment` are NOT interaction
# enum values in this schema — views live in posts.view_count, comments in the
# comments table — so they are intentionally excluded here.
INTERACTION_WEIGHTS = {
    "like": 1.5,
    "save": 2.5,
    "share": 2.5,
    "hide": -2.0,
    "report": -5.0,
}
# Realistic skew: most positive interactions are likes; negatives are rare.
INTERACTION_CHOICES = (
    ["like"] * 70 + ["save"] * 14 + ["share"] * 12 + ["hide"] * 3 + ["report"] * 1
)

REPORT_REASONS = ["spam", "harassment", "misinformation", "nudity", "violence", "other"]
REPORT_STATUSES = (
    ["pending"] * 20
    + ["resolved_ok"] * 12
    + ["resolved_hidden"] * 12
    + ["resolved_warned"] * 6
)

N_USERS = 500
N_POSTS = 2000
N_INTERACTIONS = 50_000
N_FOLLOWS = 200
N_REPORTS = 50

SEED_USERNAME_PREFIX = "seed_user_"


def role_for(index: int) -> str:
    if index < 5:
        return "admin"
    if index < 105:
        return "creator"
    return "user"


async def seed_users(conn: asyncpg.Connection, pw_hash: str) -> list:
    ids = []
    for i in range(N_USERS):
        prefs = random.sample(TOPICS, k=random.randint(0, 4))
        uid = await conn.fetchval(
            """
            INSERT INTO users (username, email, password_hash, role, display_name, topic_prefs)
            VALUES ($1, $2, $3, $4::user_role, $5, $6::text[])
            RETURNING id
            """,
            f"{SEED_USERNAME_PREFIX}{i:04d}",
            f"seed{i:04d}@example.test",
            pw_hash,
            role_for(i),
            f"Seed User {i:04d}",
            prefs,
        )
        ids.append(uid)
    return ids


async def seed_posts(conn: asyncpg.Connection, author_ids: list) -> list:
    ids = []
    for i in range(N_POSTS):
        topic = random.choice(TOPICS)
        extra = random.sample([t for t in TOPICS if t != topic], k=random.randint(0, 1))
        topics = [topic, *extra]
        uid = await conn.fetchval(
            """
            INSERT INTO posts (author_id, content, tags, topics, safety_score, status)
            VALUES ($1, $2, $3::text[], $4::text[], $5, 'published'::post_status)
            RETURNING id
            """,
            random.choice(author_ids),
            f"Seed post #{i} about {topic}. Lorem ipsum dolor sit amet, consectetur.",
            [topic],
            topics,
            round(random.uniform(0.6, 1.0), 3),
        )
        ids.append(uid)
    return ids


async def seed_interactions(conn: asyncpg.Connection, user_ids: list, post_ids: list) -> int:
    # Dedup client-side: the (user_id, post_id, type) unique index would abort a
    # COPY on the first collision, so we generate a unique set first.
    seen: set[tuple] = set()
    records = []
    attempts = 0
    max_attempts = N_INTERACTIONS * 3
    while len(records) < N_INTERACTIONS and attempts < max_attempts:
        attempts += 1
        u = random.choice(user_ids)
        p = random.choice(post_ids)
        t = random.choice(INTERACTION_CHOICES)
        key = (u, p, t)
        if key in seen:
            continue
        seen.add(key)
        records.append((u, p, t, INTERACTION_WEIGHTS[t]))
    await conn.copy_records_to_table(
        "interactions",
        records=records,
        columns=["user_id", "post_id", "type", "weight"],
    )
    return len(records)


async def seed_follows(conn: asyncpg.Connection, user_ids: list) -> int:
    seen: set[tuple] = set()
    inserted = 0
    attempts = 0
    while inserted < N_FOLLOWS and attempts < N_FOLLOWS * 10:
        attempts += 1
        a, b = random.sample(user_ids, 2)
        if (a, b) in seen:
            continue
        seen.add((a, b))
        status = await conn.execute(
            """
            INSERT INTO follows (follower_id, followee_id)
            VALUES ($1, $2) ON CONFLICT DO NOTHING
            """,
            a, b,
        )
        if status.endswith("1"):
            inserted += 1
    return inserted


async def seed_reports(conn: asyncpg.Connection, user_ids: list, post_ids: list) -> int:
    for _ in range(N_REPORTS):
        status = random.choice(REPORT_STATUSES)
        resolved_by = random.choice(user_ids[:5]) if status != "pending" else None
        await conn.execute(
            """
            INSERT INTO reports (reporter_id, post_id, reason, detail, status, resolved_by,
                                 resolved_at)
            VALUES ($1, $2, $3, $4, $5::report_status, $6,
                    CASE WHEN $5 = 'pending' THEN NULL ELSE now() END)
            """,
            random.choice(user_ids),
            random.choice(post_ids),
            random.choice(REPORT_REASONS),
            "Seeded report for local development.",
            status,
            resolved_by,
        )
    return N_REPORTS


async def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Oecophylla mock data")
    parser.add_argument("--force", action="store_true", help="seed even if seed data exists")
    parser.add_argument("--seed", type=int, default=42, help="PRNG seed for reproducibility")
    args = parser.parse_args()

    random.seed(args.seed)
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("ERROR: DATABASE_URL is not set", file=sys.stderr)
        return 1
    # asyncpg wants the postgres:// scheme without the sqlx +driver suffix.
    dsn = dsn.replace("postgresql+asyncpg://", "postgres://")

    conn = await asyncpg.connect(dsn)
    try:
        existing = await conn.fetchval(
            "SELECT count(*) FROM users WHERE username LIKE $1",
            f"{SEED_USERNAME_PREFIX}%",
        )
        if existing and not args.force:
            print(
                f"Found {existing} existing seed users — skipping. "
                "Use --force to add another batch, or `make clean` to reset.",
            )
            return 0

        print("Hashing seed password (argon2id)…")
        pw_hash = PasswordHasher().hash("Password123!")

        print(f"Seeding {N_USERS} users…")
        user_ids = await seed_users(conn, pw_hash)
        print(f"Seeding {N_POSTS} posts…")
        post_ids = await seed_posts(conn, user_ids)
        print(f"Seeding ~{N_INTERACTIONS} interactions…")
        n_inter = await seed_interactions(conn, user_ids, post_ids)
        print(f"Seeding {N_FOLLOWS} follows…")
        n_follows = await seed_follows(conn, user_ids)
        print(f"Seeding {N_REPORTS} reports…")
        n_reports = await seed_reports(conn, user_ids, post_ids)

        print(
            "Done: "
            f"{len(user_ids)} users, {len(post_ids)} posts, "
            f"{n_inter} interactions, {n_follows} follows, {n_reports} reports. "
            "All seed users share password 'Password123!'."
        )
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
