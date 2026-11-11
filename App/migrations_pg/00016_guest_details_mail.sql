-- +goose Up
-- Twin of App/app/migrations/0045_guest_details_mail.sql (brief 1120).
-- pg_schema apply runs the SQLite file first, so statements are IF NOT EXISTS.
ALTER TABLE user_account ADD COLUMN IF NOT EXISTS guest_details_mail BIGINT NOT NULL DEFAULT 1;
INSERT INTO schema_migrations (version, name, applied_at)
    VALUES (45, 'guest_details_mail', '2026-11-11T00:00:00+00:00')
    ON CONFLICT (version) DO NOTHING;

-- +goose Down
DELETE FROM schema_migrations WHERE version = 45;
ALTER TABLE user_account DROP COLUMN IF EXISTS guest_details_mail;
