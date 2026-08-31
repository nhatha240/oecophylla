\set ON_ERROR_STOP on

BEGIN;

INSERT INTO users (id, username, email, password_hash)
VALUES (
    '10000000-0000-4000-8000-000000000001',
    't4a_contract_user',
    't4a-contract@example.invalid',
    'not-a-real-password-hash'
);

INSERT INTO posts (id, author_id, content, topics, status)
VALUES
    (
        '20000000-0000-4000-8000-000000000001',
        '10000000-0000-4000-8000-000000000001',
        'Nội dung kiểm thử tính năng bài viết.',
        ARRAY['công nghệ'],
        'published'
    ),
    (
        '20000000-0000-4000-8000-000000000002',
        '10000000-0000-4000-8000-000000000001',
        'Bài viết cũ vẫn hoạt động mà không cần embedding.',
        ARRAY['thời sự'],
        'published'
    );

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM posts p
        LEFT JOIN post_content_features f ON f.post_id = p.id
        WHERE p.id = '20000000-0000-4000-8000-000000000002'
          AND f.id IS NULL
    ) THEN
        RAISE EXCEPTION 'existing post without features was not preserved';
    END IF;
END;
$$;

INSERT INTO post_content_features (
    post_id,
    encoder_version,
    embedding,
    normalized_topics,
    content_hash,
    source_updated_at,
    computed_at
) VALUES (
    '20000000-0000-4000-8000-000000000001',
    'intfloat/multilingual-e5-small@614241f622f53c4eeff9890bdc4f31cfecc418b3',
    array_fill((1.0 / sqrt(384.0))::REAL, ARRAY[384]),
    ARRAY['công nghệ', 'thời sự'],
    repeat('a', 64),
    '2026-08-31T00:00:00Z',
    '2026-08-31T00:01:00Z'
);

DO $$
BEGIN
    BEGIN
        INSERT INTO post_content_features (
            post_id, encoder_version, embedding, normalized_topics,
            content_hash, source_updated_at, computed_at
        ) VALUES (
            '20000000-0000-4000-8000-000000000001',
            'intfloat/multilingual-e5-small@614241f622f53c4eeff9890bdc4f31cfecc418b3',
            array_fill((1.0 / sqrt(383.0))::REAL, ARRAY[383]),
            ARRAY['công nghệ'], repeat('b', 64), NOW(), NOW()
        );
        RAISE EXCEPTION 'wrong dimension was accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    BEGIN
        INSERT INTO post_content_features (
            post_id, encoder_version, embedding, normalized_topics,
            content_hash, source_updated_at, computed_at
        ) VALUES (
            '20000000-0000-4000-8000-000000000001',
            'unsupported encoder',
            array_fill((1.0 / sqrt(384.0))::REAL, ARRAY[384]),
            ARRAY['công nghệ'], repeat('c', 64), NOW(), NOW()
        );
        RAISE EXCEPTION 'unsupported encoder was accepted';
    EXCEPTION WHEN foreign_key_violation THEN NULL;
    END;

    BEGIN
        INSERT INTO post_content_features (
            post_id, encoder_version, embedding, normalized_topics,
            content_hash, source_updated_at, computed_at
        ) VALUES (
            '20000000-0000-4000-8000-000000000001',
            'intfloat/multilingual-e5-small@614241f622f53c4eeff9890bdc4f31cfecc418b3',
            array_fill((1.0 / sqrt(384.0))::REAL, ARRAY[384]),
            ARRAY['công nghệ'], 'INVALID CONTENT HASH', NOW(), NOW()
        );
        RAISE EXCEPTION 'invalid content hash was accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    BEGIN
        INSERT INTO post_content_features (
            post_id, encoder_version, embedding, normalized_topics,
            content_hash, source_updated_at, computed_at
        ) VALUES (
            '20000000-0000-4000-8000-000000000001',
            'intfloat/multilingual-e5-small@614241f622f53c4eeff9890bdc4f31cfecc418b3',
            array_fill((1.0 / sqrt(384.0))::REAL, ARRAY[384]),
            ARRAY['Công nghệ'], repeat('d', 64), NOW(), NOW()
        );
        RAISE EXCEPTION 'non-normalized topics were accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;

    BEGIN
        INSERT INTO post_content_features (
            post_id, encoder_version, embedding, normalized_topics,
            content_hash, source_updated_at, computed_at
        ) VALUES (
            '20000000-0000-4000-8000-000000000001',
            'intfloat/multilingual-e5-small@614241f622f53c4eeff9890bdc4f31cfecc418b3',
            array_fill((1.0 / sqrt(384.0))::REAL, ARRAY[384]),
            ARRAY['công nghệ', 'thời sự'], repeat('a', 64),
            '2026-08-31T00:00:00Z', '2026-08-31T00:01:00Z'
        );
        RAISE EXCEPTION 'duplicate feature was accepted';
    EXCEPTION WHEN unique_violation THEN NULL;
    END;

    BEGIN
        UPDATE post_content_features
        SET encoder_version = encoder_version
        WHERE post_id = '20000000-0000-4000-8000-000000000001';
        RAISE EXCEPTION 'immutable feature was updated';
    EXCEPTION WHEN SQLSTATE '55000' THEN NULL;
    END;

    BEGIN
        UPDATE post_content_encoder_versions
        SET model_revision = model_revision
        WHERE encoder_version =
            'intfloat/multilingual-e5-small@614241f622f53c4eeff9890bdc4f31cfecc418b3';
        RAISE EXCEPTION 'immutable encoder was updated';
    EXCEPTION WHEN SQLSTATE '55000' THEN NULL;
    END;

    BEGIN
        INSERT INTO post_content_features (
            post_id, encoder_version, embedding, normalized_topics,
            content_hash, source_updated_at, computed_at
        ) VALUES (
            '20000000-0000-4000-8000-000000000001',
            'intfloat/multilingual-e5-small@614241f622f53c4eeff9890bdc4f31cfecc418b3',
            array_fill((1.0 / sqrt(384.0))::REAL, ARRAY[384]),
            ARRAY['công nghệ'], repeat('f', 64),
            '2026-08-31T00:02:00Z', '2026-08-31T00:01:00Z'
        );
        RAISE EXCEPTION 'future feature source timestamp was accepted';
    EXCEPTION WHEN check_violation THEN NULL;
    END;
END;
$$;

-- Multiple encoder versions remain additive. A production version is added
-- only by a reviewed forward migration; this transaction rolls the test one back.
INSERT INTO post_content_encoder_versions (
    encoder_version, model_repository, model_revision,
    model_artifact_sha256, license_spdx, embedding_dimension,
    preprocessing_version
) VALUES (
    'multiple encoder versions',
    'fixture/encoder',
    repeat('1', 40),
    repeat('2', 64),
    'MIT',
    384,
    'post-content-normalization-v1'
);

INSERT INTO post_content_features (
    post_id, encoder_version, embedding, normalized_topics,
    content_hash, source_updated_at, computed_at
) VALUES (
    '20000000-0000-4000-8000-000000000001',
    'multiple encoder versions',
    array_fill((1.0 / sqrt(384.0))::REAL, ARRAY[384]),
    ARRAY['công nghệ'], repeat('e', 64), NOW(), NOW()
);

ROLLBACK;
