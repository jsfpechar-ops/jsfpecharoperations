-- Brief 0996: booking site "request to book". pay_method is 'stripe' (the
-- default, every existing row) or 'direct' (host confirms a manual payment).
-- request_expires_at: end of the 24 h hold of a direct request (UTC, same
-- format as created_at); NULL for Stripe bookings. No personal data.
ALTER TABLE site_booking ADD COLUMN pay_method TEXT NOT NULL DEFAULT 'stripe';
ALTER TABLE site_booking ADD COLUMN request_expires_at TEXT;
