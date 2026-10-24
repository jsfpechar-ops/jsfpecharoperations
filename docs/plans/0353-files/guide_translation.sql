-- Brief 0303: the guest guide in the guest's language (plan: docs/plans/guest-guide.md).
--
-- guide_translation: one row per guide card and guest language, written by
-- guide_translate.fill after a guest opened the guide in that language.
-- source_hash is a hash of the card text the guest reads (title, location,
-- steps, watch out), so a host edit makes the row stale and the next guest
-- view replaces it. steps: one step per line. same = 1 when the guest reads
-- the original (already in that language, or the translation failed the
-- checks). Derived from host copy, no guest data; deleted with the card.
CREATE TABLE IF NOT EXISTS guide_translation (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id      INTEGER NOT NULL REFERENCES guide_item(id) ON DELETE CASCADE,
    lang         TEXT NOT NULL,
    source_hash  TEXT NOT NULL,
    title        TEXT NOT NULL DEFAULT '',
    location     TEXT NOT NULL DEFAULT '',
    steps        TEXT NOT NULL DEFAULT '',
    watch_out    TEXT NOT NULL DEFAULT '',
    same         INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_guide_translation ON guide_translation (item_id, lang);
