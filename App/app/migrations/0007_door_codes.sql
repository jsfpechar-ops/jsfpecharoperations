-- Task 0008: schema for TTLock door codes. Nothing reads these tables yet;
-- the feature stays off until UBYHOST_DOOR_CODES=1.
--
-- apartment: which lock serves the flat and which local hours define check-in
-- and check-out for code validity (the host sets the hours; there is no default).
--
-- lock_account: one row per host and provider (TTLock). Holds encrypted
-- credentials and tokens plus a cached lock list refreshed on demand.
--
-- door_code: one row per reservation; the PIN is encrypted until retention
-- wipes it after the code expires.
--
-- lock_api_usage: shared monthly API call budget counter per provider.
ALTER TABLE apartment ADD COLUMN lock_provider TEXT;
ALTER TABLE apartment ADD COLUMN lock_id TEXT;
ALTER TABLE apartment ADD COLUMN checkin_hour INTEGER;
ALTER TABLE apartment ADD COLUMN checkout_hour INTEGER;

CREATE TABLE IF NOT EXISTS lock_account (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_user_id     INTEGER NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    provider          TEXT NOT NULL DEFAULT 'ttlock',
    username          TEXT NOT NULL,
    password_enc      TEXT,
    access_token_enc  TEXT,
    refresh_token_enc TEXT,
    token_expires_at  TEXT,
    token_version     INTEGER NOT NULL DEFAULT 0,
    status            TEXT NOT NULL DEFAULT 'ok',
    locks_json        TEXT,
    locks_fetched_at  TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    UNIQUE (owner_user_id, provider)
);

CREATE TABLE IF NOT EXISTS door_code (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    reservation_id   INTEGER NOT NULL UNIQUE REFERENCES reservation(id) ON DELETE CASCADE,
    apartment_id     INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    lock_id          TEXT NOT NULL,
    code_kind        TEXT NOT NULL DEFAULT 'random',
    state            TEXT NOT NULL DEFAULT 'pending',
    pin_enc          TEXT,
    provider_code_id TEXT,
    valid_from       TEXT,
    valid_to         TEXT,
    attempts         INTEGER NOT NULL DEFAULT 0,
    next_attempt_at  TEXT,
    claimed_at       TEXT,
    last_error       TEXT,
    notified_at      TEXT,
    issued_at        TEXT,
    revoked_at       TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_door_code_due ON door_code (state, next_attempt_at);

CREATE TABLE IF NOT EXISTS lock_api_usage (
    month    TEXT NOT NULL,
    provider TEXT NOT NULL,
    calls    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (month, provider)
);
