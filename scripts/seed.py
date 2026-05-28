"""Comprehensive seed data generator for Oecophylla."""

import argparse
import os
import random
import sys

from argon2 import PasswordHasher
import psycopg
from psycopg.rows import tuple_row

SHARED_HASH = PasswordHasher().hash("Password!123")  # computed once

TOPICS_POOL = [
    "tech",
    "science",
    "sports",
    "politics",
    "entertainment",
    "health",
    "business",
    "culture",
    "education",
    "environment",
]

INTERACTION_TYPES = [
    ("view", 0.5, 60),
    ("like", 1.5, 20),
    ("comment", 2.0, 8),
    ("share", 2.5, 4),
    ("save", 2.5, 4),
    ("hide", -2.0, 2),
    ("report", -5.0, 2),
]

COMMENT_TEXTS = [
    "Great post!",
    "Interesting perspective.",
    "I disagree with this.",
    "Thanks for sharing.",
    "Can you elaborate?",
    "This is really helpful.",
    "Well written.",
    "I learned something new.",
    "Not sure about this one.",
    "Spot on!",
]

REPORT_REASONS = ["spam", "harassment", "misinformation"]


def chunked(lst: list, size: int):
    """Yield successive chunks from a list."""
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def seed_users(cur, count: int) -> list:
    """Insert users and return their IDs."""
    roles = ["admin"] * 5 + ["creator"] * 45 + ["user"] * (count - 50)
    random.shuffle(roles)

    rows = []
    for i in range(count):
        username = f"seed_{i:03d}"
        email = f"{username}@oec.local"
        prefs = random.sample(TOPICS_POOL, k=random.randint(1, 4))
        rows.append((username, email, SHARED_HASH, roles[i], f"Seed User {i:03d}", prefs))

    user_ids = []
    for chunk in chunked(rows, 500):
        placeholders = ",".join(["(%s, %s, %s, %s, %s, %s)"] * len(chunk))
        flat = [v for row in chunk for v in row]
        cur.execute(
            f"""INSERT INTO users (username, email, password_hash, role, display_name, topic_prefs)
                VALUES {placeholders} RETURNING id""",
            flat,
        )
        user_ids.extend(r[0] for r in cur.fetchall())

    return user_ids


def seed_posts(cur, count: int, user_ids: list) -> list:
    """Insert posts and return their IDs."""
    rows = []
    for i in range(count):
        author = random.choice(user_ids)
        topics = random.sample(TOPICS_POOL, k=random.randint(1, 3))
        content = f"Seeded post #{i} about {topics[0]}"
        rows.append((author, content, topics, topics))

    post_ids = []
    for chunk in chunked(rows, 500):
        placeholders = ",".join(["(%s, %s, %s, %s, 'published')"] * len(chunk))
        flat = [v for row in chunk for v in row]
        cur.execute(
            f"""INSERT INTO posts (author_id, content, tags, topics, status)
                VALUES {placeholders} RETURNING id""",
            flat,
        )
        post_ids.extend(r[0] for r in cur.fetchall())

    return post_ids


def seed_follows(cur, user_ids: list, count: int = 200):
    """Insert follow edges, avoiding self-follows."""
    edges = set()
    while len(edges) < count:
        a, b = random.sample(user_ids, 2)
        edges.add((a, b))

    rows = list(edges)
    for chunk in chunked(rows, 500):
        placeholders = ",".join(["(%s, %s)"] * len(chunk))
        flat = [v for row in chunk for v in row]
        cur.execute(
            f"INSERT INTO follows (follower_id, followee_id) VALUES {placeholders} ON CONFLICT DO NOTHING",
            flat,
        )


def seed_interactions(cur, user_ids: list, post_ids: list, count: int):
    """Insert interactions with weighted type distribution."""
    types, weights, _ = zip(*INTERACTION_TYPES)

    rows = []
    for _ in range(count):
        user_id = random.choice(user_ids)
        post_id = random.choice(post_ids)
        itype = random.choices(types, weights=weights, k=1)[0]
        weight = next(w for t, w, _ in INTERACTION_TYPES if t == itype)
        metadata = None
        if itype == "comment":
            metadata = {"text": random.choice(COMMENT_TEXTS)}
        rows.append((user_id, post_id, itype, weight, psycopg.types.json.Json(metadata) if metadata else None))

    inserted = 0
    for chunk in chunked(rows, 500):
        placeholders = ",".join(["(%s, %s, %s, %s, %s)"] * len(chunk))
        flat = [v for row in chunk for v in row]
        cur.execute(
            f"""INSERT INTO interactions (user_id, post_id, type, weight, metadata)
                VALUES {placeholders} ON CONFLICT DO NOTHING""",
            flat,
        )
        inserted += cur.rowcount

    return inserted


def seed_reports(cur, user_ids: list, post_ids: list, count: int = 50):
    """Insert pending reports."""
    rows = []
    for _ in range(count):
        post_id = random.choice(post_ids)
        reporter_id = random.choice(user_ids)
        reason = random.choice(REPORT_REASONS)
        rows.append((reporter_id, post_id, reason, "pending"))

    for chunk in chunked(rows, 500):
        placeholders = ",".join(["(%s, %s, %s, %s)"] * len(chunk))
        flat = [v for row in chunk for v in row]
        cur.execute(
            f"""INSERT INTO reports (reporter_id, post_id, reason, status)
                VALUES {placeholders}""",
            flat,
        )


def main():
    parser = argparse.ArgumentParser(description="Seed Oecophylla with test data")
    parser.add_argument("--users", type=int, default=500, help="Number of users (default: 500)")
    parser.add_argument("--posts", type=int, default=2000, help="Number of posts (default: 2000)")
    parser.add_argument("--interactions", type=int, default=50000, help="Number of interactions (default: 50000)")
    args = parser.parse_args()

    random.seed(20260527)

    database_url = os.environ.get("DATABASE_URL", "postgres://oecophylla:secret@localhost:5432/oecophylla")

    with psycopg.connect(database_url, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM users")
            (n,) = cur.fetchone()
            if n > 0:
                print(f"users table not empty ({n} rows); aborting", file=sys.stderr)
                sys.exit(2)

            print(f"Seeding {args.users} users...")
            user_ids = seed_users(cur, args.users)

            print(f"Seeding {args.posts} posts...")
            post_ids = seed_posts(cur, args.posts, user_ids)

            print("Seeding 200 follows...")
            seed_follows(cur, user_ids)

            print(f"Seeding {args.interactions} interactions...")
            actual_interactions = seed_interactions(cur, user_ids, post_ids, args.interactions)

            print("Seeding 50 reports...")
            seed_reports(cur, user_ids, post_ids)

        conn.commit()

    print(f"Seeded: {args.users} users, {args.posts} posts, 200 follows, {actual_interactions} interactions, 50 reports")


if __name__ == "__main__":
    main()
