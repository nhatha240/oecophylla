-- Preserve idempotency receipts after a user is deleted. Kafka retention can
-- outlive test/user rows; keeping the receipt lets the worker consume stale
-- events without retrying forever or recreating a preference vector.

ALTER TABLE feature_event_receipts
    DROP CONSTRAINT feature_event_receipts_user_id_fkey;

COMMENT ON COLUMN feature_event_receipts.user_id IS
    'Source user identity retained for replay dedupe; intentionally has no FK so receipts survive user deletion.';
