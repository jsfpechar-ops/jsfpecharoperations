-- WP21: Meta Conversions API outbox on ad_click, and the sign-up source.
ALTER TABLE user_account ADD COLUMN signup_source TEXT;
ALTER TABLE ad_click ADD COLUMN fbc TEXT;
ALTER TABLE ad_click ADD COLUMN event_id TEXT;
ALTER TABLE ad_click ADD COLUMN send_state TEXT;
ALTER TABLE ad_click ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE ad_click ADD COLUMN next_attempt_at TEXT;
ALTER TABLE ad_click ADD COLUMN last_error TEXT;
-- The browser's User-Agent string, captured at sign-up submit only when the
-- Meta box is ticked (Meta requires client_user_agent for website events).
-- Blanked together with fbc, and deleted with the row.
ALTER TABLE ad_click ADD COLUMN client_user_agent TEXT;
CREATE INDEX IF NOT EXISTS idx_ad_click_send ON ad_click (send_state, next_attempt_at);
