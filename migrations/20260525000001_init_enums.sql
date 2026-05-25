CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TYPE user_role   AS ENUM ('user', 'creator', 'admin');
CREATE TYPE post_status AS ENUM ('pending', 'published', 'hidden', 'flagged');

CREATE FUNCTION set_updated_at() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END $$;
