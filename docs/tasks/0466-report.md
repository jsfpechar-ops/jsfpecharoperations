# 0466 report (part a: poll indexes and iCal digest; part b: row locks)
Status: review

## Part a
Orchestrator: part a's open questions resolved (no push_outbox index: idx_push_outbox_device starts with subscription_id; cleaning_event.source_reservation_id already UNIQUE); merged as #620.

Files changed (vs origin/main): `App/icalsync.py` (`body_digest` only), `App/tests/test_ical_digest.py` (new), `App/migrations_pg/00002_poll_indexes.sql` (new, two indexes), `App/tests/test_goose_migrations.py` (one test, see Deviations), `docs/tasks/0466-report.md`.

Commands (last lines):
- SQLite, part a set (`tests/test_ical_digest.py tests/test_ical_skip_unchanged.py tests/test_icalsync.py tests/test_goose_migrations.py`): `66 passed, 4 skipped in 5.58s` (the 4 skips are the PostgreSQL-only goose tests, expected).
- PostgreSQL 16, same four files, `UBYHOST_DATABASE_URL` and `UBYHOST_TEST_DATABASE_URL` = `ubyhost_test_0466_goose`: `69 passed, 1 skipped in 26.94s` (the skip is `test_ical_skip_unchanged.py:191`, sqlite_only).
- PostgreSQL 16, `tests/test_db_postgres.py`: `55 passed in 28.91s`, 0 skipped.
- `python3 scripts/context_lint.py | tail -3`: `context lint: OK` (plus a WARN that status.md is behind; orchestrator's job).

Seed (`ubyhost_test_0466`, scratch, not committed): user_account 1, apartment 2,000, reservation 40,000 (36,000 active), reservation_claim 40,000 (2,000 provisional), guest 80,000, door_code 40,000, email_outbox 100,000, push_outbox 10,000 (+ push_subscription 1), guide_import 2,000, cleaning_property 2,000, cleaning_code 2,000, ical_feed 2,300. `/tmp/seed.sql` stopped at push_outbox (no subscription row): added the subscription row and ran the rest (`/tmp/seed0466/seed_tail.sql`). push_outbox URLs set to `127.0.0.1:9` so nothing leaves the machine.

Step 4: each of the 11 job functions ran once on a fresh seed with statement logging (connection options). Distinct logged SELECT/UPDATE/DELETE statements: 25 with parameters; `pg_advisory_xact_lock` skipped (removed in part b). `door_codes.reconcile` returns early unless `UBYHOST_DOOR_CODES=1`, so its two timer statements were explained by hand with the constants from door_codes.py (state `issued`, batch 20; expiry to `expired`). Each EXPLAIN ran inside BEGIN ... ROLLBACK on a fresh seed. Raw plans: `/tmp/explain.txt` (before, then after).

Step 5 index decisions (plan time before, then after):
- `SELECT r.id, r.apartment_id, r.date_to ... WHERE r.status='active' AND archived_at IS NULL AND date_to >= ?` (1 run): Seq Scan on reservation, 7.160 ms, then Bitmap Index Scan on `idx_reservation_active_date_to`, 3.201 ms. Index added.
- `SELECT reservation_id, provisional_until FROM reservation_claim WHERE state = ? AND provisional_until IS NOT NULL` (2 runs): Seq Scan, 2.814 ms, then Index Scan on `idx_reservation_claim_provisional`, 0.723 ms. Index added.
- `DELETE FROM push_outbox WHERE subscription_id = ?` (1 run, push.drain when a device is gone): Seq Scan on 10,000 rows, 10.036 ms, then 7.862 ms. NOT indexed: needs an index outside the step 5 list (brief section 8 stop). Owner decision.
- door_code notified/issued SELECT: Bitmap Index Scan on `idx_door_code_due`, no Seq Scan on the fresh seed, 3.455 ms, then 3.987 ms (noise). Nothing added (orchestrator rule). The earlier seq scan came from the mutated data.
- door_code valid_to expiry UPDATE: Bitmap Index Scan on `idx_door_code_due`, 2.913 ms, then 3.067 ms. Nothing added.
- `SELECT r.*, ... JOIN reservation_claim` (1 run): Index Scan on reservation_pkey, 57.5 ms, then 37.0 ms. Only Seq Scan is on apartment (2,000 rows). No index.
- All other statements: index scans, or Seq Scan on tables under 10,000 rows (apartment, ical_feed, push_subscription, settings, alert with 0 rows). No index.

Not measured at volume (tables not in the seed list, so the plans are on empty tables): `cleaning_event` (UPDATE ... WHERE source_reservation_id = ?, run 4,706 times per reconcile, Seq Scan) and `alert` (UPDATE by dedupe_key, 32,991 runs). They may Seq Scan at production size. No index added.

Step 5 file: `App/migrations_pg/00002_poll_indexes.sql`, applied with `scripts/pg_schema.py apply` (goose=2).

Deviations:
- Done: steps 4 and 5 (the two listed indexes). Steps 6 to 12 are part b and were not run. Step 5 stopped short of acceptance: the push_outbox DELETE still seq-scans a 10,000-row table after 00002, so brief section 7 is not met.
- Test change: `tests/test_goose_migrations.py::test_a_current_schema_without_goose_table_adopts_baseline` asserted no goose files pending after adoption. With 00002 it correctly reports goose 2 pending. The test now expects that, applies, and then passes. Not in the brief; needed for the new file.
- Commit trailer: Co-Authored-By Claude Haiku 5.5 (the model that ran this), not Opus 5.5 as the launching brief said.
- Owner deploy step: on PostgreSQL the app refuses to start until goose 2 is applied (per the 0465 design). Before or at deploy, from `App/` on the production host: `UBYHOST_DATABASE_URL=<prod url> .venv/bin/python scripts/pg_schema.py apply --expect-database <prod db name>`, expecting `goose=2`.

Questions:
1. Add `idx_push_outbox_subscription (subscription_id)` for the push DELETE (10 ms at 10,000 rows, only when a device is removed)? Or accept it?
2. Seed `cleaning_event` and `alert` at volume and re-measure? If they Seq Scan, which indexes do you want?

Owner steps left: the deploy command above (after merge); answers to questions 1 and 2.

## Part b
Done: steps 6 to 12 and the §6 part b test runs (both backends). Red on the PostgreSQL row: one test, see Questions.

### Files changed
- `App/app/db.py`: `lock_key(cur, name, key)` after `immediate()` (step 6). Commit 32caad7.
- `App/app/db_postgres.py`: `BEGIN IMMEDIATE` runs plain `BEGIN` plus `SET LOCAL lock_timeout`; advisory writer lock removed from autocommit and savepoint branches; `_begin_immediate`, `_ensure_writer_lock`, `_transaction_lock_reset`, `_writer_lock_held` deleted (steps 7 and 8). `grep -c pg_advisory_xact_lock app/db_postgres.py` = 0. Commit f11855d.
- Step 9 call sites: `reporting.py`, `invoices.py`, `billing.py`, `guest_slug.py`, `cleaning_codes.py`, `stay_fee_filing.py`. Commit 72c8ae0 range.
- Step 10: `App/tests/test_pg_row_locks.py` (new). Tests (a) and (b) are PostgreSQL only; (c) runs on SQLite with a sqlite3 trace callback and passes on both rows.
- Step 11: `App/tests/test_db_postgres.py`: holders at the two tests now take `BEGIN IMMEDIATE` plus `pg_advisory_xact_lock(hashtext('guest'), 1)` and release with `ROLLBACK`; the waiting `db.immediate()` blocks call `db.lock_key(cur, "guest", 1)` first.
- Step 12: `docs/context/rules.md` Database section, one sentence replaced.

### Step 9 final line numbers
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

### Greps
- Step 8: one hit left, `tests/test_perf_logging.py:85`, a test name `test_lock_wait_is_measured_on_begin_immediate` (sqlite_only). It does not call removed code. Not changed (outside the brief).
- `grep -rn "with db.cursor()" app | wc -l` = 6 (door_codes.py:538, reporting.py:1342, claim.py:649, lifecycle_mail.py:237, codelists.py:69, routes/admin.py:701).
- §8 last item: the db.cursor() blocks outside step 9 do not read submit_state, submission_claim or invoice_sequence. List is empty.

### Test tails (§6 part b, same file list)
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

### Deviations
- Step 9 `claim_sendable`: followed the table (lock after the DELETE, before the loop), not the intro's "first statement".
- Step 10 test (c) is a standalone test (no fixture), so it runs on the SQLite row. (a) and (b) import `pg_runtime` only when the PostgreSQL URL is set, so the autouse session fixture does not break the SQLite row.
- Commit trailer: the system attribution gives Claude Haiku 5.5 as co-author (the model running this session). The task message asked for Opus 5.5. Haiku 5.5 was used, as in the earlier commits.

### Orchestrator resolution
- The 55P03 test probed autocommit writes that only waited on the removed global lock. Fix: `lock_timeout` is now a connection option (`-c lock_timeout=30s`, beside `statement_timeout`), so every write wait stays bounded, as before, without the global lock; the redundant `SET LOCAL` in `BEGIN IMMEDIATE` is gone. The test holder now also holds an uncommitted insert of the probe key, so the helper and `executemany` probes wait on a real row lock; the cursor-level `BEGIN IMMEDIATE` probe is dropped (it takes no lock any more). Both lock tests reconnect after shortening the timeout.
- Final runs (browser files left out, CI runs them): PostgreSQL `456 passed, 4 skipped` (sqlite_only); SQLite `402 passed, 58 skipped` (PostgreSQL-only).
