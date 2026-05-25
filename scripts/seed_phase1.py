"""Seed Phase 1 data: 50 users, 100 posts, 200 follows."""
import os
import random
import sys
from argon2 import PasswordHasher
import psycopg

DATABASE_URL = os.environ["DATABASE_URL"]
SHARED_HASH = PasswordHasher().hash("Password!123")  # computed once

random.seed(20260525)

def main():
    with psycopg.connect(DATABASE_URL, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM users")
            (n,) = cur.fetchone()
            if n > 0:
                print(f"users table not empty ({n} rows); aborting", file=sys.stderr)
                sys.exit(2)

            roles = ["admin"] * 3 + ["creator"] * 7 + ["user"] * 40
            user_ids = []
            for i, role in enumerate(roles):
                username = f"seed_{i:03d}"
                email = f"{username}@oec.local"
                cur.execute(
                    """INSERT INTO users (username, email, password_hash, role, display_name)
                       VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                    (username, email, SHARED_HASH, role, f"Seed User {i:03d}"),
                )
                user_ids.append(cur.fetchone()[0])

            topics_pool = ["tech", "science", "sports", "politics", "entertainment", "health", "business", "culture", "education", "environment"]
            for i in range(100):
                author = random.choice(user_ids)
                topics = random.sample(topics_pool, k=random.randint(1, 3))
                cur.execute(
                    """INSERT INTO posts (author_id, content, tags, topics, status)
                       VALUES (%s, %s, %s, %s, 'published')""",
                    (author, f"Seeded post #{i} about {topics[0]}", topics, topics),
                )

            edges = set()
            while len(edges) < 200:
                a, b = random.sample(user_ids, 2)
                edges.add((a, b))
            for a, b in edges:
                cur.execute(
                    "INSERT INTO follows (follower_id, followee_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (a, b),
                )

        conn.commit()
    print(f"Seeded: {len(user_ids)} users, 100 posts, 200 follows")

if __name__ == "__main__":
    main()
