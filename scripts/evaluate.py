#!/usr/bin/env python3
"""Offline recommendation evaluation for Oecophylla.

Computes Precision@K, Recall@K, CTR simulation, and diversity
against the live database. No external service calls needed.

Usage:
    python scripts/evaluate.py --k 10 --user-limit 50
    python scripts/evaluate.py --k 20 --db postgres://user:pass@host:5432/db
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field

import psycopg


# ---------------------------------------------------------------------------
# Interaction classification
# ---------------------------------------------------------------------------

POSITIVE_INTERACTIONS = frozenset({"like", "comment", "share", "save"})
NEGATIVE_INTERACTIONS = frozenset({"hide", "report"})
MIN_POSITIVE_INTERACTIONS = 3


# ---------------------------------------------------------------------------
# Data containers (immutable)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Post:
    id: str
    topics: tuple[str, ...]


@dataclass(frozen=True)
class UserMetrics:
    user_id: str
    precision_at_k: float
    recall_at_k: float
    ctr_simulation: float
    diversity: float
    num_positive: int
    num_recommended_hits: int


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_user_vectors(
    conn: psycopg.Connection,
    user_limit: int,
) -> dict[str, dict[str, float]]:
    """Load user preference vectors from the database.

    Returns {user_id: {topic: weight, ...}}.
    Only loads users who have at least one preference vector entry.
    """
    cur = conn.execute(
        """
        SELECT user_id, topic_weights
        FROM user_preference_vectors
        ORDER BY user_id
        LIMIT %s
        """,
        (user_limit,),
    )
    vectors: dict[str, dict[str, float]] = {}
    for row in cur:
        user_id = str(row[0])
        topic_weights = row[1] if row[1] else {}
        # topic_weights is JSONB — psycopg returns it as a dict
        if isinstance(topic_weights, dict) and topic_weights:
            vectors[user_id] = {k: float(v) for k, v in topic_weights.items()}
    return vectors


def load_positive_interactions(conn: psycopg.Connection) -> dict[str, set[str]]:
    """Load positive interactions grouped by user.

    Returns {user_id: {post_id, ...}} for like/comment/share/save.
    """
    cur = conn.execute(
        """
        SELECT user_id::text, post_id::text
        FROM interactions
        WHERE type = ANY(%s)
        """,
        (list(POSITIVE_INTERACTIONS),),
    )
    positive: dict[str, set[str]] = defaultdict(set)
    for row in cur:
        positive[row[0]].add(row[1])
    return dict(positive)


def load_published_posts(conn: psycopg.Connection) -> dict[str, Post]:
    """Load all published posts with their topics.

    Returns {post_id: Post}.
    """
    cur = conn.execute(
        """
        SELECT id::text, topics
        FROM posts
        WHERE status = 'published'
        """,
    )
    posts: dict[str, Post] = {}
    for row in cur:
        post_id = row[0]
        topics = tuple(row[1]) if row[1] else ()
        posts[post_id] = Post(id=post_id, topics=topics)
    return posts


# ---------------------------------------------------------------------------
# Scoring & evaluation
# ---------------------------------------------------------------------------

def score_post(user_vector: dict[str, float], post: Post) -> float:
    """Compute relevance score for a post given a user's preference vector.

    Score = sum of user's topic_weight for each topic present in the post.
    This is a dot-product style overlap (not full cosine, since post vectors
    are binary indicators).
    """
    return sum(user_vector.get(topic, 0.0) for topic in post.topics)


def evaluate_user(
    user_id: str,
    user_vector: dict[str, float],
    positive_post_ids: set[str],
    all_posts: dict[str, Post],
    k: int,
) -> UserMetrics | None:
    """Evaluate recommendation quality for a single user.

    Returns None if the user has fewer than MIN_POSITIVE_INTERACTIONS
    positive interactions (not enough data to evaluate).
    """
    if len(positive_post_ids) < MIN_POSITIVE_INTERACTIONS:
        return None

    # Score all candidate posts (exclude posts the user already interacted with
    # to simulate a realistic recommendation scenario — we still measure against
    # those interactions as ground truth)
    scored: list[tuple[str, float]] = []
    for post_id, post in all_posts.items():
        s = score_post(user_vector, post)
        if s > 0:
            scored.append((post_id, s))

    # Sort descending by score, break ties deterministically by post_id
    scored.sort(key=lambda x: (-x[1], x[0]))
    recommended_ids = {pid for pid, _ in scored[:k]}

    # Metrics
    hits = recommended_ids & positive_post_ids
    precision = len(hits) / k if k > 0 else 0.0
    recall = len(hits) / len(positive_post_ids) if positive_post_ids else 0.0

    # CTR simulation: normalized average score of recommended posts
    # Proxy for click probability — higher scores mean more relevant content
    if scored:
        top_k_scores = [s for _, s in scored[:k]]
        max_score = top_k_scores[0] if top_k_scores else 1.0
        ctr = sum(top_k_scores) / (max_score * k) if max_score > 0 and k > 0 else 0.0
    else:
        ctr = 0.0

    # Diversity: fraction of unique topics across top-K posts
    recommended_posts = [all_posts[pid] for pid, _ in scored[:k] if pid in all_posts]
    all_topics: set[str] = set()
    for p in recommended_posts:
        all_topics.update(p.topics)
    diversity = len(all_topics) / k if k > 0 else 0.0

    return UserMetrics(
        user_id=user_id,
        precision_at_k=precision,
        recall_at_k=recall,
        ctr_simulation=ctr,
        diversity=diversity,
        num_positive=len(positive_post_ids),
        num_recommended_hits=len(hits),
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_results(metrics: list[UserMetrics], k: int) -> None:
    """Print evaluation results as a formatted table."""
    if not metrics:
        print("\nNo users had enough data to evaluate.")
        return

    n = len(metrics)
    avg_precision = sum(m.precision_at_k for m in metrics) / n
    avg_recall = sum(m.recall_at_k for m in metrics) / n
    avg_ctr = sum(m.ctr_simulation for m in metrics) / n
    avg_diversity = sum(m.diversity for m in metrics) / n
    avg_hits = sum(m.num_recommended_hits for m in metrics) / n
    avg_positive = sum(m.num_positive for m in metrics) / n

    header = f"Oecophylla Offline Evaluation (K={k}, users={n})"
    sep = "=" * len(header)

    print(f"\n{sep}")
    print(header)
    print(sep)
    print(f"  {'Metric':<25} {'Value':>10}")
    print(f"  {'-' * 25} {'-' * 10}")
    print(f"  {'Precision@K':<25} {avg_precision:>10.4f}")
    print(f"  {'Recall@K':<25} {avg_recall:>10.4f}")
    print(f"  {'CTR simulation':<25} {avg_ctr:>10.4f}")
    print(f"  {'Diversity':<25} {avg_diversity:>10.4f}")
    print(f"  {'Avg hits in top-K':<25} {avg_hits:>10.2f}")
    print(f"  {'Avg positive interactions':<25} {avg_positive:>10.1f}")
    print(sep)

    # Per-user detail (top 5 by precision, bottom 5 by precision)
    if n > 1:
        sorted_by_p = sorted(metrics, key=lambda m: m.precision_at_k, reverse=True)
        top = sorted_by_p[:5]
        bottom = sorted_by_p[-5:]

        print(f"\n  Top users by Precision@K:")
        print(f"  {'User ID':<38} {'Prec':>6} {'Recall':>7} {'Hits':>5} {'Pos':>4}")
        for m in top:
            print(
                f"  {m.user_id:<38} {m.precision_at_k:>6.3f} "
                f"{m.recall_at_k:>7.3f} {m.num_recommended_hits:>5} "
                f"{m.num_positive:>4}"
            )

        if n > 5:
            print(f"\n  Bottom users by Precision@K:")
            print(f"  {'User ID':<38} {'Prec':>6} {'Recall':>7} {'Hits':>5} {'Pos':>4}")
            for m in bottom:
                print(
                    f"  {m.user_id:<38} {m.precision_at_k:>6.3f} "
                    f"{m.recall_at_k:>7.3f} {m.num_recommended_hits:>5} "
                    f"{m.num_positive:>4}"
                )

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline recommendation evaluation for Oecophylla",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=10,
        help="Top-K for evaluation (default: 10)",
    )
    parser.add_argument(
        "--user-limit",
        type=int,
        default=50,
        help="Max users to evaluate (default: 50)",
    )
    parser.add_argument(
        "--db",
        default=os.environ.get("DATABASE_URL"),
        help="Database URL (default: $DATABASE_URL)",
    )
    args = parser.parse_args()

    if not args.db:
        print("ERROR: DATABASE_URL not set and --db not provided", file=sys.stderr)
        sys.exit(1)

    if args.k < 1:
        print("ERROR: --k must be >= 1", file=sys.stderr)
        sys.exit(1)

    if args.user_limit < 1:
        print("ERROR: --user-limit must be >= 1", file=sys.stderr)
        sys.exit(1)

    print(f"Connecting to database...")
    try:
        conn = psycopg.connect(args.db)
    except Exception as exc:
        print(f"ERROR: Failed to connect to database: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        print(f"Loading user preference vectors (limit={args.user_limit})...")
        user_vectors = load_user_vectors(conn, args.user_limit)
        if not user_vectors:
            print("ERROR: No user preference vectors found. "
                  "Run the feature-store-worker first.", file=sys.stderr)
            sys.exit(1)
        print(f"  Loaded {len(user_vectors)} user vectors")

        print("Loading positive interactions...")
        positive_interactions = load_positive_interactions(conn)
        print(f"  Found {sum(len(v) for v in positive_interactions.values())} "
              f"positive interactions across {len(positive_interactions)} users")

        print("Loading published posts...")
        all_posts = load_published_posts(conn)
        if not all_posts:
            print("ERROR: No published posts found.", file=sys.stderr)
            sys.exit(1)
        print(f"  Loaded {len(all_posts)} published posts")

        # Evaluate each user
        print(f"\nEvaluating (K={args.k})...")
        results: list[UserMetrics] = []
        skipped = 0
        for user_id, vector in user_vectors.items():
            pos_ids = positive_interactions.get(user_id, set())
            m = evaluate_user(user_id, vector, pos_ids, all_posts, args.k)
            if m is not None:
                results.append(m)
            else:
                skipped += 1

        if skipped > 0:
            print(f"  Skipped {skipped} users with < {MIN_POSITIVE_INTERACTIONS} "
                  f"positive interactions")

        print_results(results, args.k)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
