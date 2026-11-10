-- +goose Up
-- Twin of App/app/migrations/0044_lead_reduced_guests.sql (brief 1095).
-- pg_schema apply runs the SQLite file first, so statements are IF NOT EXISTS.
ALTER TABLE reservation ADD COLUMN IF NOT EXISTS lead_reduced_guests INTEGER;
ALTER TABLE reservation ADD COLUMN IF NOT EXISTS lead_reduced_from INTEGER;
ALTER TABLE reservation ADD COLUMN IF NOT EXISTS lead_reduced_at TEXT;
ALTER TABLE reservation ADD COLUMN IF NOT EXISTS lead_reduced_changes INTEGER NOT NULL DEFAULT 0;
INSERT INTO schema_migrations (version, name, applied_at)
    VALUES (44, 'lead_reduced_guests', '2026-11-10T00:00:00+00:00')
    ON CONFLICT (version) DO NOTHING;

-- +goose Down
DELETE FROM schema_migrations WHERE version = 44;
ALTER TABLE reservation DROP COLUMN IF EXISTS lead_reduced_guests;
ALTER TABLE reservation DROP COLUMN IF EXISTS lead_reduced_from;
ALTER TABLE reservation DROP COLUMN IF EXISTS lead_reduced_at;
ALTER TABLE reservation DROP COLUMN IF EXISTS lead_reduced_changes;
