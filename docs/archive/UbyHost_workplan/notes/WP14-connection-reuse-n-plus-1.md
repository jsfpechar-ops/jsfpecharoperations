# WP14: One database connection per thread, and remove N+1 queries (HIGH RISK)

Commit `e97b048` on branch `wp14`, based on `wpbase`. WP15 is stacked on top of this commit.

## Summary

Part A. `db.py` keeps one SQLite connection per thread, opened once with the three PRAGMAs and reused by every helper (`query`, `query_one`, `execute`, `insert`, `update`, `update_if`, `get_setting`, `set_setting`, `audit`) and by `cursor()` / `immediate()`. The cache is keyed by the database path and by the file's device and inode, so a test that changes `config.DB_PATH`, or a restore that replaces the file, gets a new connection. Transaction semantics are the same as before:

- Connections stay in autocommit mode (`isolation_level=None`). A helper call is its own statement.
- `cursor()` / `immediate()` run `BEGIN` / `BEGIN IMMEDIATE` and always COMMIT or ROLLBACK before the block returns, including on `BaseException`. After a failed block the connection is rolled back and stays usable. If ROLLBACK itself fails, the connection is dropped and a new one is opened on next use.
- After every helper call and every block, the code checks that `conn.in_transaction` is False. This check is always on, not only in debug or tests. A helper that leaves a transaction open (for example `db.execute("BEGIN")`) is rolled back and raises `RuntimeError`.
- A helper call, or a nested block, inside an open block on the same thread gets a separate short-lived connection, the same as before sharing. So it never joins the outer transaction, and it never commits it.
- `db.execute()` returns `lastrowid` only when the statement inserted a row, and 0 otherwise. A fresh connection used to report 0, and `acceptance.backfill_from_audit` counts `INSERT OR IGNORE` inserts that way. A shared connection would otherwise report the previous insert's id.
- New `db.execute_rowcount()`. `routes/admin.py` (headcount correction) used `db.connect()` directly and now uses this helper.
- New `db.close_connections()`, called from the app lifespan after `scheduler.shutdown()`. It is also used by tests. Pool threads that exit take their connection with them (a weak registry).
- `db.connect()` still returns a private connection. `init_db` and some tests use it.

Part B. N+1 removal:

- `reporting.guests_by_reservation(ids)`: one `IN (...)` query per chunk of 500 ids, in the same order the per-stay read used.
- `reporting.preload_guests(rows)` wraps it. If any guest will not decrypt, it returns `{}`, and every stay then reads its own guests as before. So one unreadable stay is still skipped alone and does not break the page.
- `reservation_progress(reservation, guests=None)` and `reservation_deadline_anchor(reservation, guests=None)` accept the preloaded guests.
- Dashboard (`dashboard_rows`): guests are batched, the deadline anchor is computed from the same guests, and the apartment rows the route already loaded are reused (new optional `apartments` parameter). Any apartment missing from that list is still looked up per stay.
- Stays list (`/reservations`): guests are batched and each property is read once. The template passes `progress.guests` to `deadline_anchor`.
- Notification cards (`alerts.present_many`, shown on every page): the reservations and guests behind all stay alerts are read in two queries. The deadline anchor comes from the progress guests.
- `celebrations.celebration_context`: one count instead of three.
- Stay fees: `property_period` counts unsigned guests in the same pass. `unsigned_stays(..., period)` uses that count when the period matches, so the period's guests are not read and decrypted a second time. `guest_period` no longer decrypts `fee_host_reason_enc` again for a row the helpers already decrypted (`db.is_decrypted`).

Measured on the demo seed: 18 stays, 2 properties, stay fees switched on. The method uses SQLite's trace callback on every connection, after a warm-up request. "Statements" includes the PRAGMAs and connection opens that went away.

| Page | Queries before | Queries after | Statements before | Statements after | Connections opened before / after |
|---|---|---|---|---|---|
| Dashboard `/` | 73 | 18 | 292 | 18 | 73 / 0 |
| Stays list `/reservations` | 67 | 19 | 268 | 19 | 67 / 0 |
| Stay page (most guests) | 25 | 19 | 100 | 19 | 25 / 0 |
| Stay fees list `/stay-fees` | 31 | 23 | 124 | 23 | 31 / 0 |
| Stay fee detail (per property) | 24 | 17 | 96 | 17 | 24 / 0 |
| Invoices `/invoices` | 20 | 14 | 80 | 14 | 20 / 0 |

Target met: dashboard 18 and stays list 19, both under 20.

Render equality. I seeded one database, copied it twice, and rendered 27 pages with the base code (`wpbase`) and with WP14: dashboard, stays list, every stay page, stay fees list for three months, both stay fee detail pages, and invoices. Result: 27 of 27 identical after removing CSRF tokens and ISO timestamps. The same check runs inside the suite (`test_batched_pages_render_exactly_as_the_per_stay_path`), comparing the batched pages with the per-stay fallback path.

## Files changed

- `App/app/db.py`: per-thread connection cache, `_transaction`, idle check, `close_connections`, `execute_rowcount`, `is_decrypted`, and `execute()` return value made the same as on a fresh connection.
- `App/app/main.py`: closes connections on shutdown, after the scheduler.
- `App/app/reporting.py`: `guests_by_reservation`, `preload_guests`, `IN_CHUNK`, optional `guests` on progress and anchor, batched `dashboard_rows`.
- `App/app/routes/admin.py`: dashboard passes `apartments`, stays list batches guests and properties, headcount correction uses `db.execute_rowcount`.
- `App/app/templates/reservations.html`: `deadline_anchor(reservation, progress.guests)`.
- `App/app/alerts.py`: `_preload_stays`, and `present` / `present_many` reuse it.
- `App/app/celebrations.py`: one count.
- `App/app/stay_fee.py`: unsigned count in the same pass, no second decrypt.
- `App/app/routes/stay_fees.py`: passes `period` to `unsigned_stays`.
- `App/tests/test_alert_language.py`, `App/tests/test_notification_copy.py`: the monkeypatched `reservation_progress` and anchor fakes accept the new optional argument.
- `App/tests/test_connection_reuse.py`: new.
- `App/tests/test_query_budget.py`: new.

## Tests added

`tests/test_connection_reuse.py` (13 tests, each on its own temporary database):
- reuse on one thread, and a separate connection per thread
- switching `config.DB_PATH` changes the connection; a replaced file is reopened; `close_connections` works
- no open transaction after helpers and blocks
- rollback on error inside `immediate()` keeps the connection usable
- a helper that opens a transaction is rolled back and raises
- a helper inside a block does not join the block
- a nested block uses its own connection
- `execute()` return values: inserted id, `INSERT OR IGNORE`, UPDATE, DELETE
- three concurrency tests, 8 threads started together with a barrier:
  - read-modify-write `immediate()` blocks mixed with autocommit inserts: no lost update, no "database is locked"
  - 32 concurrent invoice issues: numbers 1 to 32, no gaps or duplicates
  - 8 concurrent `claim_sendable` calls over the same 30 guests: each guest leased exactly once

`tests/test_query_budget.py` (7 tests, demo seed in a temporary database):
- dashboard and stays list each under 20 queries, with no per-stay guest read
- stay fee list reads guests once per property
- render equality between the batched path and the per-stay path
- one undecryptable guest skips only its stay
- `guests_by_reservation` matches the per-stay read
- chunking works

## Test commands and results (exact counts)

Run from `/tmp/wp/wp14/App`:

- `.venv/bin/python -m pytest -q tests/test_connection_reuse.py tests/test_query_budget.py`: 20 passed.
- Whole suite in one process, WP14 commit alone: `pytest -q tests` gave 2183 passed, 7 skipped, 2 failed.
- Whole suite in one process, with WP15 on top: 2192 passed, 7 skipped, 2 failed. Both failures already happen on `wpbase`:
  - `test_host_geometry.py::test_the_month_filter_shares_its_page_edges`: Chromium cannot start in this sandbox (missing `libXdamage.so.1`). It fails the same way on `wpbase`.
  - `test_stale_submission.py::test_a_running_batch_without_a_live_claim_becomes_outcome_unknown`: depends on test order. It passes alone. On `wpbase` it fails the same way when run after `tests/test_[p-r]*.py tests/test_s[a-t]*.py` (checked: 1 failed, 588 passed on `wpbase`).
- 5 runs of the concurrency tests: all passed.
- Ruff (`E9,F63,F7,F82,F401,F841`): all checks passed.

## Deviations from the spec and why

- "Add a check in debug and tests": the `in_transaction` check is always on. It is an attribute read, and a leaked transaction on a shared connection would swallow later writes, so production should fail loudly too.
- Helper calls and nested blocks inside an open block use a private connection, as before, instead of the shared one. This keeps "exactly the same transaction semantics". The codebase has no such call today; all blocks use `cur` only.
- `db.execute()` now returns 0 for non-inserts and for ignored inserts, which is what a fresh connection returned. One case cannot be reproduced: an upsert that took the UPDATE branch now returns the connection's previous insert id. No caller reads an upsert's result (checked by grep).
- Beyond the dashboard and stays list, I also batched the notification cards (`alerts.present_many`) and the celebration count. Without them the dashboard stayed at 22 queries and missed the target of under 20.
- The stay page went from 25 to 19 queries without page-specific work. The fees list keeps 3 queries per property (filing lookup, guests, adjustments). The demo seed has 2 properties, so the per-property gain looks small there.
- Query counts were measured with an SQLite trace callback (helper scripts below), because WP13's per-request counter is not in this base.

## What Cursor must verify or adapt when applying on the real main

- If WP13 is merged first, its contextvar counter will hook into `db.py` helpers that this patch rewrote. Put the counter in `_helper_conn()` and `_transaction()`. Measure `lock_ms` around `cur.execute(begin)` in `_transaction`.
- Grep for any new direct `db.connect()` callers on main. Each must close its own connection, or move to a helper.
- Grep for any new `db.execute(...)` whose return value is used for something other than an inserted id.
- Grep for new `with db.immediate()` / `db.cursor()` blocks that contain an `await` or a `yield`. A block must not span an await on the event-loop thread, because coroutines on that thread share its connection.
- Re-run the before/after measurement with `WP14-measure_queries.py` and `WP14-compare_html.py` (in this folder). Usage: from `<checkout>/App`, run `python measure.py seed /tmp/x/seed.db`. Then copy the seed and run `python measure.py render <copy> <outdir>` once with the old code and once with the new. Finally run `python compare_html.py <old_outdir> <new_outdir>`.
- Deploy to staging and click through: dashboard, stays list, a stay, Sync now, a guest form save, an invoice issue, and a stay fee finalize. Watch for "database is locked" in the logs.

## Manual steps for the owner

- None on the server. After deploy, the `-wal` file next to the database stays present while the app runs, because connections are long-lived. SQLite's autocheckpoint keeps it small. This is normal and fine for Litestream.
- Review the `db.py` hunks by hand (HIGH RISK): `_thread_conn`, `_helper_conn`, `_transaction`, `close_connections`, `execute`.
