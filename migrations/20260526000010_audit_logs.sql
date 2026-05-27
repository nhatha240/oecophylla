CREATE TYPE audit_action AS ENUM (
    'report_dismissed',
    'post_hidden',
    'post_unhidden',
    'author_warned',
    'author_banned',
    'author_unbanned'
);

CREATE TABLE audit_logs (
    id          UUID PRIMARY KEY DEFAULT uuidv7(),
    actor_id    UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    action      audit_action NOT NULL,
    target_type TEXT NOT NULL,
    target_id   UUID NOT NULL,
    report_id   UUID REFERENCES reports(id) ON DELETE SET NULL,
    note        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_actor_created ON audit_logs (actor_id, created_at DESC);
CREATE INDEX idx_audit_logs_target        ON audit_logs (target_type, target_id);
CREATE INDEX idx_audit_logs_report        ON audit_logs (report_id);
