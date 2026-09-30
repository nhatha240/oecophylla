-- Preserve the topics used to interpret new interactions when a post is later
-- edited. Historical NULL rows still require the current-post fallback.
ALTER TABLE behavior_events ADD COLUMN topic_snapshot TEXT[];

COMMENT ON COLUMN behavior_events.topic_snapshot IS
    'Server-captured effective post topics at behavior insertion time; NULL only for pre-migration rows.';
