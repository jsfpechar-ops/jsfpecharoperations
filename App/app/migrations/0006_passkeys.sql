-- Task 0004: passkeys (WebAuthn) as an optional, faster way to log in, and the
-- one-time "secure your account" prompt.
--
-- A passkey row holds the public half of a key pair that lives on the host's
-- device or in their password manager. Nothing here logs anyone in: a copy of
-- the database has no private key. credential_id and public_key are
-- base64url text so the table moves to Postgres unchanged.
--
-- sign_count is the authenticator's counter. Most synced passkeys always
-- report 0; a key that once counted and then goes backwards was probably
-- cloned, and the login is refused (passkeys.py).
CREATE TABLE IF NOT EXISTS passkey (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_account_id  INTEGER NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    credential_id    TEXT NOT NULL UNIQUE,
    public_key       TEXT NOT NULL,
    sign_count       INTEGER NOT NULL DEFAULT 0,
    transports       TEXT,
    name             TEXT NOT NULL,
    backed_up        INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL,
    last_used_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_passkey_user ON passkey (user_account_id);

-- One row per WebAuthn ceremony the server started. Only the SHA-256 of the
-- challenge is kept; a row is spent once and dies after 5 minutes, and the
-- retention job deletes it a day later. purpose: 'register' (bound to the
-- account adding a passkey) or 'login' (no account yet).
CREATE TABLE IF NOT EXISTS webauthn_challenge (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    challenge_hash   TEXT NOT NULL UNIQUE,
    purpose          TEXT NOT NULL,
    user_account_id  INTEGER REFERENCES user_account(id) ON DELETE CASCADE,
    created_at       TEXT NOT NULL,
    expires_at       TEXT NOT NULL,
    used_at          TEXT
);
CREATE INDEX IF NOT EXISTS idx_webauthn_challenge_expires ON webauthn_challenge (expires_at);

-- The random, opaque user handle a passkey stores for this account (never the
-- e-mail or the database id), base64url.
ALTER TABLE user_account ADD COLUMN webauthn_user_handle TEXT;
-- When the one-time "secure your account" prompt was shown. NULL: not yet.
ALTER TABLE user_account ADD COLUMN two_factor_prompted_at TEXT;
