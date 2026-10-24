-- Brief 0291: the guest guide (plan: docs/plans/guest-guide.md).
--
-- guide_item: one thing a guest may need to know or do at a property ("Turn
-- on the heating"). The host writes it; guests read it on the guide page and
-- the guest bot answers from it. kind names a built-in card ('checkin',
-- 'wifi', ...) or 'custom'; a property has at most one row per built-in kind.
-- visibility: 'everyone' (QR page), 'booked' (stay link during the stay only),
-- 'host' (never shown to guests). state: 'missing' (empty card), 'check'
-- (drafted for the host, not confirmed: never shown to guests), 'done',
-- 'skipped' (does not apply, e.g. no air conditioning). Host-written content,
-- no guest personal data.
CREATE TABLE IF NOT EXISTS guide_item (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id  INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    topic         TEXT NOT NULL,
    kind          TEXT NOT NULL DEFAULT 'custom',
    title         TEXT NOT NULL DEFAULT '',
    location      TEXT NOT NULL DEFAULT '',
    steps         TEXT NOT NULL DEFAULT '',
    watch_out     TEXT NOT NULL DEFAULT '',
    video_url     TEXT NOT NULL DEFAULT '',
    visibility    TEXT NOT NULL DEFAULT 'everyone' CHECK (visibility IN ('everyone', 'booked', 'host')),
    state         TEXT NOT NULL DEFAULT 'missing' CHECK (state IN ('missing', 'check', 'done', 'skipped')),
    source        TEXT NOT NULL DEFAULT 'host' CHECK (source IN ('host', 'legacy', 'booking', 'airbnb', 'paste', 'ai', 'guest_question')),
    sort_order    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_guide_item_apartment ON guide_item (apartment_id, topic, sort_order);
CREATE UNIQUE INDEX IF NOT EXISTS uq_guide_item_kind ON guide_item (apartment_id, kind) WHERE kind != 'custom';

-- guide_photo: photos on a guide item, stored under DATA_DIR/guide_photos by
-- brief 0343. Kept while the item exists; the files go with the item.
CREATE TABLE IF NOT EXISTS guide_photo (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id       INTEGER NOT NULL REFERENCES guide_item(id) ON DELETE CASCADE,
    file_name     TEXT NOT NULL UNIQUE,
    sort_order    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_guide_photo_item ON guide_photo (item_id, sort_order);
