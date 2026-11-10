-- Brief 1082 (S5, decision 7b): the server draft of an unfinished guest form.
-- Personal data, encrypted in fields_enc. Deleted when the form is sent, else
-- 7 days after updated_at or the day after check-out (guest_draft.purge).
CREATE TABLE IF NOT EXISTS guest_form_draft (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    reservation_id   INTEGER NOT NULL REFERENCES reservation(id) ON DELETE CASCADE,
    device_key_hash  TEXT NOT NULL,
    claim_generation INTEGER NOT NULL DEFAULT 0,
    owned_count      INTEGER NOT NULL DEFAULT 0,
    fields_enc       TEXT NOT NULL,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    UNIQUE (reservation_id, device_key_hash)
);
CREATE INDEX IF NOT EXISTS idx_guest_form_draft_updated ON guest_form_draft (updated_at);
