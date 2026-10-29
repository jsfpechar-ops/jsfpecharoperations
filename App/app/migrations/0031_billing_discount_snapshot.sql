-- 0443/0444: the operator's discount and the monthly snapshot for analytics.
-- discount_reason is business info (why the operator lowered a price); it follows
-- billing_account's retention. billing_month_snapshot is derived data: it can be
-- rebuilt from billing_account history + audit log, and is kept as long as the
-- invoices it explains (10 years).
CREATE TABLE IF NOT EXISTS billing_month_snapshot (
    owner_user_id  INTEGER,
    month          TEXT NOT NULL,
    status         TEXT NOT NULL,
    plan           TEXT,
    billing_interval TEXT,
    apartments     INTEGER NOT NULL DEFAULT 0,
    addon_ttlock   INTEGER NOT NULL DEFAULT 0,
    addon_whitelabel INTEGER NOT NULL DEFAULT 0,
    founder        INTEGER NOT NULL DEFAULT 0,
    discount_percent INTEGER NOT NULL DEFAULT 0,
    list_czk       INTEGER NOT NULL DEFAULT 0,
    net_czk        INTEGER NOT NULL DEFAULT 0,
    monthly_czk    INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL,
    PRIMARY KEY (owner_user_id, month)
);
CREATE INDEX IF NOT EXISTS idx_billing_snapshot_month ON billing_month_snapshot (month);

-- 0443: the operator's price reduction, applied by billing.quote so the host's
-- plan page, the next invoice and the cockpit all use the same number.
ALTER TABLE billing_account ADD COLUMN discount_percent INTEGER NOT NULL DEFAULT 0
    CHECK (discount_percent >= 0 AND discount_percent <= 100);
ALTER TABLE billing_account ADD COLUMN discount_reason TEXT;
