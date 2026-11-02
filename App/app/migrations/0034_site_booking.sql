-- Brief 0814: booking site v1 (plan booking-site-v1). One row per guest
-- booking made on /p/<slug>; the reservation row is created only when the
-- payment arrives (0816). guest_name / guest_email: see retention.py (0814).
CREATE TABLE IF NOT EXISTS site_booking (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id             INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    owner_user_id            INTEGER NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    reservation_id           INTEGER REFERENCES reservation(id) ON DELETE SET NULL,
    hold_id                  INTEGER,
    status                   TEXT NOT NULL DEFAULT 'pending',
    date_from                TEXT NOT NULL,
    date_to                  TEXT NOT NULL,
    guests                   INTEGER NOT NULL,
    guest_name               TEXT,
    guest_email              TEXT,
    lang                     TEXT NOT NULL DEFAULT 'cs',
    nights                   INTEGER NOT NULL,
    nightly_czk              INTEGER NOT NULL,
    cleaning_fee_czk         INTEGER NOT NULL DEFAULT 0,
    total_czk                INTEGER NOT NULL,
    refunded_czk             INTEGER NOT NULL DEFAULT 0,
    cancellation_policy      TEXT NOT NULL,
    terms_version            TEXT NOT NULL,
    terms_accepted_at        TEXT,
    stripe_session_id        TEXT UNIQUE,
    stripe_payment_intent_id TEXT,
    cancel_token_hash        TEXT,
    invoice_id               INTEGER REFERENCES invoice(id) ON DELETE SET NULL,
    paid_at                  TEXT,
    cancelled_at             TEXT,
    created_at               TEXT NOT NULL,
    updated_at               TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_site_booking_apartment ON site_booking (apartment_id, date_from);
CREATE INDEX IF NOT EXISTS idx_site_booking_status ON site_booking (status);
