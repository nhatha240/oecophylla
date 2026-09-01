-- T3 preference-vector-v2 storage. Additive and forward-only: v1 remains the
-- immediate rollback target and must not be removed while v2 is rolling out.

CREATE TABLE user_preference_vectors_v2 (
    user_id             UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    schema_version      TEXT NOT NULL DEFAULT 'preference-vector-v2'
                        CHECK (schema_version = 'preference-vector-v2'),
    positive_weights    JSONB NOT NULL DEFAULT '{}'
                        CHECK (jsonb_typeof(positive_weights) = 'object')
                        CHECK (NOT jsonb_path_exists(
                            positive_weights,
                            '$.* ? (@.type() != "number" || @ < 0 || @ > 10)'
                        )),
    negative_weights    JSONB NOT NULL DEFAULT '{}'
                        CHECK (jsonb_typeof(negative_weights) = 'object')
                        CHECK (NOT jsonb_path_exists(
                            negative_weights,
                            '$.* ? (@.type() != "number" || @ < 0 || @ > 10)'
                        )),
    reference_at        TIMESTAMPTZ NOT NULL,
    source_event_count  INTEGER NOT NULL DEFAULT 0 CHECK (source_event_count >= 0),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_user_preference_vectors_v2_updated
    ON user_preference_vectors_v2 (updated_at DESC);

CREATE TRIGGER trg_user_pref_vectors_v2_updated_at
    BEFORE UPDATE ON user_preference_vectors_v2
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Operational queue for the feature worker's resumable backfill. The worker
-- derives every value by replaying canonical behavior_events joined to the
-- event-time post topics; the view itself does not materialize a vector.
CREATE VIEW preference_vector_v2_backfill_users AS
SELECT
    user_id,
    MIN(occurred_at) AS first_event_at,
    MAX(occurred_at) AS last_event_at,
    COUNT(*)::BIGINT AS event_count
FROM behavior_events
GROUP BY user_id;

COMMENT ON TABLE user_preference_vectors_v2 IS
    'Bounded positive/negative event-time preference-vector-v2 channels; v1 is retained for rollback.';
COMMENT ON VIEW preference_vector_v2_backfill_users IS
    'Users eligible for canonical behavior_events replay by the feature worker.';

