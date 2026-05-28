-- array_to_string is STABLE, so it cannot be used directly in a STORED
-- generated column. For text[] the conversion is deterministic, so wrap it in
-- an IMMUTABLE function to satisfy the generated-column requirement.
CREATE OR REPLACE FUNCTION immutable_array_to_string(arr text[], sep text)
RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT array_to_string(arr, sep)
$$;

-- Add tsvector column to posts for full-text search
ALTER TABLE posts
  ADD COLUMN IF NOT EXISTS search_vector tsvector
    GENERATED ALWAYS AS (
      to_tsvector('english'::regconfig,
        coalesce(content, '') || ' ' || immutable_array_to_string(coalesce(tags, '{}'), ' ')
      )
    ) STORED;

-- GIN index for full-text search on posts
CREATE INDEX IF NOT EXISTS idx_posts_search_vector
  ON posts USING GIN(search_vector);

-- GIN index on tags array for tag-filter queries
CREATE INDEX IF NOT EXISTS idx_posts_tags
  ON posts USING GIN(tags);

-- Index for user search by username prefix
CREATE INDEX IF NOT EXISTS idx_users_username_lower
  ON users (lower(username) text_pattern_ops);

CREATE INDEX IF NOT EXISTS idx_users_display_name_lower
  ON users (lower(display_name) text_pattern_ops);
