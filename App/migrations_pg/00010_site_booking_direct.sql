-- +goose Up
-- Twin of App/app/migrations/0039_site_booking_direct.sql. pg_schema apply
-- runs the SQLite file first, so the statements are IF NOT EXISTS.
ALTER TABLE site_booking ADD COLUMN IF NOT EXISTS pay_method TEXT NOT NULL DEFAULT 'stripe';
ALTER TABLE site_booking ADD COLUMN IF NOT EXISTS request_expires_at TEXT;
INSERT INTO schema_migrations (version, name, applied_at)
    VALUES (39, 'site_booking_direct', '2026-11-07T00:00:00+00:00')
    ON CONFLICT (version) DO NOTHING;

-- +goose Down
DELETE FROM schema_migrations WHERE version = 39;
ALTER TABLE site_booking DROP COLUMN IF EXISTS request_expires_at;
ALTER TABLE site_booking DROP COLUMN IF EXISTS pay_method;
