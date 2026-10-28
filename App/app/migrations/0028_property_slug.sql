-- Brief 0430: property page slugs — current row + rename history for 301s.
--
-- One page per property at /p/<slug> on the public host. The slug is
-- deterministic (name normalisation + a 4-char hash of the apartment id), so
-- it is recomputed from the row, never random. property_slug holds the live
-- mapping and the publication state; property_slug_history keeps old slugs
-- alive as 301 redirects, pruned with the property by the same cascade.
-- No personal data beyond the property reference and its public name (the
-- address never enters a slug); no retention.py line needed.
CREATE TABLE IF NOT EXISTS property_slug (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id   INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    slug           TEXT NOT NULL UNIQUE,
    published      INTEGER NOT NULL DEFAULT 0,
    published_at   TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    UNIQUE (apartment_id)
);

CREATE TABLE IF NOT EXISTS property_slug_history (
    old_slug      TEXT PRIMARY KEY,
    apartment_id  INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    created_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_property_slug_history_apartment
    ON property_slug_history (apartment_id);
