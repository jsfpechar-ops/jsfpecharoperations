-- 0440: the /admin console queue reads unpaid overdue invoices daily.
-- A covering index on the queue's filter columns keeps the daily read a seek
-- instead of a scan as the invoice table grows. Postgres-portable syntax only.
CREATE INDEX IF NOT EXISTS idx_platform_invoice_unpaid_due
    ON platform_invoice (due_date, paid_on);
