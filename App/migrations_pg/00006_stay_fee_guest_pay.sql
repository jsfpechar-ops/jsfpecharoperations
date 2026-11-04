-- +goose Up
-- Brief 0897: twin of App/app/migrations/0036_stay_fee_guest_pay.sql. pg_schema
-- apply runs the SQLite file first, so every statement is IF NOT EXISTS.
ALTER TABLE apartment ADD COLUMN IF NOT EXISTS stay_fee_collect BIGINT NOT NULL DEFAULT 0;
ALTER TABLE apartment ADD COLUMN IF NOT EXISTS stay_fee_guest_rails TEXT NOT NULL DEFAULT '';
ALTER TABLE apartment ADD COLUMN IF NOT EXISTS stay_fee_guest_revolut_link TEXT;
ALTER TABLE apartment ADD COLUMN IF NOT EXISTS stay_fee_guest_cash_note TEXT;
-- A goose-only database must also record SQLite migration 36, or the
-- schema check reports it as not current.
INSERT INTO schema_migrations (version, name, applied_at)
    VALUES (36, 'stay_fee_guest_pay', '2026-11-04T00:00:00+00:00')
    ON CONFLICT (version) DO NOTHING;

-- +goose Down
DELETE FROM schema_migrations WHERE version = 36;
ALTER TABLE apartment DROP COLUMN IF EXISTS stay_fee_guest_cash_note;
ALTER TABLE apartment DROP COLUMN IF EXISTS stay_fee_guest_revolut_link;
ALTER TABLE apartment DROP COLUMN IF EXISTS stay_fee_guest_rails;
ALTER TABLE apartment DROP COLUMN IF EXISTS stay_fee_collect;
