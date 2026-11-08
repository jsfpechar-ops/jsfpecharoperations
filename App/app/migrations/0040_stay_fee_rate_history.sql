-- Brief 1027: dated stay-fee rates. Host configuration only, no personal data.
-- A night is priced at the rate with the latest effective_from on or before it.
CREATE TABLE IF NOT EXISTS stay_fee_rate (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id   INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    rate_czk       INTEGER NOT NULL CHECK (rate_czk >= 0),
    effective_from TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    UNIQUE (apartment_id, effective_from)
);
CREATE INDEX IF NOT EXISTS idx_stay_fee_rate_apartment ON stay_fee_rate (apartment_id, effective_from);
INSERT INTO stay_fee_rate (apartment_id, rate_czk, effective_from, created_at)
SELECT id, stay_fee_rate_czk, '2000-01-01', '2026-11-08T00:00:00+00:00'
FROM apartment WHERE stay_fee_rate_czk > 0
ON CONFLICT (apartment_id, effective_from) DO NOTHING;
