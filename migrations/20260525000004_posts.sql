CREATE TABLE posts (
    id           UUID PRIMARY KEY DEFAULT uuidv7(),
    author_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content      TEXT    NOT NULL CHECK (length(content) BETWEEN 1 AND 4000),
    media_urls   TEXT[]  NOT NULL DEFAULT '{}',
    tags         TEXT[]  NOT NULL DEFAULT '{}',
    topics       TEXT[]  NOT NULL DEFAULT '{}',
    safety_score REAL    NOT NULL DEFAULT 1.0
                  CHECK (safety_score BETWEEN 0 AND 1),
    status       post_status NOT NULL DEFAULT 'pending',
    view_count   BIGINT  NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_posts_author_created   ON posts (author_id, created_at DESC);
CREATE INDEX idx_posts_published_created ON posts (created_at DESC) WHERE status = 'published';
CREATE INDEX idx_posts_topics_gin        ON posts USING GIN (topics);

CREATE TRIGGER trg_posts_updated_at BEFORE UPDATE ON posts
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
