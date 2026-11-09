-- +goose Up
-- Twin of App/app/migrations/0038_property_page_house_rules.sql. pg_schema
-- apply runs the SQLite file first, so the statement is IF NOT EXISTS.
ALTER TABLE property_page ADD COLUMN IF NOT EXISTS house_rules TEXT;
INSERT INTO schema_migrations (version, name, applied_at)
    VALUES (38, 'property_page_house_rules', '2026-11-07T00:00:00+00:00')
    ON CONFLICT (version) DO NOTHING;

-- +goose Down
DELETE FROM schema_migrations WHERE version = 38;
ALTER TABLE property_page DROP COLUMN IF EXISTS house_rules;
