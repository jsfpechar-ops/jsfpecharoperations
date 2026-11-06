-- +goose Up
-- Twin of App/app/migrations/0037_stay_fee_guest_default_rail.sql. pg_schema
-- apply runs the SQLite file first, so the statement is IF NOT EXISTS.
ALTER TABLE apartment ADD COLUMN IF NOT EXISTS stay_fee_guest_default_rail TEXT NOT NULL DEFAULT '';
INSERT INTO schema_migrations (version, name, applied_at)
    VALUES (37, 'stay_fee_guest_default_rail', '2026-11-05T00:00:00+00:00')
    ON CONFLICT (version) DO NOTHING;

-- +goose Down
DELETE FROM schema_migrations WHERE version = 37;
ALTER TABLE apartment DROP COLUMN IF EXISTS stay_fee_guest_default_rail;
