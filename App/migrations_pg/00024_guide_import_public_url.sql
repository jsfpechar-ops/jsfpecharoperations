-- +goose Up
-- Guide import from a public URL (brief 2034). Source 'url'; count of removed codes (never the values).
ALTER TABLE guide_import DROP CONSTRAINT IF EXISTS guide_import_source_check;
ALTER TABLE guide_import ADD CONSTRAINT guide_import_source_check CHECK (source IN ('booking', 'airbnb', 'url'));
ALTER TABLE guide_item DROP CONSTRAINT IF EXISTS guide_item_source_check;
ALTER TABLE guide_item ADD CONSTRAINT guide_item_source_check CHECK (source IN ('host', 'legacy', 'booking', 'airbnb', 'paste', 'ai', 'guest_question', 'url'));
ALTER TABLE guide_import ADD COLUMN IF NOT EXISTS codes_left_out BIGINT;

-- +goose Down
-- Down cannot restore source constraints: rows with source 'url' would block it.
ALTER TABLE guide_import DROP COLUMN IF EXISTS codes_left_out;