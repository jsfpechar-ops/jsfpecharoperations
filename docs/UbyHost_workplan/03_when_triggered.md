# When triggered: later items

> Status: this is the original specification. The code is in `series/` and the per-WP notes in `notes/` record every deviation. Where they differ, `series/` and `notes/` win.

Do not implement any item here until the owner says its trigger has fired. The WP13 log report (`App/tools/perf_report.py`) is how most triggers are measured.

| # | Item | Trigger | Effort |
|---|---|---|---|
| L1 | Bigger Lightsail bundle (4 GB, $24) and 4 web workers | Guest p99 over 500 ms or host p99 over 1 s for a week | S (owner step plus `--workers` change) |
| L2 | File blobs to S3 behind a storage interface | Database file over about 2 GB, or before L3 | M |
| L3 | Postgres plus a second app server | Downtime starts costing customers, or lock wait p99 over 50 ms for a week, or any "database is locked" error | L (1 to 2 weeks) |
| L4 | Admin audit log viewer | First real incident or a customer audit request | S |
| L5 | Google Ads API upload instead of the CSV | Manual CSV upload takes more than a few minutes a month | M |
| L6 | Move from Lightsail to EC2 | Only if one of these is needed: automatic scaling, instance IAM roles or VPC networking, reserved pricing, or a machine type no bundle offers | S (snapshot export) |

Not planned at all (owner decisions): Lambda, Turso, in-app billing, feature flags, any analytics script on app or guest pages. PostHog Cloud EU is planned in [posthog-analytics](../plans/posthog-analytics.md) (2026-10-10).

---

## L2: Storage interface and S3 blobs

Background: review 6.6.

- `storage.put(kind, owner_user_id, bytes) -> key`, `storage.get(key)`, `storage.delete(key)`. Backends: local disk (tests, dev) and S3 (`eu-central-1`, private bucket, SSE, versioning).
- Keys `owner_user_id/kind/yyyy/uuid.ext`. The database stores keys, never URLs.
- Access: ownership check through `access.py` first, then stream the file or return a presigned GET valid 60 s.
- Covers: passport photos, `invoice.pdf_blob`, `stay_fee_filing.pdf_enc` and `csv_enc`, `submission.receipt_pdf`. Encrypted blobs stay encrypted with the app's data key before upload.
- Migration: copy, verify checksums, switch reads (dual read during copy), then clear the database columns. Run `VACUUM` afterwards in a maintenance window.
- IAM: extend the server user only to the files bucket prefix.

## L3: Postgres and two app servers

Background: review 7.2.5 and 7.2.6. Preparation is WP18.

- Target: Lightsail managed Postgres in Frankfurt, or RDS / Neon in Frankfurt; decide at the time on price and backups. Not Turso.
- Two app containers behind the Lightsail load balancer; the worker (WP06) runs on one of them only, protected by a Postgres advisory lock instead of the file lock.
- `with db.immediate()` blocks become `BEGIN` plus `SELECT ... FOR UPDATE` or advisory locks. The claim model in `reporting.py` is reviewed by hand line by line (HIGH RISK: never file twice).
- The 6 triggers become PL/pgSQL triggers. `COLLATE NOCASE` becomes a unique index on `lower(username)`.
- Run the full test suite against both engines in CI for the month before the switch.
- Cut-over: maintenance window of 15 to 30 minutes: stop writes, dump, load, verify row counts per table, switch the DSN. Keep the SQLite file read-only for a week as the rollback.
- Litestream is removed after the switch; Postgres backups and point-in-time recovery replace it.

## L4: Audit log viewer

Read-only list under `/admin/audit`: filter by workspace, action, actor, date range; 100 rows per page; no guest identity in the list (ids only). Admin page views are logged.

## L7: Payments with Stripe (owner decision 4 October 2026)

Trigger: the owner sets a price. Stripe Checkout plus Stripe Billing for a per-property monthly subscription; cards, Apple Pay and Google Pay come through Checkout with no extra integration. Server-side webhook (signed) updates a `subscription` row per account; the app stores only the Stripe customer and subscription ids and the status, never card data. A grace period before features lock, and filing is never blocked for a stay that is already due (legal duty of the host). Stripe added to the subprocessor page. Invoices to hosts from Stripe, not from the in-app invoice tool (which is the hosts' own tool for their guests).
