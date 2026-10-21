ALTER TABLE user_account ADD COLUMN stay_fee_emails_opt_out INTEGER NOT NULL DEFAULT 0;
ALTER TABLE user_account ADD COLUMN stay_fee_emails_opt_out_at TEXT;
