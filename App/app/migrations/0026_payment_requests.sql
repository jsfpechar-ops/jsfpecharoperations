-- Brief 0425: direct payment requests and the host's Stripe connected-account mirror.
--
-- ubyhost never receives or holds funds. Rail 'card' = Stripe payment link on
-- the host's own connected account (host is merchant of record, application fee
-- 0). Rail 'qr' = SPAYD QR the guest pays into the host's own bank account;
-- ubyhost is only the technology provider (plan ubyhost-complete-stripe,
-- Appendix D item 11b). stripe_account mirrors non-sensitive status only: no
-- API keys, no secrets, no identity documents (those live only in Stripe).
-- payment_request.guest_email and guest_note are personal data (retention.py).
CREATE TABLE IF NOT EXISTS stripe_account (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_user_id         INTEGER NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    stripe_account_id     TEXT NOT NULL UNIQUE,
    mode                  TEXT NOT NULL CHECK (mode IN ('test', 'live')),
    onboarding_state      TEXT NOT NULL DEFAULT 'pending'
                          CHECK (onboarding_state IN ('pending', 'action_required', 'complete', 'rejected', 'disabled')),
    charges_enabled       INTEGER NOT NULL DEFAULT 0,
    payouts_enabled       INTEGER NOT NULL DEFAULT 0,
    requirements_json     TEXT,
    payout_delay_days     INTEGER NOT NULL DEFAULT 7 CHECK (payout_delay_days BETWEEN 0 AND 14),
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL,
    UNIQUE (owner_user_id, mode)
);

-- One row per "ask a guest for money". VS (variable symbol) is unique per
-- request so bank matching never collides across hosts. invoice_id links a
-- paid request to the faktura the invoice engine created.
CREATE TABLE IF NOT EXISTS payment_request (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_user_id         INTEGER NOT NULL REFERENCES user_account(id) ON DELETE CASCADE,
    apartment_id          INTEGER REFERENCES apartment(id) ON DELETE SET NULL,
    reservation_id        INTEGER REFERENCES reservation(id) ON DELETE SET NULL,
    reason                TEXT NOT NULL CHECK (reason IN ('repair', 'extra_guest', 'late_checkout', 'cleaning', 'damage', 'custom')),
    amount_czk            INTEGER NOT NULL CHECK (amount_czk >= 1),
    currency              TEXT NOT NULL DEFAULT 'CZK' CHECK (currency = 'CZK'),
    guest_email           TEXT,
    guest_note            TEXT,
    rail                  TEXT NOT NULL CHECK (rail IN ('card', 'qr')),
    status                TEXT NOT NULL DEFAULT 'draft'
                          CHECK (status IN ('draft', 'sent', 'awaiting_payment', 'paid', 'expired', 'cancelled')),
    variable_symbol       TEXT UNIQUE,
    stripe_payment_link_id TEXT,
    stripe_session_id     TEXT,
    stripe_payment_intent_id TEXT,
    invoice_id            INTEGER REFERENCES invoice(id) ON DELETE SET NULL,
    paid_at               TEXT,
    expires_at            TEXT NOT NULL,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_payment_request_owner ON payment_request(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_payment_request_status ON payment_request(status);
