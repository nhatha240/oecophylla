CREATE TABLE comments (
    id                 UUID PRIMARY KEY DEFAULT uuidv7(),
    post_id            UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    author_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_comment_id  UUID REFERENCES comments(id) ON DELETE CASCADE,
    content            TEXT NOT NULL CHECK (length(content) BETWEEN 1 AND 2000),
    is_deleted         BOOLEAN NOT NULL DEFAULT false,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (parent_comment_id IS NULL OR parent_comment_id <> id)
);

CREATE INDEX idx_comments_post_created ON comments (post_id, created_at ASC) WHERE is_deleted = false;
CREATE INDEX idx_comments_parent       ON comments (parent_comment_id, created_at ASC)
                                       WHERE parent_comment_id IS NOT NULL AND is_deleted = false;
CREATE INDEX idx_comments_author       ON comments (author_id, created_at DESC);

CREATE TRIGGER trg_comments_updated_at BEFORE UPDATE ON comments
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
