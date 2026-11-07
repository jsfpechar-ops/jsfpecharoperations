-- +goose Up
-- Indexes for the hot loops on alert, ical_feed and guest (0991), ready for ~1000 properties.
-- Index-only and additive: no SQLite twin (no column is read by Python), the previous image keeps working.
CREATE INDEX IF NOT EXISTS idx_alert_open_apartment ON alert (apartment_id) WHERE resolved_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_alert_open_kind ON alert (kind) WHERE resolved_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_ical_feed_apartment_active ON ical_feed (apartment_id) WHERE active = 1;
CREATE INDEX IF NOT EXISTS idx_guest_submit_state_open ON guest (submit_state) WHERE archived_at IS NULL;

-- +goose Down
DROP INDEX IF EXISTS idx_guest_submit_state_open;
DROP INDEX IF EXISTS idx_ical_feed_apartment_active;
DROP INDEX IF EXISTS idx_alert_open_kind;
DROP INDEX IF EXISTS idx_alert_open_apartment;
