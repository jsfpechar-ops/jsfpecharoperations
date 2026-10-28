-- Brief 0434: property-page booking widget (plan property-pages E, payments P2.1).
--
-- A 15-minute checkout hold excludes the dates at DB level while the guest is
-- paying; the sweep releases what expires. The page's nightly price is the
-- host's own field (the widget cannot price a property that has none).
-- No personal data beyond the guest e-mail already covered by
-- payment_request.guest_email (retention: 0425).
CREATE TABLE IF NOT EXISTS booking_hold (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id   INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    date_from      TEXT NOT NULL,
    date_to        TEXT NOT NULL,
    expires_at     TEXT NOT NULL,
    created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_booking_hold_apartment ON booking_hold (apartment_id, date_from);
CREATE INDEX IF NOT EXISTS idx_booking_hold_expires ON booking_hold (expires_at);

ALTER TABLE property_page ADD COLUMN nightly_price_czk INTEGER;
