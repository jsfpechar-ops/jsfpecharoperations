-- Readable guest links (WP19): "/l/{slug}" beside the permanent
-- "/l/{permalink_token}". One current slug per apartment; renamed slugs keep
-- their row with is_current = 0 and redirect to the current one.
CREATE TABLE IF NOT EXISTS apartment_slug (
    slug          TEXT PRIMARY KEY,
    apartment_id  INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    is_current    INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_slug_current
    ON apartment_slug (apartment_id) WHERE is_current = 1;
