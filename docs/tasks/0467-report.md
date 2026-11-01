# 0467 report, part a

Status: review

## Files changed
- `App/migrations_pg/00003_job.sql` (step 1: IF NOT EXISTS, DROP IF EXISTS)
- `App/app/scheduler.py` (step 4b levels; step 4 queue targets, `job_queue` consumer, shutdown stop)
- `App/app/host_i18n.py` (step 4b job names, en and cs)
- `App/app/retention.py` (step 5 comment)
- `docs/ENVIRONMENT.md`, `docs/plans/postgresql/owner-steps-cutover.md` (step 7)
- `App/tests/test_job_queue.py` (step 6, new)
- Earlier: `App/migrations_pg/00003_job.sql`, `App/app/config.py`, `App/app/jobqueue.py` (steps 1 to 3)

Commits: `0467 step 1: ...`, `0467 step 4b`, `0467 step 4`, `0467 step 5`, `0467 step 7`, `0467 step 6`.

## Commands
- PostgreSQL, both URLs set: `tests/test_job_queue.py tests/test_scheduler.py tests/test_worker.py tests/test_goose_migrations.py`: 38 passed, 1 failed, 3 skipped. The 3 skips are the SQLite-only registration tests, skipped by design on PostgreSQL. All 7 PostgreSQL lifecycle tests (a) to (g) pass.
  - Failure: `test_goose_migrations.py:94` expects `goose migrations 2 are not applied`; actual is `goose migrations 2, 3 are not applied`. Caused by the new 00003 file.
- Without URLs: 31 passed, 11 skipped (PostgreSQL-only tests).
- `python3 scripts/context_lint.py | tail -3`: lint OK.
- `tests/test_host_i18n.py` alone: 3 failures, identical at the commit before step 4b (pre-existing, `no such table: apartment` when run alone). Not in §6.

## Checklist (§7)
- [x] With the setting unset, registration is unchanged (test_unset_setting_registers_the_wrappers_unchanged)
- [x] PostgreSQL tests (a) to (g) green, 0 skipped
- [x] SQLite tests green
- [ ] No job runs inside the claim transaction: true by drain's design, not tested separately
- [ ] Part b: not started

## Deviations
Done: steps 1 to 7 (4b first). Left: part b (steps 8 to 10).

## Orchestrator resolution
- `test_goose_migrations.py` adoption test now matches `goose migrations 2(, \d+)* are not applied`, so a later goose file does not break it again. `scheduler.py` imports `jobqueue` in its import block. Reruns: PostgreSQL 39 passed, 3 skipped (SQLite-only registration tests); SQLite 29 passed, 7 skipped.
- Note for part b: the `_job_*` wrappers catch their own exceptions, so on the queue a failing job still alerts through its wrapper and the row is marked done; `fail`/backoff covers crashes outside the wrappers.

## Owner steps left
- Step 7 (ENVIRONMENT row and cutover step) is written. Nothing to run yet.

# 0467 report, part b

Status: review

## Files changed
- `App/app/scheduler.py`: `start()` takes `_acquire_single_instance_lock()` only when not every job kind is queued on PostgreSQL (step 8).
- `App/app/worker.py`: docstring sentence on the lock skip (step 9).
- `App/tests/test_job_queue.py`: two PostgreSQL tests, 15 kinds queued (lock never taken) and 14 kinds (lock taken once) (step 10).
- Commits: `0467 step 8`, `0467 step 9`, `0467 step 10`, then this report.

## Commands
- PostgreSQL, both URLs set (`ubyhost_test`): `tests/test_job_queue.py tests/test_scheduler.py tests/test_worker.py tests/test_goose_migrations.py -q --tb=short -x -rs`
  ```
  SKIPPED [1] tests/test_job_queue.py:60: SQLite registration rules
  SKIPPED [1] tests/test_job_queue.py:69: SQLite registration rules
  SKIPPED [1] tests/test_job_queue.py:78: SQLite registration rules
  41 passed, 3 skipped in 21.14s
  ```
- Neither URL set: `tests/` same four files, `-q --tb=short -x -rs`
  ```
  31 passed, 13 skipped in 4.40s
  ```
  The 13 skips are the PostgreSQL-only tests (9 in `test_job_queue.py`, 4 in `test_goose_migrations.py`).
- `python3 scripts/context_lint.py | tail -3`: `context lint: OK`.

## Checklist (§7, part b)
- [x] Lock skipped only with all 15 ids on PostgreSQL (test 10, 15-kind case; 14-kind case takes it once)
- [x] SQLite tests unchanged and green
- [x] Part a acceptance unchanged: unset setting registration test green

## Deviations
- The 3 "SQLite registration rules" tests skip on PostgreSQL by design (they are existing part a tests), so the PostgreSQL run is `3 skipped`, not `0 skipped`. All new part b tests run on PostgreSQL and pass.
- Commit trailer: the brief asked for `Co-Authored-By: Claude Opus 5.5`. The executor is Haiku 5.5, so the commits carry `Co-Authored-By: Claude Haiku 5.5` as the session attribution instructed. Owner or orchestrator can amend if Opus was intended.
- Done: steps 8 to 10. Left: nothing in part b.

## Owner steps left
- Part b changes nothing to deploy. Step 7 cutover order still applies (see part a).
