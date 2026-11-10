-- +goose Up
-- Twin of App/app/migrations/0041_claim_fee_mailed.sql (brief 1078). pg_schema
-- apply runs the SQLite file first, so the statements are IF NOT EXISTS.
ALTER TABLE reservation_claim ADD COLUMN IF NOT EXISTS fee_mailed_total BIGINT;
ALTER TABLE reservation_claim ADD COLUMN IF NOT EXISTS fee_mailed_at TEXT;
ALTER TABLE reservation_claim ADD COLUMN IF NOT EXISTS fee_pending_total BIGINT;
ALTER TABLE reservation_claim ADD COLUMN IF NOT EXISTS fee_pending_since TEXT;
INSERT INTO schema_migrations (version, name, applied_at)
    VALUES (41, 'claim_fee_mailed', '2026-11-10T00:00:00+00:00')
    ON CONFLICT (version) DO NOTHING;

-- +goose Down
DELETE FROM schema_migrations WHERE version = 41;
ALTER TABLE reservation_claim DROP COLUMN IF EXISTS fee_pending_since;
ALTER TABLE reservation_claim DROP COLUMN IF EXISTS fee_pending_total;
ALTER TABLE reservation_claim DROP COLUMN IF EXISTS fee_mailed_at;
ALTER TABLE reservation_claim DROP COLUMN IF EXISTS fee_mailed_total;
