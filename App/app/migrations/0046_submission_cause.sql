-- Brief A1b P1: the cause and the fault-table key of a transport_error are stored
-- as fields, so the operator page and the digest need no message-text matching.
-- Nullable, no personal data, so no retention.py line.
ALTER TABLE submission ADD COLUMN cause TEXT;
ALTER TABLE submission ADD COLUMN error_code TEXT;
