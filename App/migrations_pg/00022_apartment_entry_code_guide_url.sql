-- +goose Up
-- Building entry code and external guide link per apartment (brief 1661, plan entry-code-external-guide).
-- Goose-only: no SQLite twin, no schema_migrations row. Additive: the previous image ignores the columns.
-- entry_code_enc is Fernet ciphertext (never plaintext); entry_code_until is an ISO date or NULL.
ALTER TABLE apartment ADD COLUMN IF NOT EXISTS entry_code_enc TEXT;
ALTER TABLE apartment ADD COLUMN IF NOT EXISTS entry_code_label TEXT;
ALTER TABLE apartment ADD COLUMN IF NOT EXISTS entry_code_until TEXT;
ALTER TABLE apartment ADD COLUMN IF NOT EXISTS guide_external_url TEXT;

-- +goose Down
ALTER TABLE apartment DROP COLUMN IF EXISTS guide_external_url;
ALTER TABLE apartment DROP COLUMN IF EXISTS entry_code_until;
ALTER TABLE apartment DROP COLUMN IF EXISTS entry_code_label;
ALTER TABLE apartment DROP COLUMN IF EXISTS entry_code_enc;