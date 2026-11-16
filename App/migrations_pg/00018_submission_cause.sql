-- +goose Up
-- Brief A1b P1: nullable cause and fault-table key of a transport_error.
-- Goose-only: no SQLite twin (App/app/migrations/ is frozen at 0045). The status
-- check expects these through db.GOOSE_ONLY_COLUMNS.
ALTER TABLE submission ADD COLUMN IF NOT EXISTS cause TEXT;
ALTER TABLE submission ADD COLUMN IF NOT EXISTS error_code TEXT;

-- +goose Down
ALTER TABLE submission DROP COLUMN IF EXISTS error_code;
ALTER TABLE submission DROP COLUMN IF EXISTS cause;
