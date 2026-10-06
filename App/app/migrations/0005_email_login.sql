-- Task 0003: log in with a link sent by e-mail; passwords are gone.
--
-- One row per link that was sent. Only the SHA-256 of the link's secret is
-- stored, so a copy of the database (or of a backup) logs nobody in. A row is
-- spent once (used_at), dies at expires_at, and is deleted a day later by the
-- retention job (retention.py, login_tokens).
--
-- purpose: 'login' (from the login page), 'invite' (an account an admin
-- created), 'email_change' (confirms a new login address; email is the new
-- address). For the other two, email is the address the link went to, so a
-- link stops working once the account's login e-mail changes.
CREATE TABLE IF NOT EXISTS login_token (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash       TEXT NOT NULL UNIQUE,
    user_account_id  INTEGER NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    purpose          TEXT NOT NULL,
    email            TEXT NOT NULL,
    remember         INTEGER NOT NULL DEFAULT 0,
    next_path        TEXT,
    created_at       TEXT NOT NULL,
    expires_at       TEXT NOT NULL,
    used_at          TEXT
);
CREATE INDEX IF NOT EXISTS idx_login_token_user ON login_token (user_account_id, purpose);
CREATE INDEX IF NOT EXISTS idx_login_token_expires ON login_token (expires_at);

-- Hard cutover: no account logs in with a password any more, so no password
-- hash is kept. The column stays (NOT NULL in the frozen baseline) and holds ''.
UPDATE user_account SET password_hash = '', must_change_password = 0;
