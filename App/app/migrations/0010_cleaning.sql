-- Cleaning schedules are independent of booking availability and guest codes.
CREATE TABLE cleaning_event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    source_reservation_id INTEGER UNIQUE REFERENCES reservation(id) ON DELETE CASCADE,
    source_date TEXT,
    scheduled_date TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    notes_enc TEXT,
    overridden INTEGER NOT NULL DEFAULT 0,
    state TEXT NOT NULL DEFAULT 'scheduled'
        CHECK (state IN ('scheduled', 'dismissed', 'source_cancelled')),
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_cleaning_schedule ON cleaning_event(apartment_id, scheduled_date, state);
CREATE TABLE cleaning_code (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    source TEXT NOT NULL CHECK (source IN ('manual', 'ttlock')),
    pin_enc TEXT,
    lock_account_id INTEGER REFERENCES lock_account(id) ON DELETE SET NULL,
    lock_id TEXT,
    provider_code_id TEXT,
    operation_ref TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT,
    claimed_at TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_cleaning_code_due ON cleaning_code(state, next_attempt_at);
CREATE TABLE cleaning_property (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id INTEGER NOT NULL UNIQUE REFERENCES apartment(id) ON DELETE CASCADE,
    instructions TEXT NOT NULL DEFAULT '',
    checkout_time TEXT,
    checkin_time TEXT,
    code_id INTEGER REFERENCES cleaning_code(id) ON DELETE SET NULL,
    pending_code_id INTEGER REFERENCES cleaning_code(id) ON DELETE SET NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE cleaning_share (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_user_id INTEGER REFERENCES user_account(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE cleaning_share_property (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    share_id INTEGER NOT NULL REFERENCES cleaning_share(id) ON DELETE CASCADE,
    apartment_id INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    UNIQUE (share_id, apartment_id)
);
