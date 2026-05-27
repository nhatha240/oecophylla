CREATE TYPE notification_kind AS ENUM (
    'liked',
    'commented',
    'replied',
    'followed',
    'post_hidden',
    'author_warned',
    'author_banned'
);

CREATE TABLE notifications (
    id           UUID PRIMARY KEY DEFAULT uuidv7(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind         notification_kind NOT NULL,
    actor_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    post_id      UUID REFERENCES posts(id) ON DELETE CASCADE,
    comment_id   UUID REFERENCES comments(id) ON DELETE CASCADE,
    payload      JSONB NOT NULL DEFAULT '{}'::jsonb,
    read_at      TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notifications_user_created
    ON notifications (user_id, created_at DESC);

CREATE INDEX idx_notifications_user_unread_created
    ON notifications (user_id, created_at DESC)
    WHERE read_at IS NULL;
