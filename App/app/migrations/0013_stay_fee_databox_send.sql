-- Brief 0240: one row per "Send by data box" hand-off to the ISDS Odesílací brána.
-- No credentials and no message content: only which filing, who pressed it, a
-- one-time token we hand to ISDS, and how it ended. Deleted after 90 days.
CREATE TABLE IF NOT EXISTS stay_fee_databox_send (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    filing_id        INTEGER NOT NULL REFERENCES stay_fee_filing(id) ON DELETE CASCADE,
    apartment_id     INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    user_account_id  INTEGER NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    token            TEXT NOT NULL UNIQUE,
    state            TEXT NOT NULL DEFAULT 'pending',
    created_at       TEXT NOT NULL,
    expires_at       TEXT NOT NULL,
    returned_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_databox_send_user ON stay_fee_databox_send (user_account_id, created_at);
