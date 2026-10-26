-- Brief 0411: UbyHost's own billing, phase 1 (bank transfer on an invoice, no card gateway).
--
-- billing_account: one row per host account that has started billing. No row
-- means the host predates billing and stays active Standard. buyer_* is the
-- host's invoicing identity (personal data for sole traders); the row is
-- deleted with the workspace.
-- platform_invoice / bank_payment: UbyHost's accounting records, kept 10 years.
-- owner_user_id is set to NULL when the workspace is deleted; snapshot_json keeps
-- the seller, buyer and items exactly as printed. number is UBY-{year}-{0001};
-- vs is year + the 4-digit number (UBY-2026-0042 -> 20260042) so it never repeats.
-- voided marks an invoice a storno cancelled, so its period can be invoiced again.
-- founder_slot: the first hosts' locked price; a deleted workspace keeps its slot used.
-- apartment.ubyport_verified_at: starts the trial clock (set by the trial brief).
CREATE TABLE IF NOT EXISTS billing_account (
    owner_user_id        INTEGER PRIMARY KEY REFERENCES user_account(id),
    status               TEXT NOT NULL DEFAULT 'trial_pending'
                         CHECK (status IN ('trial_pending', 'trialing', 'active', 'overdue', 'canceling', 'paused')),
    plan                 TEXT CHECK (plan IN ('standard', 'max')),
    billing_interval     TEXT CHECK (billing_interval IN ('month', 'year')),
    payment_method       TEXT NOT NULL DEFAULT 'invoice',
    founder              INTEGER NOT NULL DEFAULT 0,
    addon_ttlock         INTEGER NOT NULL DEFAULT 0,
    addon_whitelabel     INTEGER NOT NULL DEFAULT 0,
    apartments_billed    INTEGER NOT NULL DEFAULT 0,
    trial_started_at     TEXT,
    trial_ends_at        TEXT,
    period_start         TEXT,
    period_end           TEXT,
    cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
    pending_change_json  TEXT,
    carry_czk            INTEGER NOT NULL DEFAULT 0,
    buyer_name           TEXT,
    buyer_street         TEXT,
    buyer_city           TEXT,
    buyer_zip            TEXT,
    buyer_ico            TEXT,
    buyer_dic            TEXT,
    buyer_email          TEXT,
    updated_at           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS platform_invoice (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_user_id  INTEGER REFERENCES user_account(id),
    kind           TEXT NOT NULL CHECK (kind IN ('invoice', 'supplementary', 'storno')),
    corrects_id    INTEGER REFERENCES platform_invoice(id),
    seq_year       INTEGER NOT NULL,
    seq_no         INTEGER NOT NULL,
    number         TEXT NOT NULL UNIQUE,
    vs             TEXT NOT NULL UNIQUE,
    issue_date     TEXT NOT NULL,
    due_date       TEXT NOT NULL,
    period_from    TEXT NOT NULL,
    period_to      TEXT NOT NULL,
    total_haler    INTEGER NOT NULL,
    voided         INTEGER NOT NULL DEFAULT 0,
    paid_on        TEXT,
    paid_via       TEXT CHECK (paid_via IN ('bank_auto', 'bank_manual')),
    snapshot_json  TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    UNIQUE (seq_year, seq_no)
);

-- An invoice for a period is never issued twice; a storno'd one (voided) can be reissued.
CREATE UNIQUE INDEX IF NOT EXISTS idx_platform_invoice_period
    ON platform_invoice (owner_user_id, period_from, period_to)
    WHERE kind = 'invoice' AND voided = 0;
CREATE INDEX IF NOT EXISTS idx_platform_invoice_owner ON platform_invoice (owner_user_id);

CREATE TABLE IF NOT EXISTS platform_invoice_sequence (
    year    INTEGER PRIMARY KEY,
    last_no INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS bank_payment (
    bank_tx_id         TEXT PRIMARY KEY,
    received_on        TEXT NOT NULL,
    amount_haler       INTEGER NOT NULL,
    vs                 TEXT,
    counter_account    TEXT,
    message            TEXT,
    matched_invoice_id INTEGER REFERENCES platform_invoice(id),
    status             TEXT NOT NULL CHECK (status IN ('matched', 'unmatched', 'partial', 'overpaid'))
);
CREATE INDEX IF NOT EXISTS idx_bank_payment_vs ON bank_payment (vs);

CREATE TABLE IF NOT EXISTS founder_slot (
    slot          INTEGER PRIMARY KEY CHECK (slot >= 1),
    owner_user_id INTEGER UNIQUE REFERENCES user_account(id),
    claimed_at    TEXT NOT NULL
);

ALTER TABLE apartment ADD COLUMN ubyport_verified_at TEXT;
