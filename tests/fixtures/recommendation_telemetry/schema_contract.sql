\set ON_ERROR_STOP on

-- P0-T1 schema contract fixture.
-- Run only against a disposable/test database. Everything is wrapped in a
-- transaction and rolled back, including the cascade-deletion assertions.
BEGIN;

INSERT INTO users (id, username, email, password_hash)
VALUES
    ('00000000-0000-7000-8000-000000000131', 'telemetry_fixture_1', 'telemetry-1@example.invalid', 'fixture'),
    ('00000000-0000-7000-8000-000000000132', 'telemetry_fixture_2', 'telemetry-2@example.invalid', 'fixture');

INSERT INTO posts (id, author_id, content, topics, status)
VALUES (
    '00000000-0000-7000-8000-000000000133',
    '00000000-0000-7000-8000-000000000132',
    'Telemetry schema contract fixture',
    ARRAY['ai', 'tech'],
    'published'
);

INSERT INTO recommendation_impressions (
    id,
    request_id,
    user_id,
    post_id,
    position,
    feed_source,
    candidate_source,
    score,
    model_version,
    feature_snapshot,
    served_at
)
VALUES (
    '00000000-0000-7000-8000-000000000134',
    '00000000-0000-7000-8000-000000000135',
    '00000000-0000-7000-8000-000000000131',
    '00000000-0000-7000-8000-000000000133',
    0,
    'personalized',
    'topic',
    0.625,
    'heuristic-v1',
    '{
      "schema_version": "rank-features-v1",
      "topic_relevance": 0.75,
      "freshness": 0.8,
      "safety_score": 1.0,
      "candidate_source": "topic",
      "is_followed_author": false,
      "author_affinity": null,
      "heuristic_score": 0.625,
      "ml_score": null
    }'::jsonb,
    '2026-08-27T10:00:00Z'
);

INSERT INTO behavior_events (
    id,
    client_event_id,
    user_id,
    post_id,
    impression_id,
    session_id,
    event_type,
    dwell_ms,
    metadata,
    occurred_at,
    ingested_at
)
VALUES
    (
        '00000000-0000-7000-8000-000000000136',
        '00000000-0000-7000-8000-000000000137',
        '00000000-0000-7000-8000-000000000131',
        '00000000-0000-7000-8000-000000000133',
        '00000000-0000-7000-8000-000000000134',
        '00000000-0000-7000-8000-000000000138',
        'visible',
        NULL,
        '{"viewport_ratio": 0.75}'::jsonb,
        '2026-08-27T10:00:01Z',
        '2026-08-27T10:00:01Z'
    ),
    (
        '00000000-0000-7000-8000-000000000139',
        '00000000-0000-7000-8000-000000000140',
        '00000000-0000-7000-8000-000000000131',
        '00000000-0000-7000-8000-000000000133',
        '00000000-0000-7000-8000-000000000134',
        '00000000-0000-7000-8000-000000000138',
        'dwell',
        12000,
        '{}'::jsonb,
        '2026-08-27T10:00:13Z',
        '2026-08-27T10:00:13Z'
    ),
    (
        '00000000-0000-7000-8000-000000000141',
        '00000000-0000-7000-8000-000000000142',
        '00000000-0000-7000-8000-000000000131',
        '00000000-0000-7000-8000-000000000133',
        '00000000-0000-7000-8000-000000000134',
        '00000000-0000-7000-8000-000000000138',
        'like',
        NULL,
        '{"source": "canonical-like-endpoint"}'::jsonb,
        '2026-08-27T10:00:15Z',
        '2026-08-27T10:00:15Z'
    );

DO $$
BEGIN
    IF (SELECT count(*) FROM recommendation_impressions) <> 1 THEN
        RAISE EXCEPTION 'expected exactly one fixture impression';
    END IF;

    IF (SELECT count(*) FROM behavior_events) <> 3 THEN
        RAISE EXCEPTION 'expected exactly three fixture behavior events';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM recommendation_impressions
        WHERE id = '00000000-0000-7000-8000-000000000134'
          AND feature_snapshot->>'schema_version' = 'rank-features-v1'
          AND feature_snapshot->'author_affinity' = 'null'::jsonb
    ) THEN
        RAISE EXCEPTION 'feature snapshot did not round-trip as JSON object';
    END IF;
END $$;

-- Idempotency: a retried client event must not create a second row.
DO $$
BEGIN
    BEGIN
        INSERT INTO behavior_events (
            client_event_id, user_id, post_id, event_type, occurred_at
        ) VALUES (
            '00000000-0000-7000-8000-000000000137',
            '00000000-0000-7000-8000-000000000131',
            '00000000-0000-7000-8000-000000000133',
            'visible',
            '2026-08-27T10:00:01Z'
        );
        RAISE EXCEPTION 'duplicate client_event_id unexpectedly succeeded';
    EXCEPTION
        WHEN unique_violation THEN NULL;
    END;
END $$;

-- A request cannot contain the same post twice for the same user.
DO $$
BEGIN
    BEGIN
        INSERT INTO recommendation_impressions (
            request_id, user_id, post_id, position, feed_source,
            candidate_source, model_version, feature_snapshot
        ) VALUES (
            '00000000-0000-7000-8000-000000000135',
            '00000000-0000-7000-8000-000000000131',
            '00000000-0000-7000-8000-000000000133',
            1,
            'personalized',
            'topic',
            'heuristic-v1',
            '{"schema_version":"rank-features-v1"}'::jsonb
        );
        RAISE EXCEPTION 'duplicate request/user/post unexpectedly succeeded';
    EXCEPTION
        WHEN unique_violation THEN NULL;
    END;
END $$;

-- An impression can only be attached to the same user/post pair.
DO $$
BEGIN
    BEGIN
        INSERT INTO behavior_events (
            client_event_id, user_id, post_id, impression_id,
            event_type, occurred_at
        ) VALUES (
            '00000000-0000-7000-8000-000000000143',
            '00000000-0000-7000-8000-000000000132',
            '00000000-0000-7000-8000-000000000133',
            '00000000-0000-7000-8000-000000000134',
            'visible',
            '2026-08-27T10:01:00Z'
        );
        RAISE EXCEPTION 'cross-user impression attachment unexpectedly succeeded';
    EXCEPTION
        WHEN foreign_key_violation THEN NULL;
    END;
END $$;

-- Boundary guards reject invalid positions, dwell values, and metadata shapes.
DO $$
BEGIN
    BEGIN
        INSERT INTO recommendation_impressions (
            request_id, user_id, post_id, position, feed_source,
            candidate_source, model_version, feature_snapshot
        ) VALUES (
            '00000000-0000-7000-8000-000000000144',
            '00000000-0000-7000-8000-000000000131',
            '00000000-0000-7000-8000-000000000133',
            -1,
            'personalized',
            'topic',
            'heuristic-v1',
            '{}'::jsonb
        );
        RAISE EXCEPTION 'negative impression position unexpectedly succeeded';
    EXCEPTION
        WHEN check_violation THEN NULL;
    END;

    BEGIN
        INSERT INTO behavior_events (
            client_event_id, user_id, post_id, event_type, dwell_ms
        ) VALUES (
            '00000000-0000-7000-8000-000000000145',
            '00000000-0000-7000-8000-000000000131',
            '00000000-0000-7000-8000-000000000133',
            'dwell',
            1800001
        );
        RAISE EXCEPTION 'oversized dwell unexpectedly succeeded';
    EXCEPTION
        WHEN check_violation THEN NULL;
    END;

    BEGIN
        INSERT INTO behavior_events (
            client_event_id, user_id, post_id, event_type, metadata
        ) VALUES (
            '00000000-0000-7000-8000-000000000146',
            '00000000-0000-7000-8000-000000000131',
            '00000000-0000-7000-8000-000000000133',
            'click',
            '[]'::jsonb
        );
        RAISE EXCEPTION 'non-object metadata unexpectedly succeeded';
    EXCEPTION
        WHEN check_violation THEN NULL;
    END;
END $$;

-- Privacy deletion: deleting a user removes their telemetry rows.
DELETE FROM users WHERE id = '00000000-0000-7000-8000-000000000131';

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM recommendation_impressions
        WHERE user_id = '00000000-0000-7000-8000-000000000131'
    ) THEN
        RAISE EXCEPTION 'user deletion did not cascade to impressions';
    END IF;

    IF EXISTS (
        SELECT 1 FROM behavior_events
        WHERE user_id = '00000000-0000-7000-8000-000000000131'
    ) THEN
        RAISE EXCEPTION 'user deletion did not cascade to behavior events';
    END IF;
END $$;

ROLLBACK;
