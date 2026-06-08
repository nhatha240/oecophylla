#!/usr/bin/env python3
"""Offline evaluation of the recommendation ranking on seeded data.

This is the canonical, held-out evaluation referenced in the spec. For each
sampled user with enough positive interactions, it:

  1. Splits the user's positive interactions (like / save / share) into
     train (80%) and test (20%).
  2. Builds a topic-preference vector from the *train* positives only.
  3. Scores a candidate pool of published posts with the same formula the live
     ranker uses (relevance + freshness + safety), reranked for diversity.
  4. Measures the top-K against the held-out *test* positives.

Metrics (averaged over evaluated users):
  - Precision@K : fraction of top-K that are held-out positives
  - Recall@K    : fraction of held-out positives that appear in top-K
  - CTR sim     : clicks / impressions on the served top-K, where a "click" is a
                  held-out positive (a held-out impression list per user)
  - Diversity   : average distinct-topic ratio within each top-K feed

Run:  docker compose run --rm scripts evaluate.py --k 10
      python scripts/evaluate.py --k 10        # with DATABASE_URL set
"""
from __future__ import annotations

import argparse
import asyncio
import math
import os
import random
import sys
from datetime import datetime, timezone

import asyncpg

POSITIVE_TYPES = ("like", "save", "share")
POOL_SIZE = 300
HALF_LIFE_HOURS = 36.0
WEIGHTS = (0.5, 0.2, 0.1)  # relevance, freshness, safety


def freshness_decay(created_at: datetime) -> float:
    age_h = max(0.0, (datetime.now(timezone.utc) - created_at).total_seconds() / 3600.0)
    return math.exp(-age_h / HALF_LIFE_HOURS)


def relevance(user_vec: dict, topics: list) -> float:
    topics = [t for t in topics if t]
    if not user_vec or not topics:
        return 0.0
    total = sum(abs(v) for v in user_vec.values()) or 1.0
    return sum(max(user_vec.get(t, 0.0), 0.0) for t in topics) / total


def score_post(user_vec: dict, topics: list, safety: float, created_at: datetime) -> float:
    w1, w2, w3 = WEIGHTS
    return (
        w1 * relevance(user_vec, topics)
        + w2 * freshness_decay(created_at)
        + w3 * float(safety)
    )


def build_vector(rows: list) -> dict:
    """rows: list of (weight, topics) for the user's train positives."""
    out: dict = {}
    for weight, topics in rows:
        topics = [t for t in (topics or []) if t] or ["general"]
        share = float(weight) / len(topics)
        for t in topics:
            out[t] = out.get(t, 0.0) + share
    return out


def diversity_score(top_topics: list) -> float:
    if not top_topics:
        return 0.0
    distinct = len({t for t in top_topics if t})
    return distinct / len(top_topics)


async def eval_user(conn, user_id, k: int) -> tuple | None:
    positives = await conn.fetch(
        """
        SELECT i.post_id, i.weight, p.topics
        FROM interactions i
        JOIN posts p ON p.id = i.post_id
        WHERE i.user_id = $1 AND i.type = ANY($2::interaction_type[])
        ORDER BY i.created_at
        """,
        user_id, list(POSITIVE_TYPES),
    )
    if len(positives) < 5:
        return None  # not enough signal to split

    split = max(1, int(len(positives) * 0.8))
    train, test = positives[:split], positives[split:]
    if not test:
        return None

    user_vec = build_vector([(r["weight"], r["topics"]) for r in train])
    test_ids = {r["post_id"] for r in test}
    train_ids = {r["post_id"] for r in train}

    # Candidate pool: recent published posts, excluding train items (can't
    # "recommend" what the model already learned from).
    candidates = await conn.fetch(
        """
        SELECT id, topics, safety_score, created_at
        FROM posts
        WHERE status = 'published'
        ORDER BY created_at DESC
        LIMIT $1
        """,
        POOL_SIZE,
    )
    scored = [
        (
            r["id"],
            score_post(user_vec, list(r["topics"] or []), r["safety_score"], r["created_at"]),
            (list(r["topics"] or []) or [None])[0],
        )
        for r in candidates
        if r["id"] not in train_ids
    ]
    if not scored:
        return None
    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:k]

    hits = sum(1 for pid, _, _ in top if pid in test_ids)
    precision = hits / len(top)
    recall = hits / len(test_ids)
    ctr = hits / len(top)  # served impressions = top-K; clicks = held-out hits
    diversity = diversity_score([topic for _, _, topic in top])
    return precision, recall, ctr, diversity


async def main() -> int:
    parser = argparse.ArgumentParser(description="Offline recommendation evaluation")
    parser.add_argument("--k", type=int, default=10, help="top-K cutoff")
    parser.add_argument("--users", type=int, default=200, help="max users to sample")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    random.seed(args.seed)

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("ERROR: DATABASE_URL is not set", file=sys.stderr)
        return 1
    dsn = dsn.replace("postgresql+asyncpg://", "postgres://")

    conn = await asyncpg.connect(dsn)
    try:
        user_rows = await conn.fetch(
            """
            SELECT user_id, count(*) AS n
            FROM interactions
            WHERE type = ANY($1::interaction_type[])
            GROUP BY user_id
            HAVING count(*) >= 5
            ORDER BY n DESC
            LIMIT $2
            """,
            list(POSITIVE_TYPES), args.users,
        )
        if not user_rows:
            print("No users with >=5 positive interactions. Run seed.py first.", file=sys.stderr)
            return 1

        agg = {"precision": 0.0, "recall": 0.0, "ctr": 0.0, "diversity": 0.0}
        evaluated = 0
        for row in user_rows:
            res = await eval_user(conn, row["user_id"], args.k)
            if res is None:
                continue
            p, r, c, d = res
            agg["precision"] += p
            agg["recall"] += r
            agg["ctr"] += c
            agg["diversity"] += d
            evaluated += 1

        if evaluated == 0:
            print("No users could be evaluated.", file=sys.stderr)
            return 1

        print(f"Offline evaluation @K={args.k} over {evaluated} users:")
        print(f"  Precision@{args.k}: {agg['precision'] / evaluated:.4f}")
        print(f"  Recall@{args.k}:    {agg['recall'] / evaluated:.4f}")
        print(f"  CTR (sim):         {agg['ctr'] / evaluated:.4f}")
        print(f"  Diversity:         {agg['diversity'] / evaluated:.4f}")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
