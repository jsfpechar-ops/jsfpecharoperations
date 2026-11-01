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
