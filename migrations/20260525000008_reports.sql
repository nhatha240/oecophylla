CREATE TYPE report_status AS ENUM ('pending', 'resolved_hidden', 'resolved_ok', 'resolved_warned');

CREATE TABLE reports (
    id           UUID PRIMARY KEY DEFAULT uuidv7(),
    reporter_id  UUID REFERENCES users(id) ON DELETE SET NULL,
    post_id      UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    reason       VARCHAR(50) NOT NULL,
    detail       TEXT,
    status       report_status NOT NULL DEFAULT 'pending',
    resolved_by  UUID REFERENCES users(id) ON DELETE SET NULL,
    resolved_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reports_post            ON reports (post_id);
CREATE INDEX idx_reports_pending_created ON reports (created_at DESC) WHERE status = 'pending';
CREATE UNIQUE INDEX idx_reports_one_pending_per_user_post
    ON reports (reporter_id, post_id) WHERE status = 'pending';
