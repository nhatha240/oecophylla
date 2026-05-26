CREATE TABLE user_preference_vectors (
    user_id       UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    topic_weights JSONB NOT NULL DEFAULT '{}',
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_user_pref_vectors_updated_at
    ON user_preference_vectors (updated_at DESC);

CREATE TRIGGER trg_user_pref_vectors_updated_at BEFORE UPDATE ON user_preference_vectors
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
