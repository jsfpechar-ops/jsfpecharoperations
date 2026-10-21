-- Brief 0225: urgent alerts on the host's phone (Web Push).
--
-- push_subscription: one row per browser that turned alerts on. The endpoint is
-- the push service address the browser gave; with the two keys it is enough to
-- message that device, so all three are stored encrypted. endpoint_hash
-- (sha256) finds a row without decrypting. device is a coarse family name
-- ("iPhone"); lang is the interface language the alerts are written in.
CREATE TABLE IF NOT EXISTS push_subscription (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_account_id  INTEGER NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    endpoint_hash    TEXT NOT NULL UNIQUE,
    endpoint_enc     TEXT NOT NULL,
    p256dh_enc       TEXT NOT NULL,
    auth_enc         TEXT NOT NULL,
    lang             TEXT NOT NULL DEFAULT 'en',
    device           TEXT NOT NULL DEFAULT '',
    failures         INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL,
    last_seen_at     TEXT NOT NULL,
    last_sent_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_push_subscription_user ON push_subscription (user_account_id);

-- push_outbox: one row per alert per device. params holds a property name and
-- dates for the text, never a guest's name. Rows are deleted 30 days after they
-- were queued (retention.py). The idempotency key stops a retried event from
-- buzzing the same phone twice.
CREATE TABLE IF NOT EXISTS push_outbox (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    idempotency_key  TEXT NOT NULL UNIQUE,
    subscription_id  INTEGER NOT NULL REFERENCES push_subscription(id) ON DELETE CASCADE,
    user_account_id  INTEGER NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    kind             TEXT NOT NULL,
    params           TEXT NOT NULL DEFAULT '{}',
    url              TEXT NOT NULL DEFAULT '/',
    state            TEXT NOT NULL DEFAULT 'queued' CHECK (state IN ('queued', 'sent', 'failed')),
    attempts         INTEGER NOT NULL DEFAULT 0,
    next_attempt_at  TEXT NOT NULL,
    last_status      INTEGER,
    created_at       TEXT NOT NULL,
    sent_at          TEXT
);
CREATE INDEX IF NOT EXISTS idx_push_outbox_due ON push_outbox (state, next_attempt_at);
CREATE INDEX IF NOT EXISTS idx_push_outbox_device ON push_outbox (subscription_id, state, sent_at);
