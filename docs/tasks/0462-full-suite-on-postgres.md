# 0462: Run the whole test suite against PostgreSQL in CI
Status: review
Depends on: 0461 merged | Base commit: main after 0461 | Branch: task/0462-full-suite-on-postgres
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 80k tokens (expect several sessions: one per batch of dialect failures)
## 1. Objective
Prove the application, not just the DB module, runs on PostgreSQL: a CI job that runs `pytest tests` with `UBYHOST_DATABASE_URL` set against the service container, green. Until it is green and required, the flag is never set in production. Plan: [migration-plan-v4](../plans/postgresql/migration-plan-v4.md) step 5.
## 2. Context
`tests/conftest.py` points every test at a temporary SQLite file. On PostgreSQL all tests share one database, so the job needs a per-session schema reset (truncate all tables between tests or a fresh schema per test module). Expect dialect failures: bare columns in `GROUP BY`, TEXT compared to int, NULL ordering, `LIKE` on non-ASCII. Each is fixed in the app query (Postgres-portable SQL, rule 5), never by skipping the test.
## 3. Files
`.github/workflows/ci.yml` (job `test-postgres`: add a second step or a sibling job `test-postgres-full`, `continue-on-error: true` until green, then remove that line), `App/tests/conftest.py` (PostgreSQL reset fixture, SQLite path unchanged), app queries the failures point at.
## 4. Steps
1. Add the job with `continue-on-error: true` and upload the junit XML as an artifact. Push, read the failure list from the artifact.
2. Add the reset fixture in `conftest.py` guarded by `config.DB_BACKEND == "postgresql"`.
3. Fix failures in batches of at most 10, one commit per batch, each with the file:line and the dialect cause in the message.
4. When the job is green twice in a row, remove `continue-on-error` and add the job to the required checks list in the report for the owner.
## 5. Do not touch
Test assertions (fix the query, not the test), `test_db_postgres.py`, anything under `deploy/`.
## 6. Commands
From `App/`: `.venv/bin/python -m pytest <failing files> -q --tb=short -x 2>&1 | tail -30` on SQLite to prove the fix keeps SQLite green; CI proves PostgreSQL.
## 7. Acceptance
`test-postgres-full` green on `main` without `continue-on-error`; SQLite `test` job unchanged and green.
## 8. Stop and ask
Stop if a failure needs a schema change (new migration) or touches the UbyPort submit path (`reporting.py`, `ubyport/`): report it, the orchestrator decides.
## 9. Report
`docs/tasks/0462-report.md`: failure count per batch, each dialect cause once, final green run link.

## Batch E (CI run 2079 on 5f9fc25: 4479 passed, 1 error)

`tests/test_retention_job.py::test_log_and_acceptance_retention` errors at teardown on PostgreSQL:
`_purge()` deletes `user_account` rows named `retjob-%` while `legal_acceptance` still references them (`legal_acceptance_user_account_id_fkey`). On SQLite the test swaps `config.DB_PATH` to a temp file, so the teardown purge never sees those rows; on PostgreSQL there is one database.

Fix, in `_purge()` only: before `DELETE FROM alert WHERE owner_user_id = ?` add
`db.execute("DELETE FROM legal_acceptance WHERE user_account_id = ?", (row["id"],))`.
Nothing else changes. Verify from `App/` with `UBYHOST_DATABASE_URL=postgresql://postgres:ubyhost@127.0.0.1:5432/ubyhost_test .venv/bin/python -m pytest tests/test_retention_job.py -q --tb=short 2>&1 | tail -5` and then the same file without the env var (SQLite). Both must pass with 0 failed. Commit on this branch with message `0462: retention purge removes legal_acceptance before the user (PostgreSQL FK)` and push with `git push -u origin task/0462-full-suite-on-postgres`.
