-- WP20: self sign-up and its Google Ads attribution.
-- The setup-tips opt-out columns (onboarding_emails_opt_out, _at) are not
-- here: WP12 added them to the baseline, and the sign-up box writes those.
ALTER TABLE user_account ADD COLUMN email TEXT;
ALTER TABLE user_account ADD COLUMN email_verified_at TEXT;
ALTER TABLE user_account ADD COLUMN signup_at TEXT;
ALTER TABLE user_account ADD COLUMN signup_verify_nonce TEXT;
ALTER TABLE user_account ADD COLUMN signup_utm_source TEXT;
ALTER TABLE user_account ADD COLUMN signup_utm_medium TEXT;
ALTER TABLE user_account ADD COLUMN signup_utm_campaign TEXT;

-- WP20: one account per sign-up e-mail. NULLs (admin-created accounts) do not
-- collide, in SQLite or in Postgres.
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_account_email ON user_account (email);

-- WP20: the exact wording of every consent box a visitor was shown, one row per
-- version and language, so each recorded consent points at what was displayed.
CREATE TABLE IF NOT EXISTS consent_texts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    version      TEXT NOT NULL UNIQUE,
    purpose      TEXT NOT NULL,
    lang         TEXT NOT NULL,
    text         TEXT NOT NULL,
    text_sha256  TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

-- WP20: an ad click identifier kept with consent, one row per account and ad
-- platform. The identifiers are blanked on schedule (ids_deleted_at); the row
-- itself stays as the record of the consent.
CREATE TABLE IF NOT EXISTS ad_click (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_account_id  INTEGER NOT NULL REFERENCES user_account(id),
    platform         TEXT NOT NULL,
    gclid            TEXT,
    gbraid           TEXT,
    wbraid           TEXT,
    clicked_at       TEXT NOT NULL,
    consent_text_id  INTEGER NOT NULL REFERENCES consent_texts(id),
    consented_at     TEXT NOT NULL,
    withdrawn_at     TEXT,
    uploaded_at      TEXT,
    ids_deleted_at   TEXT,
    created_at       TEXT NOT NULL,
    UNIQUE (user_account_id, platform)
);
CREATE INDEX IF NOT EXISTS idx_ad_click_platform ON ad_click (platform, uploaded_at);
