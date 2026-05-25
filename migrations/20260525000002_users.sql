CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT uuidv7(),
    username      VARCHAR(50)  UNIQUE NOT NULL,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          user_role    NOT NULL DEFAULT 'user',
    display_name  VARCHAR(100),
    bio           TEXT,
    avatar_url    TEXT,
    topic_prefs   TEXT[]       NOT NULL DEFAULT '{}',
    is_active     BOOLEAN      NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- UNIQUE already indexes username/email — no redundant idx_users_username/email.
CREATE INDEX idx_users_search_trgm ON users
  USING GIN (username gin_trgm_ops, display_name gin_trgm_ops);

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
