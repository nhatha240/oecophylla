-- Versioned multilingual post features for recommendation.
--
-- This migration is additive and forward-only. Existing posts remain valid
-- without a feature row, so keyword topics continue to serve as the fallback.

CREATE FUNCTION post_content_embedding_is_valid(
    vector_values REAL[],
    expected_dimension INTEGER
) RETURNS BOOLEAN
LANGUAGE plpgsql
IMMUTABLE
STRICT
AS $$
DECLARE
    coordinate REAL;
    squared_norm DOUBLE PRECISION := 0.0;
BEGIN
    IF array_ndims(vector_values) IS DISTINCT FROM 1
       OR array_lower(vector_values, 1) IS DISTINCT FROM 1
       OR cardinality(vector_values) IS DISTINCT FROM expected_dimension THEN
        RETURN false;
    END IF;

    FOREACH coordinate IN ARRAY vector_values LOOP
        IF coordinate IS NULL
           OR coordinate = 'NaN'::REAL
           OR coordinate = 'Infinity'::REAL
           OR coordinate = '-Infinity'::REAL THEN
            RETURN false;
        END IF;
        squared_norm := squared_norm + coordinate::DOUBLE PRECISION
                                     * coordinate::DOUBLE PRECISION;
    END LOOP;

    -- Encoder output is L2-normalized before storage. The tolerance permits
    -- float32 round-off while rejecting zero or unnormalized vectors.
    RETURN abs(sqrt(squared_norm) - 1.0) <= 0.001;
END;
$$;

CREATE FUNCTION post_content_topics_are_normalized(topic_values TEXT[])
RETURNS BOOLEAN
LANGUAGE plpgsql
IMMUTABLE
STRICT
AS $$
DECLARE
    label TEXT;
    previous_label TEXT;
    seen TEXT[] := '{}';
BEGIN
    IF cardinality(topic_values) > 32 THEN
        RETURN false;
    END IF;

    FOREACH label IN ARRAY topic_values LOOP
        IF label IS NULL
           OR label = ''
           OR label <> btrim(label)
           OR label <> lower(label)
           OR char_length(label) > 64
           OR regexp_replace(label, '[[:space:]]+', ' ', 'g') <> label
           OR array_position(seen, label) IS NOT NULL
           OR (
               previous_label IS NOT NULL
               AND label COLLATE "C" <= previous_label COLLATE "C"
           ) THEN
            RETURN false;
        END IF;
        seen := array_append(seen, label);
        previous_label := label;
    END LOOP;

    RETURN true;
END;
$$;

CREATE TABLE post_content_encoder_versions (
    encoder_version       TEXT PRIMARY KEY
                          CHECK (
                              encoder_version ~
                              '^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*@[0-9a-f]{40}$'
                          ),
    model_repository      TEXT NOT NULL
                          CHECK (
                              model_repository ~
                              '^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$'
                          ),
    model_revision        TEXT NOT NULL CHECK (model_revision ~ '^[0-9a-f]{40}$'),
    model_artifact_sha256 TEXT NOT NULL
                          CHECK (model_artifact_sha256 ~ '^[0-9a-f]{64}$'),
    license_spdx          TEXT NOT NULL
                          CHECK (length(btrim(license_spdx)) BETWEEN 1 AND 32),
    embedding_dimension  SMALLINT NOT NULL CHECK (embedding_dimension = 384),
    preprocessing_version TEXT NOT NULL
                          CHECK (preprocessing_version = 'post-content-normalization-v1'),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_post_content_encoder_canonical_identity
        CHECK (encoder_version = model_repository || '@' || model_revision)
);

INSERT INTO post_content_encoder_versions (
    encoder_version,
    model_repository,
    model_revision,
    model_artifact_sha256,
    license_spdx,
    embedding_dimension,
    preprocessing_version
) VALUES (
    'intfloat/multilingual-e5-small@614241f622f53c4eeff9890bdc4f31cfecc418b3',
    'intfloat/multilingual-e5-small',
    '614241f622f53c4eeff9890bdc4f31cfecc418b3',
    '1a55775f53449dac10a2bcbc312469fac40b96d53198c407081a831f81c98477',
    'MIT',
    384,
    'post-content-normalization-v1'
);

CREATE TABLE post_content_features (
    id                UUID PRIMARY KEY DEFAULT uuidv7(),
    post_id           UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    encoder_version   TEXT NOT NULL REFERENCES post_content_encoder_versions(encoder_version),
    embedding         REAL[] NOT NULL
                      CHECK (post_content_embedding_is_valid(embedding, 384)),
    normalized_topics TEXT[] NOT NULL DEFAULT '{}'
                      CHECK (post_content_topics_are_normalized(normalized_topics)),
    content_hash      TEXT NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    source_updated_at TIMESTAMPTZ NOT NULL,
    computed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_post_content_features_temporal_order
        CHECK (source_updated_at <= computed_at),
    CONSTRAINT uq_post_content_features_content_revision
        UNIQUE (post_id, encoder_version, content_hash)
);

CREATE INDEX idx_post_content_features_latest
    ON post_content_features (
        post_id,
        encoder_version,
        source_updated_at DESC,
        computed_at DESC
    );
CREATE INDEX idx_post_content_features_topics_gin
    ON post_content_features USING GIN (normalized_topics);

CREATE FUNCTION prevent_post_content_feature_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- A parent post deletion invokes this trigger below the FK cascade trigger
    -- (depth > 1). Permit that lifecycle cascade, but reject direct deletion.
    IF TG_OP = 'DELETE' AND pg_trigger_depth() > 1 THEN
        RETURN OLD;
    END IF;

    RAISE EXCEPTION 'post content feature rows are immutable; insert a new content hash or encoder version'
        USING ERRCODE = '55000';
END;
$$;

CREATE TRIGGER trg_post_content_features_immutable
    BEFORE UPDATE OR DELETE ON post_content_features
    FOR EACH ROW EXECUTE FUNCTION prevent_post_content_feature_mutation();

CREATE FUNCTION prevent_post_content_encoder_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'post content encoder contracts are immutable; add a new encoder version'
        USING ERRCODE = '55000';
END;
$$;

CREATE TRIGGER trg_post_content_encoder_versions_immutable
    BEFORE UPDATE OR DELETE ON post_content_encoder_versions
    FOR EACH ROW EXECUTE FUNCTION prevent_post_content_encoder_mutation();

COMMENT ON TABLE post_content_features IS
    'Append-only operational post features. Raw post_id must not be exported to datasets or model artifacts.';
COMMENT ON COLUMN post_content_features.content_hash IS
    'Lowercase SHA-256 of post-content-normalization-v1 plus the normalized source text.';
COMMENT ON COLUMN post_content_features.source_updated_at IS
    'Source content timestamp used to prevent future-feature leakage.';
