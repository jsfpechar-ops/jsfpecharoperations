-- +goose Up
-- Brief 0834: twin of App/app/migrations/0035_apartment_ocr_scan.sql. pg_schema
-- apply runs the SQLite file first, so every statement is IF NOT EXISTS.
ALTER TABLE apartment ADD COLUMN IF NOT EXISTS ocr_scan BIGINT NOT NULL DEFAULT 0;

-- +goose Down
DELETE FROM schema_migrations WHERE version = 35;
ALTER TABLE apartment DROP COLUMN IF EXISTS ocr_scan;
