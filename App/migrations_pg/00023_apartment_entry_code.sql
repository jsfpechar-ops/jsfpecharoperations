-- +goose Up
-- Up to three extra entry codes per apartment (brief 2032, owner decisions 2026-11-22 D1, D2).
-- Goose-only table: no SQLite twin, no schema_migrations row. Additive. code_enc is Fernet ciphertext, never plaintext.
CREATE TABLE IF NOT EXISTS apartment_entry_code (
    id BIGSERIAL PRIMARY KEY,
    apartment_id BIGINT NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    position INTEGER NOT NULL CHECK (position BETWEEN 1 AND 3),
    code_type TEXT NOT NULL CHECK (code_type IN ('building_entrance', 'gate', 'garage', 'bike_room', 'other')),
    custom_label TEXT,
    code_enc TEXT NOT NULL,
    valid_until TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CONSTRAINT apartment_entry_code_position_key UNIQUE (apartment_id, position),
    CONSTRAINT apartment_entry_code_other_label CHECK (code_type <> 'other' OR COALESCE(BTRIM(custom_label), '') <> ''),
    CONSTRAINT apartment_entry_code_label_len CHECK (custom_label IS NULL OR char_length(custom_label) <= 60)
);

INSERT INTO apartment_entry_code (apartment_id, position, code_type, custom_label, code_enc, valid_until, created_at, updated_at)
SELECT id,
       1,
       CASE WHEN COALESCE(BTRIM(entry_code_label), '') IN ('', 'Building entrance') THEN 'building_entrance' ELSE 'other' END,
       CASE WHEN COALESCE(BTRIM(entry_code_label), '') IN ('', 'Building entrance') THEN NULL ELSE LEFT(BTRIM(entry_code_label), 60) END,
       entry_code_enc,
       NULLIF(entry_code_until, ''),
       to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
       to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
FROM apartment
WHERE entry_code_enc IS NOT NULL
ON CONFLICT (apartment_id, position) DO NOTHING;

-- +goose Down
DROP TABLE IF EXISTS apartment_entry_code;
