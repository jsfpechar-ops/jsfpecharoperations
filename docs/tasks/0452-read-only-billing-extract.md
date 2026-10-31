# 0452: Read-only legacy billing analytics extract

Status: review
Depends on: none | Base commit: verify at execution | Branch: task/0452-read-only-billing-extract
Executor: Luna (owner requested) | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add a read-only, transaction-consistent export of the current legacy quote portfolio and bounded non-void invoice totals. Publish one complete JSON file atomically so a failure cannot leave mixed generations or replace the last successful output.

## 2. Context

Verified source anchors and exact constraints:

- `App/app/billing_analytics.py:38-82`: `portfolio()` selects user name/email/username although its quote math does not use them. It includes plan-bearing accounts; only active, overdue, and canceling add to its MRR/ARR. It adds carry to quote net. Monthly plans use net and net×12; annual plans use per-account Python `round(net / 12)` and net. This is a legacy whole-Kč quote output, not reconciled financial MRR. Do not call `portfolio()` from the export.
- `App/app/billing.py:66-104`: `quote()` input contract is apartments, plan, interval, add-on flags, founder, discount percent; it returns whole-Kč list/discount/net. The code does not settle VAT treatment.
- `App/app/migrations/0023_billing.sql:14-40,42-68`: exact account and invoice fields. Invoices contain `kind`, `corrects_id`, integer `total_haler`, `voided`, and `paid_on`; preserve existing `voided = 0` source semantics and do not invent kind filters.
- `App/app/billing_analytics.py:86-101,319-332`: current “collected” aggregation sums the whole invoice total by `paid_on`; this is invoice totals marked paid, not cash received or allocations. Report exact `total_haler`, no truncation or FX.
- `App/app/migrations/0031_billing_discount_snapshot.sql:1-23`: monthly snapshot is derived; it is not needed for this export.
- `App/app/scheduler.py:411-420`: daily snapshot job calls `write_month_snapshot`; grep also found `routes/admin_customers.py:149,168,249`. Export must call none of these paths.
- `App/app/db.py:666-712,819-900`: imports alone do not initialize DB. However current `_open()` chmods DB_PATH and runs `PRAGMA journal_mode=WAL` and `secure_delete=ON`, so `db.cursor()` is not guaranteed strictly side-effect-free. Add a narrow read-only cursor helper inside `db.py`; do not use `_open()`, `db.init_db()`, or raw SQL in the script. `db.readonly_cursor()` opens SQLite with URI `mode=ro`, executes `BEGIN`, and holds one cursor/transaction across all reads. SQLite’s snapshot is pinned on the first SELECT; this yields one consistent view for subsequent SELECTs. In WAL mode SQLite may create/refresh the `-shm` coordination sidecar; main database bytes, permissions, and persistent journal mode must remain unchanged.
- Script convention verified in `App/scripts/list_accounts_without_email.py`: add App root to `sys.path` before `from app import ...`. Its `db.init_db()` call is explicitly unsuitable here; the new script must omit it. `App/app/__init__.py` only defines `__version__`; importing app modules does not initialize DB.
- `App/tests/conftest.py:1-35` gives an isolated temp DB via `UBYHOST_DB`; existing `test_billing_analytics.py:19-47` uses `db.init_db()` to prepare fixture data. New tests must monkeypatch `config.DB_PATH` to `tmp_path` before setup and never point at production.
- Test map: `docs/context/test-map.md:11-12` maps billing to `test_billing_*.py`, DB helper to `test_db_*.py`.

### Output schema

Publish exactly one UTF-8 JSON document at an explicitly supplied `--output` path:

```json
{
  "schema_version": 1,
  "source_snapshot_at_utc": "2026-10-30T12:00:00+00:00",
  "as_of_date_prague": "2026-10-30",
  "generated_at_utc": "2026-10-30T12:00:01+00:00",
  "range": {"from_month": "2026-09", "through_month": "2026-10"},
  "definitions": {
    "portfolio": "Legacy quote portfolio; whole-Kc amounts from billing.quote plus carry; not VAT-reconciled MRR.",
    "invoice_amount_currency": "CZK per source billing contract; source table has no currency column; no FX or general multi-currency support.",
    "paid_on": "Non-void invoice totals marked paid by paid_on; not cash collections or payment allocations."
  },
  "portfolio_quote": [
    {"status":"active","plan_account_count":1,"legacy_quote_monthly_czk":149,"legacy_quote_annual_czk":1788}
  ],
  "invoice_month_totals": [
    {"month":"2026-10","basis":"issue_date","currency":"CZK","nonvoid_invoice_count":2,"total_haler":29800},
    {"month":"2026-10","basis":"paid_on","currency":"CZK","nonvoid_invoice_count":1,"total_haler":14900}
  ]
}
```

The example values are illustrative only. `portfolio_quote` contains one row per status present among plan-bearing accounts. Its amounts use the exact legacy quote semantics above. `invoice_month_totals` has only month, basis, row count, and integer `total_haler`; the source billing contract is CZK and this extract has no currency conversion or general multi-currency support. All non-void kinds remain included as in the current analytics query. Never export account/user IDs, invoice IDs/numbers, names, emails, buyer details, bank references, discount reason, or free text.

### Proposed exact helper diff

In `App/app/db.py`, next to the existing `cursor()` helper at lines 888–895, add:

```python
@contextmanager
def readonly_cursor():
    """A consistent read transaction on the configured SQLite database.

    Uses SQLite URI mode=ro. It must not create the DB, chmod it, or change
    persistent journal/connection pragmas.
    """
    uri = config.DB_PATH.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        cur.execute("BEGIN")
        yield cur
        cur.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            cur.execute("ROLLBACK")
        raise
    finally:
        cur.close()
        conn.close()
```

This remains behind the DB abstraction. Export SQL stays parameterized and inside this helper. No PRAGMAs, schema changes, dependency, or data writes are added. A WAL-mode read-only connection may create or refresh SQLite's `-shm` coordination sidecar; tests must still prove the main database bytes, file mode, and persistent journal mode do not change. Do not use `immutable=1`, which can miss committed WAL data. If project-supported backends change, the DB abstraction owns the equivalent read-only snapshot implementation; do not put SQLite URI logic in the export script.

### Proposed exact export implementation

Add `App/scripts/export_billing_analytics.py`, with the same `sys.path` bootstrap as `list_accounts_without_email.py`. Use stdlib `argparse`, `csv` is unnecessary, `json`, `os`, `tempfile`, `datetime/date/timezone`, `zoneinfo.ZoneInfo`, `Path`, and `app.billing`, `app.config`, `app.db`.

The code contract is:

```python
MRR_STATES = {"active", "overdue", "canceling"}
ACCOUNT_SQL = """SELECT status, plan, billing_interval, apartments_billed,
addon_ttlock, addon_whitelabel, founder, carry_czk, discount_percent
FROM billing_account WHERE plan IS NOT NULL ORDER BY status"""

# Build month bounds with date(year, month, 1). The upper bound is the first
# day after through_month, including December rollover.
ISSUED_SQL = """SELECT substr(issue_date,1,7) AS month, COUNT(*) AS n,
COALESCE(SUM(total_haler),0) AS h FROM platform_invoice
WHERE voided = 0 AND issue_date >= ? AND issue_date < ?
GROUP BY substr(issue_date,1,7) ORDER BY month"""
PAID_SQL = """SELECT substr(paid_on,1,7) AS month, COUNT(*) AS n,
COALESCE(SUM(total_haler),0) AS h FROM platform_invoice
WHERE voided = 0 AND paid_on IS NOT NULL AND paid_on >= ? AND paid_on < ?
GROUP BY substr(paid_on,1,7) ORDER BY month"""
```

`extract(from_month, through_month)` validates strict `YYYY-MM` inputs and ordering before opening the DB. It runs the first account SELECT inside one `with db.readonly_cursor() as cur:`; immediately after that first SELECT starts the source snapshot, capture one `snapshot_at_utc = datetime.now(timezone.utc)` and derive `as_of_date_prague` from that same instant. Capture later `generated_at_utc` separately. Run all remaining SELECTs on the same cursor. For each account row, call `billing.quote(apartments_billed, plan, billing_interval, ttlock=bool(addon_ttlock), whitelabel=bool(addon_whitelabel), founder=bool(founder), discount_percent=int(discount_percent or 0))`; add `int(carry_czk or 0)` to `quote["total"]`. Aggregate per status: only MRR states contribute amounts; monthly interval contributes net and net×12; annual interval contributes `round(net / 12)` and net. Account count counts every plan-bearing row in that status. No identity data enters the output.

Before extraction, resolve `--output` and `config.DB_PATH`, and reject collision with the database or its `-wal`, `-shm`, and `-journal` sidecars. Collision detection must cover resolved symlink targets and existing hardlink/samefile aliases. This rejection happens before extraction or any output directory/file creation.

`publish(payload, output)` serializes once with `json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"`; creates the parent directory only after successful extraction; creates a temporary sibling using `tempfile.mkstemp(dir=output.parent, prefix=f".{output.name}.", suffix=".tmp")`; writes UTF-8, flushes and `os.fsync()`s the file; then calls `os.replace(temp, output)` exactly once. Before that replace succeeds, any error leaves a prior output intact and cleanup removes the temp. After replace succeeds, the new complete file is published; if parent-directory fsync then fails, raise/report that durability sync failed after publication (do not claim rollback or that the old output remains). In `finally`, unlink a remaining temp file. CLI arguments are required `--from-month`, `--through-month`, and `--output`; do not default to all history or a production path. Never call `db.init_db()`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/db.py` | Modify | Add encapsulated strict read-only transaction helper. |
| `App/scripts/export_billing_analytics.py` | Add | Bounded aggregate extract and one-file atomic publication. |
| `App/tests/test_db_readonly_cursor.py` | Add | Read-only enforcement, no side effects, snapshot consistency. |
| `App/tests/test_billing_analytics_export.py` | Add | Export fields/labels/range/privacy and atomic publication. |

No other file may change.

## 4. Steps

1. Implement the helper exactly as §2. It must use SQLite URI `mode=ro`, avoid `_open()` and all PRAGMAs, and commit or roll back one deferred transaction.
2. Implement the script exactly to §2. Do not invoke `db.init_db()`, `portfolio()`, snapshot/movement/funnel helpers, routes, or scheduler. Keep all data reads on the single read-only cursor.
3. Test helper with an isolated temp schema prepared using existing test helpers: assert SELECT works, INSERT raises SQLite read-only error, existing DB bytes/mode/journal mode remain unchanged, `db.init_db`, `_open`, chmod, and PRAGMA write paths are not called, and a second connection's WAL update is invisible until the read transaction ends.
4. Test export against isolated account/invoice fixtures: monthly and annual legacy rounding plus carry; trial excluded from amounts; discounted, canceling and overdue states; negative storno/correction amount semantics preserved by nonvoid row filtering; all plan accounts count; bounded months only; voided=1 excluded; `paid_on` before and after requested range handled correctly; exact minor units retained; known contact/buyer/invoice-number sentinels and IDs absent; repeated extraction has stable business sections; invalid/reversed ranges fail before DB access; output collision with DB/sidecars, symlinks, and existing samefile aliases fails before extract/publication; injected failure before replace preserves existing bytes and cleans temp; directory-fsync failure after replace reports new complete file already published.
5. Inspect diff to verify only §3 files changed.

## 5. Do not touch

- No schema, route, template, scheduler, snapshot, invoice, payment/refund writer, retention, config, deploy or production data.
- No `db.init_db()` in the script. No raw `sqlite3.connect`, raw SQL, or query outside DB helpers in the script.
- No account/user/invoice identifiers, contact or buyer fields, bank references, or free text in output.
- No cash collections, VAT, FX, credit policy, churn, historical MRR, or complete history claims.
- No dependencies, remote requests, secrets, or implicit production output path.

## 6. Commands

From `App/`, run only the focused files from the test-map billing and DB rows:

```sh
.venv/bin/python -m pytest tests/test_db_readonly_cursor.py tests/test_db_upgrade.py tests/test_db_update_if.py tests/test_billing_analytics_export.py tests/test_billing_analytics.py -q --tb=short -x 2>&1 | tail -30
```

From repo root:

```sh
python3 scripts/context_lint.py 2>&1 | tail -30
```

Do not run the full suite or invoke the CLI against production.

## 7. Acceptance

- [ ] `db.readonly_cursor()` uses URI `mode=ro`, one transaction and no chmod, initialization, PRAGMA, or source database mutation.
- [ ] All extract SELECTs share one consistent read transaction and include only the specified projections/aggregates.
- [ ] One JSON generation publishes by one atomic `os.replace`; failures before replacement preserve prior output, while a post-replacement directory fsync failure is reported as a published complete file with uncertain directory durability.
- [ ] Output path collision protection rejects resolved database/sidecar symlinks and existing samefile aliases before extraction.
- [ ] Portfolio values are labeled legacy quote and preserve rounded whole-Kč semantics; invoice amounts preserve exact integer minor units.
- [ ] Paid-date metric says invoice totals marked paid by paid_on, never cash collections.
- [ ] Output excludes identifiers, contact/buyer fields and free text; range is explicit.
- [ ] Focused tests and context lint pass; diff is limited to §3.

## 8. Stop and ask

Stop before implementation if mode=ro is unavailable for the configured SQLite database, the app gains a backend where the helper cannot preserve equivalent read-only snapshot behavior, output labels are requested to mean reconciled finances, the test cannot prove source DB state is unchanged, or any extra file/dependency is needed. Report exact blocker and do not weaken read-only guarantees.

## 9. Report

After implementation, write `docs/tasks/0452-report.md` (600 tokens max), set this brief to `Status: review`, and report changed files, exact commands and last five output lines, §7 checklist, deviations, questions, and owner steps. Do not publish or deploy the output.

## Risk list (for the reviewer)

Review the DB helper’s mode=ro connection and snapshot boundaries, the script’s field/query allowlist, and atomic replacement behavior. Confirm outputs never imply cash collections or reconciled financial MRR.

## Owner steps

1. Review the four scoped files and test report.
2. If approved, choose a non-production database and explicit output path for a manual local extraction. Production usage requires a separate owner decision and controlled environment.
