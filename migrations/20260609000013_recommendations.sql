-- Impression log for the recommendation pipeline.
-- feed-service writes one row per served personalized post; content-service sets
-- clicked_at when the user later views that post. This is the source of truth for
-- offline CTR measurement (see scripts/evaluate.py and analytics-service).
CREATE TABLE IF NOT EXISTS recommendations (
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    post_id    UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    score      DOUBLE PRECISION NOT NULL,
    source     VARCHAR(50) NOT NULL,  -- 'follow' | 'topic' | 'recent' | 'trending' | 'fallback' | 'personalized'
    served_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    clicked_at TIMESTAMPTZ,
    PRIMARY KEY (user_id, post_id, served_at)
);

-- Per-user impression history, newest first.
CREATE INDEX IF NOT EXISTS idx_recs_user_served
    ON recommendations(user_id, served_at DESC);

-- CTR aggregation scans clicked vs total over a time window.
CREATE INDEX IF NOT EXISTS idx_recs_served_clicked
    ON recommendations(served_at) INCLUDE (clicked_at);
