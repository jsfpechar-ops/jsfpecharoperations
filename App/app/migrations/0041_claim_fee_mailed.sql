-- Brief 1078: the stay-fee total last mailed to the lead guest and a pending changed total.
-- An amount and timestamps, no personal data; the columns go with the claim row.
ALTER TABLE reservation_claim ADD COLUMN fee_mailed_total INTEGER;
ALTER TABLE reservation_claim ADD COLUMN fee_mailed_at TEXT;
ALTER TABLE reservation_claim ADD COLUMN fee_pending_total INTEGER;
ALTER TABLE reservation_claim ADD COLUMN fee_pending_since TEXT;
