-- P7-T1 recommendation telemetry retention.
--
-- Raw impressions and behavior events are retained for 180 days by default.
-- Derived aggregates such as user_pref_vectors are intentionally not touched;
-- they remain subject to account deletion and their own lifecycle policy.

CREATE OR REPLACE FUNCTION prune_recommendation_telemetry(
    retain_for INTERVAL DEFAULT INTERVAL '180 days'
)
RETURNS TABLE (
    behavior_events_deleted BIGINT,
    recommendation_impressions_deleted BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    cutoff_at TIMESTAMPTZ;
BEGIN
    IF retain_for < INTERVAL '1 day' THEN
        RAISE EXCEPTION 'recommendation telemetry retention must be at least 1 day';
    END IF;

    cutoff_at := statement_timestamp() - retain_for;

    WITH deleted AS (
        DELETE FROM behavior_events
        WHERE occurred_at < cutoff_at
        RETURNING 1
    )
    SELECT count(*) INTO behavior_events_deleted FROM deleted;

    WITH deleted AS (
        DELETE FROM recommendation_impressions
        WHERE served_at < cutoff_at
        RETURNING 1
    )
    SELECT count(*) INTO recommendation_impressions_deleted FROM deleted;

    RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION prune_recommendation_telemetry(INTERVAL) IS
    'Prunes raw recommendation telemetry after the configured retention window; default 180 days.';
