-- Brief 0297: Booking.com and Airbnb listing imports (plan: docs/plans/guest-guide.md).
--
-- guide_import: one request by the host to fetch their own public listing
-- through Apify. url is the rebuilt, allowlisted link (never the pasted text).
-- status: 'queued' (waiting for the worker), 'running', 'done' (raw_json holds
-- the trimmed result for brief 0298), 'failed' (error holds a short code, no
-- listing text), 'used' (0298 drafted cards; raw_json is NULL), 'expired'
-- (raw_json removed by retention after 7 days). Failed rows go after 60 days;
-- the others stay, without text, as the record of the one import per listing.
-- Listing text only, no guest data.
CREATE TABLE IF NOT EXISTS guide_import (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id  INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    source        TEXT NOT NULL CHECK (source IN ('booking', 'airbnb')),
    url           TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'done', 'failed', 'used', 'expired')),
    error         TEXT,
    raw_json      TEXT,
    created_at    TEXT NOT NULL,
    started_at    TEXT,
    finished_at   TEXT,
    used_at       TEXT
);
CREATE INDEX IF NOT EXISTS idx_guide_import_apartment ON guide_import (apartment_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_guide_import_status ON guide_import (status, id);
