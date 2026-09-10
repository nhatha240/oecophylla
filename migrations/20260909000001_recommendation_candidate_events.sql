-- Protected operational retrieval telemetry. This table is never an engagement
-- label source; only final served impressions can join observed behavior.
CREATE TABLE recommendation_candidate_events (
    retrieval_request_id UUID NOT NULL,
    post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    stage TEXT NOT NULL CHECK (stage = 'eligible'),
    source TEXT NOT NULL,
    retrieval_score DOUBLE PRECISION CHECK (
        retrieval_score > '-Infinity'::float8 AND retrieval_score < 'Infinity'::float8),
    eligibility_reason TEXT NOT NULL,
    model_version TEXT NOT NULL,
    retrieval_version TEXT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (retrieval_request_id, post_id, stage)
);
CREATE INDEX idx_recommendation_candidate_events_retention
    ON recommendation_candidate_events(recorded_at);
CREATE FUNCTION reject_candidate_event_update() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'candidate events are append-only' USING ERRCODE = '55000';
END;
$$;
CREATE TRIGGER candidate_events_append_only BEFORE UPDATE ON recommendation_candidate_events
    FOR EACH ROW EXECUTE FUNCTION reject_candidate_event_update();
-- Run via the existing maintenance job; deletion is restricted to expired rows
-- by this bounded operation. Parent post erasure remains supported by the FK.
CREATE FUNCTION prune_recommendation_candidate_events(retention_days INTEGER DEFAULT 7,
                                                       batch_size INTEGER DEFAULT 10000)
RETURNS BIGINT LANGUAGE plpgsql AS $$
DECLARE removed BIGINT;
BEGIN
    IF retention_days < 1 OR retention_days > 30 OR batch_size < 1 OR batch_size > 10000 THEN
        RAISE EXCEPTION 'invalid candidate telemetry retention bounds';
    END IF;
    DELETE FROM recommendation_candidate_events WHERE ctid IN (
        SELECT ctid FROM recommendation_candidate_events
        WHERE recorded_at < now() - make_interval(days => retention_days)
        ORDER BY recorded_at LIMIT batch_size
    );
    GET DIAGNOSTICS removed = ROW_COUNT;
    RETURN removed;
END;
$$;
