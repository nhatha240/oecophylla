-- P1-T4 feature worker idempotency receipts.
--
-- A receipt is claimed in the same PostgreSQL transaction that updates the
-- user's preference vector. Kafka offset replay can therefore observe either
-- both writes or neither write, never a partially applied feature event.

CREATE TABLE feature_event_receipts (
    event_id      UUID PRIMARY KEY,
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_type    TEXT NOT NULL CHECK (length(btrim(event_type)) BETWEEN 1 AND 64),
    occurred_at   TIMESTAMPTZ NOT NULL,
    processed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_feature_event_receipts_user_processed
    ON feature_event_receipts (user_id, processed_at DESC);

COMMENT ON TABLE feature_event_receipts IS
    'Feature-worker Kafka event receipts; inserted atomically with preference-vector updates.';
