-- P0-T1 recommendation telemetry schema.
--
-- This is an additive, forward-only migration. The tables are intentionally
-- created empty, so regular index creation does not block an existing hot
-- table. Once deployed, rollback must use a new forward migration; do not edit
-- or drop this migration when telemetry data exists.

CREATE TABLE recommendation_impressions (
    id               UUID PRIMARY KEY DEFAULT uuidv7(),
    request_id       UUID NOT NULL,
    user_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    post_id          UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    position         SMALLINT NOT NULL CHECK (position >= 0),
    feed_source      TEXT NOT NULL
                     CHECK (length(btrim(feed_source)) BETWEEN 1 AND 32),
    candidate_source TEXT NOT NULL
                     CHECK (length(btrim(candidate_source)) BETWEEN 1 AND 64),
    score            REAL
                     CHECK (score IS NULL OR score BETWEEN -1000000.0 AND 1000000.0),
    model_version    TEXT NOT NULL
                     CHECK (length(btrim(model_version)) BETWEEN 1 AND 128),
    feature_snapshot JSONB NOT NULL
                     CHECK (jsonb_typeof(feature_snapshot) = 'object')
                     CHECK (feature_snapshot ? 'schema_version')
                     CHECK (jsonb_typeof(feature_snapshot->'schema_version') = 'string')
                     CHECK (
                         length(btrim(feature_snapshot->>'schema_version'))
                         BETWEEN 1 AND 100
                     )
                     CHECK (octet_length(feature_snapshot::text) <= 16384),
    served_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_recommendation_impressions_request_user_post
        UNIQUE (request_id, user_id, post_id),
    -- Supports a composite FK that proves an event's impression belongs to
    -- the same user/post pair. `id` remains the public identity/primary key.
    CONSTRAINT uq_recommendation_impressions_identity
        UNIQUE (id, user_id, post_id)
);

CREATE INDEX idx_recommendation_impressions_user_served
    ON recommendation_impressions (user_id, served_at DESC);
CREATE INDEX idx_recommendation_impressions_post_served
    ON recommendation_impressions (post_id, served_at DESC);
CREATE INDEX idx_recommendation_impressions_model_served
    ON recommendation_impressions (model_version, served_at DESC);

CREATE TABLE behavior_events (
    id              UUID PRIMARY KEY DEFAULT uuidv7(),
    client_event_id UUID NOT NULL UNIQUE,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    post_id         UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    impression_id   UUID,
    session_id      UUID,
    event_type      TEXT NOT NULL CHECK (event_type IN (
                        'visible',
                        'view',
                        'click',
                        'dwell',
                        'like',
                        'unlike',
                        'save',
                        'unsave',
                        'share',
                        'unshare',
                        'hide',
                        'unhide',
                        'report',
                        'comment'
                    )),
    dwell_ms        INTEGER CHECK (dwell_ms IS NULL OR dwell_ms BETWEEN 0 AND 1800000),
    metadata        JSONB NOT NULL DEFAULT '{}'
                    CHECK (jsonb_typeof(metadata) = 'object')
                    CHECK (octet_length(metadata::text) <= 8192),
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_behavior_events_dwell_required
        CHECK (event_type <> 'dwell' OR dwell_ms IS NOT NULL),
    CONSTRAINT ck_behavior_events_dwell_event_type
        CHECK (dwell_ms IS NULL OR event_type IN ('view', 'dwell')),
    CONSTRAINT fk_behavior_events_impression_identity
        FOREIGN KEY (impression_id, user_id, post_id)
        REFERENCES recommendation_impressions (id, user_id, post_id)
        ON DELETE SET NULL (impression_id)
);

CREATE INDEX idx_behavior_events_user_occurred
    ON behavior_events (user_id, occurred_at DESC);
CREATE INDEX idx_behavior_events_post_occurred
    ON behavior_events (post_id, occurred_at DESC);
CREATE INDEX idx_behavior_events_impression
    ON behavior_events (impression_id)
    WHERE impression_id IS NOT NULL;
CREATE INDEX idx_behavior_events_type_occurred
    ON behavior_events (event_type, occurred_at DESC);

COMMENT ON TABLE recommendation_impressions IS
    'Append-only record of feed items served to authenticated users.';
COMMENT ON COLUMN recommendation_impressions.feature_snapshot IS
    'Versioned rank feature values captured at serving time; maximum 16 KiB.';
COMMENT ON TABLE behavior_events IS
    'Append-only user behavior telemetry; user_id is always server-derived.';
COMMENT ON COLUMN behavior_events.client_event_id IS
    'Idempotency key retained across client retries; server-generated for canonical actions.';
