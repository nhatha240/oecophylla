CREATE TABLE user_avatars (
    user_id      UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    content_type TEXT NOT NULL CHECK (content_type IN ('image/jpeg', 'image/png', 'image/webp')),
    image_data   BYTEA NOT NULL CHECK (octet_length(image_data) BETWEEN 1 AND 5242880),
    version      UUID NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER trg_user_avatars_updated_at BEFORE UPDATE ON user_avatars
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
