-- Interaction events are inserted in the same transaction as their source
-- mutation. Delivery is at least once; consumers deduplicate by event_id.
CREATE TABLE interaction_event_outbox (
    event_id      UUID PRIMARY KEY,
    topic         TEXT NOT NULL CHECK (length(btrim(topic)) BETWEEN 1 AND 255),
    partition_key TEXT NOT NULL CHECK (length(btrim(partition_key)) BETWEEN 1 AND 255),
    payload       JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at       TIMESTAMPTZ,
    attempts      INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_error    TEXT
);

CREATE INDEX idx_interaction_event_outbox_pending
    ON interaction_event_outbox (created_at, event_id)
    WHERE sent_at IS NULL;

CREATE INDEX idx_interaction_event_outbox_sent
    ON interaction_event_outbox (sent_at, event_id)
    WHERE sent_at IS NOT NULL;

COMMENT ON TABLE interaction_event_outbox IS
    'Transactional interaction Kafka envelopes awaiting broker acknowledgement.';
