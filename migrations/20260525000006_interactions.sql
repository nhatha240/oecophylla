CREATE TYPE interaction_type AS ENUM ('like', 'save', 'share', 'hide', 'report');

CREATE TABLE interactions (
    id           UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    post_id      UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    type         interaction_type NOT NULL,
    weight       REAL NOT NULL,
    metadata     JSONB NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_interactions_unique_single ON interactions (user_id, post_id, type);
CREATE INDEX        idx_interactions_post_type     ON interactions (post_id, type);
CREATE INDEX        idx_interactions_user_time     ON interactions (user_id, created_at DESC);
