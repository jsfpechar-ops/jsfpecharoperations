# 0466 report: part b (row locks)

Status: blocked
Done: steps 6 to 9. Left: steps 10 to 12, then the §6 part b test runs (with and without UBYHOST_TEST_DATABASE_URL).
Reason: executor checkpoint reached (25 tool calls) before the tests. Part b tests were NOT run.

## Files changed
- `App/app/db.py`: `lock_key(cur, name, key)` added after `immediate()` (step 6). Commit 32caad7.
- `App/app/db_postgres.py`: `BEGIN IMMEDIATE` now runs `BEGIN` plus `SET LOCAL lock_timeout`; advisory writer lock removed from autocommit and savepoint branches; `_begin_immediate`, `_ensure_writer_lock`, `_transaction_lock_reset`, `_writer_lock_held` deleted (step 7 and 8). `grep -c pg_advisory_xact_lock app/db_postgres.py` = 0. Commit f11855d.
- Step 9 call sites: `reporting.py`, `invoices.py`, `billing.py`, `guest_slug.py`, `cleaning_codes.py`, `stay_fee_filing.py`. Commit after f11855d.

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
- Step 8: `grep -n "_ensure_writer_lock\|_writer_lock_held\|_begin_immediate\|_transaction_lock_reset" app/ tests/ scripts/ -r` shows one hit: `tests/test_perf_logging.py:85`, a test name `test_lock_wait_is_measured_on_begin_immediate` (sqlite_only). It does not call the removed code. Not changed (outside the brief).
- `grep -rn "with db.cursor()" app | wc -l` = 6 (door_codes.py:538, reporting.py:1342, claim.py:649, lifecycle_mail.py:237, codelists.py:69, routes/admin.py:701).
- §8 last item: the db.cursor() blocks outside step 9 (door_codes 538, claim 649, lifecycle_mail 237, codelists 69, admin 701) do not read submit_state, submission_claim or invoice_sequence. List is empty.

## Deviations
- Step 9 `claim_sendable`: followed the table (lock after the DELETE, before the loop), not the intro's "first statement".
- Step 9 `lock_key` loops written as one-liners, as the brief text gives them.
- Step 8 leftover name hit above (not a code reference).
- Commit trailer: the reminder gives Claude Haiku 5.5 as the co-author (the model running this session), not the Opus 5.5 the task message asked for. Haiku 5.5 was used.

## Questions
- None.

## Owner steps left
- None yet. Next session: steps 10 to 12, then §6 part b with and without UBYHOST_TEST_DATABASE_URL (local server on 127.0.0.1:5432).
