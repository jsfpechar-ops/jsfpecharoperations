-- +goose Up
-- Brief 1700c, plan docs/plans/ruian-local.md section 3. Goose-only: no SQLite twin.
-- ruian_address holds the public ČÚZK address points (no personal data). It is UNLOGGED:
-- no WAL, so WAL-G skips it, and backup.sh dumps its schema but not its rows. After a
-- crash it is empty and the Go job re-imports it. pg_trgm needs the bootstrap superuser
-- once: owner step in the brief (CREATE EXTENSION IF NOT EXISTS skips the permission
-- check when the extension already exists).
SET LOCAL lock_timeout = '5s';

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE UNLOGGED TABLE IF NOT EXISTS ruian_address (
    code      BIGINT PRIMARY KEY,
    street    TEXT NOT NULL DEFAULT '',
    house_no  TEXT NOT NULL,
    orient_no TEXT NOT NULL DEFAULT '',
    is_evid   BOOLEAN NOT NULL DEFAULT FALSE,
    zip       TEXT NOT NULL DEFAULT '',
    obec      TEXT NOT NULL,
    obec_code INTEGER NOT NULL,
    part      TEXT NOT NULL DEFAULT '',
    district  TEXT NOT NULL DEFAULT '',
    okres     TEXT NOT NULL DEFAULT '',
    search    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ruian_address_search_trgm ON ruian_address USING gin (search gin_trgm_ops);

-- One row: which month is loaded. Logged, so it survives a crash that empties the table.
CREATE TABLE IF NOT EXISTS ruian_import (
    id          SMALLINT PRIMARY KEY CHECK (id = 1),
    data_date   DATE NOT NULL,
    rows        BIGINT NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL
);

-- +goose Down
DROP TABLE IF EXISTS ruian_import;
DROP TABLE IF EXISTS ruian_address;
