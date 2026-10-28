-- Brief 0431: property page content, scrape-prefilled (plan property-pages).
--
-- The host's own OTA listing content, stored verbatim (after the 0347 trim
-- caps) for the public /p/<slug> page: no AI transform, nothing generated.
-- Re-imports fill only empty columns, never host edits. The publish flag and
-- timestamp live here; the slug itself is property_slug (0028). Content is
-- the host's own listing text and photo files — no personal data, no
-- retention.py line beyond the content comment already in 0016 (guide_import
-- raw_json purge applies to the source rows, not to these confirmed fields).
CREATE TABLE IF NOT EXISTS property_page (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id   INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    description    TEXT,
    photos_json    TEXT,
    amenities_json TEXT,
    checkin_text   TEXT,
    checkout_text  TEXT,
    published      INTEGER NOT NULL DEFAULT 0,
    published_at   TEXT,
    hide_from_search INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    UNIQUE (apartment_id)
);
