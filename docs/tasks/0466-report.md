# 0466 report: part b (row locks)

Status: review
Done: steps 6 to 12 and the §6 part b test runs (both backends). Red on the PostgreSQL row: one test, see Questions.

## Files changed
- `App/app/db.py`: `lock_key(cur, name, key)` after `immediate()` (step 6). Commit 32caad7.
- `App/app/db_postgres.py`: `BEGIN IMMEDIATE` runs plain `BEGIN` plus `SET LOCAL lock_timeout`; advisory writer lock removed from autocommit and savepoint branches; `_begin_immediate`, `_ensure_writer_lock`, `_transaction_lock_reset`, `_writer_lock_held` deleted (steps 7 and 8). `grep -c pg_advisory_xact_lock app/db_postgres.py` = 0. Commit f11855d.
- Step 9 call sites: `reporting.py`, `invoices.py`, `billing.py`, `guest_slug.py`, `cleaning_codes.py`, `stay_fee_filing.py`. Commit 72c8ae0 range.
- Step 10: `App/tests/test_pg_row_locks.py` (new). Tests (a) and (b) are PostgreSQL only; (c) runs on SQLite with a sqlite3 trace callback and passes on both rows.
- Step 11: `App/tests/test_db_postgres.py`: holders at the two tests now take `BEGIN IMMEDIATE` plus `pg_advisory_xact_lock(hashtext('guest'), 1)` and release with `ROLLBACK`; the waiting `db.immediate()` blocks call `db.lock_key(cur, "guest", 1)` first.
- Step 12: `docs/context/rules.md` Database section, one sentence replaced.

## Step 9 final line numbers
- reporting.claim_sendable: 1347 (after the DELETE at 1344)
- reporting.recover_stale_submissions: 1829, 1850
- reporting._retry_outcome_unknown_batches: 1908
- reporting.mark_filed_by_hand: 2145 (plus the SELECT id line above it)
- reporting.undo_filed_by_hand: 2186 (plus the SELECT id line above it)
- invoices._write_issued: 651
- billing.set_status: 172; billing.claim_founder_slot: 365
- guest_slug.ensure: 183; rename: 214; rotate: 258
- cleaning_codes.save_manual: 76; queue_permanent: 109; remove: 254
- stay_fee_filing.save: 129

## Greps
- Step 8: one hit left, `tests/test_perf_logging.py:85`, a test name `test_lock_wait_is_measured_on_begin_immediate` (sqlite_only). It does not call removed code. Not changed (outside the brief).
- `grep -rn "with db.cursor()" app | wc -l` = 6 (door_codes.py:538, reporting.py:1342, claim.py:649, lifecycle_mail.py:237, codelists.py:69, routes/admin.py:701).
- §8 last item: the db.cursor() blocks outside step 9 do not read submit_state, submission_claim or invoice_sequence. List is empty.

## Test tails (§6 part b, same file list)
SQLite row (no UBYHOST_TEST_DATABASE_URL), run with `-x`:
```
240 passed, 60 skipped in 17.89s
```
The skips are the PostgreSQL-only tests and the Playwright files (`test_cleaning_browser.py`, `test_host_ux_acceptance.py`, `test_stay_fee_send_panel.py`: `playwright` is not installed in `App/.venv`). Those browser tests did not run here.

PostgreSQL row (UBYHOST_TEST_DATABASE_URL set to the local ubyhost_test database), run with `-x`:
```
1 failed, 15 passed, 3 skipped in 7.38s
FAILED tests/test_db_postgres.py::test_writer_lock_timeout_surfaces_as_lock_not_available_through_every_helper
E   Failed: DID NOT RAISE LockNotAvailable
```
Same row without `-x`: `1 failed, 294 passed, 5 skipped in 96.55s`. The 5 skips: the 3 Playwright files above, plus `test_guest_slugs.py:147` and `test_stay_fee.py:392` (both `sqlite_only`). The new tests (a), (b) and the rest of `test_db_postgres.py` (57 tests) pass.

## Deviations
- Step 9 `claim_sendable`: followed the table (lock after the DELETE, before the loop), not the intro's "first statement".
- Step 10 test (c) is a standalone test (no fixture), so it runs on the SQLite row. (a) and (b) import `pg_runtime` only when the PostgreSQL URL is set, so the autouse session fixture does not break the SQLite row.
- Commit trailer: the system attribution gives Claude Haiku 5.5 as co-author (the model running this session). The task message asked for Opus 5.5. Haiku 5.5 was used, as in the earlier commits.

## Orchestrator resolution
- The 55P03 test probed autocommit writes that only waited on the removed global lock. Fix: `lock_timeout` is now a connection option (`-c lock_timeout=30s`, beside `statement_timeout`), so every write wait stays bounded, as before, without the global lock; the redundant `SET LOCAL` in `BEGIN IMMEDIATE` is gone. The test holder now also holds an uncommitted insert of the probe key, so the helper and `executemany` probes wait on a real row lock; the cursor-level `BEGIN IMMEDIATE` probe is dropped (it takes no lock any more). Both lock tests reconnect after shortening the timeout.
- Final runs (browser files left out, CI runs them): PostgreSQL `456 passed, 4 skipped` (sqlite_only); SQLite `402 passed, 58 skipped` (PostgreSQL-only).
