-- +goose Up
-- Twin of App/app/migrations/0043_guest_signed_for.sql (brief 1089).
-- pg_schema apply runs the SQLite file first, so statements are IF NOT EXISTS.
ALTER TABLE guest ADD COLUMN IF NOT EXISTS signed_for_guest_id BIGINT;
ALTER TABLE guest ADD COLUMN IF NOT EXISTS signed_for_role TEXT;
ALTER TABLE guest ADD COLUMN IF NOT EXISTS signed_for_at TEXT;
ALTER TABLE guest ADD COLUMN IF NOT EXISTS signed_for_wording TEXT;
INSERT INTO schema_migrations (version, name, applied_at)
    VALUES (43, 'guest_signed_for', '2026-11-10T00:00:00+00:00')
    ON CONFLICT (version) DO NOTHING;

-- +goose Down
DELETE FROM schema_migrations WHERE version = 43;
ALTER TABLE guest DROP COLUMN IF EXISTS signed_for_guest_id;
ALTER TABLE guest DROP COLUMN IF EXISTS signed_for_role;
ALTER TABLE guest DROP COLUMN IF EXISTS signed_for_at;
ALTER TABLE guest DROP COLUMN IF EXISTS signed_for_wording;
