ALTER TABLE posts
    ADD COLUMN like_count    INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN comment_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN save_count    INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN share_count   INTEGER NOT NULL DEFAULT 0;

CREATE INDEX idx_posts_published_engagement ON posts
    ((like_count + comment_count * 2 + share_count) DESC, created_at DESC)
    WHERE status = 'published';
