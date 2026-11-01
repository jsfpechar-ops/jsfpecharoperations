# 0467 report, part a

Status: blocked

## Files changed
- `App/migrations_pg/00003_job.sql` (new, step 1)
- `App/app/config.py` (`JOB_QUEUE_KINDS`, step 2)
- `App/app/jobqueue.py` (new, step 3)

Commits: `0467 step 1`, `0467 step 2`, `0467 step 3`.

## Commands
- `scripts/pg_schema.py plan|apply|check --expect-database ubyhost_test` (local, step 1): apply OK, version 33, goose=3, check OK.
- `pytest tests/test_scheduler.py tests/test_worker.py tests/test_goose_migrations.py` with `UBYHOST_TEST_DATABASE_URL` only: 27 passed, 1 error (goose test needs `UBYHOST_DATABASE_URL`).
- Same with both URLs set: `1 failed, 1 passed`. Second test fails with `relation "job" already exists`.
- Without URLs: 27 passed, 4 skipped.
- `python3 scripts/context_lint.py | tail -3`: lint OK.
- `tests/test_job_queue.py` does not exist yet (step 6), so it is not in the run.

## Checklist (§7)
Not ticked. Steps 4 to 7 not done.

## Deviations
Done: steps 1 to 3. Left: steps 4 to 7.

## Questions (stop)
1. Migration 00003 is not idempotent. `CREATE TABLE job` and `CREATE UNIQUE INDEX` / `CREATE INDEX` fail when the table exists. The test harness (`App/tests/conftest.py`, around line 225 to 238) truncates all tables including `goose_db_version`, then calls `db.apply_postgresql_schema()`, which re-runs goose files not recorded as applied. Existing `00002_poll_indexes.sql` uses `IF NOT EXISTS`. Brief §4 step 1 gives the exact SQL without it. Should 00003 use `CREATE TABLE IF NOT EXISTS job` and `IF NOT EXISTS` on both indexes? Or should the harness be changed? The local `ubyhost_test` DB currently has `job` and goose version 3 from my manual apply.
2. `scheduler._job_failed` looks up `_JOB_LEVELS[job_id]` (`App/app/scheduler.py` line 62). That map has no entry for `billing`, `billing_snapshot`, `stripe_sweep` or `job_queue`. The dead-letter path in `jobqueue.fail` would raise KeyError for those kinds, and step 4's `job_failed:job_queue` alert would too. Should I add `"job_queue": "warning"` and the three missing kinds to `_JOB_LEVELS`? The brief does not name that edit.

## Owner steps left
None yet for part a.
