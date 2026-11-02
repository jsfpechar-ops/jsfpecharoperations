-- +goose Up
-- Brief 0834: twin of App/app/migrations/0035_apartment_ocr_scan.sql. pg_schema
-- apply runs the SQLite file first, so every statement is IF NOT EXISTS.
ALTER TABLE apartment ADD COLUMN IF NOT EXISTS ocr_scan BIGINT NOT NULL DEFAULT 0;
-- A goose-only database must also record SQLite migration 35, or the
-- schema check reports it as not current.
INSERT INTO schema_migrations (version, name, applied_at)
    VALUES (35, 'apartment_ocr_scan', '2026-11-02T00:00:00+00:00')
    ON CONFLICT (version) DO NOTHING;

-- +goose Down
DELETE FROM schema_migrations WHERE version = 35;
ALTER TABLE apartment DROP COLUMN IF EXISTS ocr_scan;
