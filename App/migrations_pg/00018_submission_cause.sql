-- +goose Up
-- Twin of App/app/migrations/0046_submission_cause.sql (brief A1b P1).
-- pg_schema apply runs the SQLite file first, so statements are IF NOT EXISTS.
ALTER TABLE submission ADD COLUMN IF NOT EXISTS cause TEXT;
ALTER TABLE submission ADD COLUMN IF NOT EXISTS error_code TEXT;
INSERT INTO schema_migrations (version, name, applied_at)
    VALUES (46, 'submission_cause', '2026-11-16T00:00:00+00:00')
    ON CONFLICT (version) DO NOTHING;

-- +goose Down
DELETE FROM schema_migrations WHERE version = 46;
ALTER TABLE submission DROP COLUMN IF EXISTS error_code;
ALTER TABLE submission DROP COLUMN IF EXISTS cause;
