# 0460: Run the PostgreSQL test module in CI
Status: review
Depends on: none (no-op until #592 lands `App/tests/test_db_postgres.py`) | Base commit: main | Branch: task/0460-postgres-tests-in-ci
Executor: Haiku 5.5 | Fits one session: 15 tool calls, 30k tokens
## 1. Objective
Give CI a disposable PostgreSQL so `App/tests/test_db_postgres.py` (arriving with PR #592) runs with 0 skipped instead of skipping for lack of a server. Plan: [migration-plan-v4](../plans/postgresql/migration-plan-v4.md) step 4.
## 2. Context
`.github/workflows/ci.yml` job `test` runs `python -m pytest tests -q` with SQLite. The PG module skips unless `UBYHOST_TEST_DATABASE_URL` points at a disposable database (its name must contain `test`). On main the file does not exist yet, so the new job must be a no-op there.
## 3. Files
`.github/workflows/ci.yml` only.
## 4. Steps
1. Add a job `test-postgres` after `test`, same runner, Python and pip cache steps copied from `test`.
2. `services: postgres:` image `postgres:17-alpine`, env `POSTGRES_PASSWORD: ubyhost`, `POSTGRES_DB: ubyhost_test`, ports `5432:5432`, health check `pg_isready` (interval 5s, retries 10).
3. Steps: checkout, setup python, install requirements, then
   `if: hashFiles('App/tests/test_db_postgres.py') != ''` →
   `env: UBYHOST_TEST_DATABASE_URL: postgresql://postgres:ubyhost@localhost:5432/ubyhost_test` and run from `App/`: `python -m pytest tests/test_db_postgres.py -q -rs --tb=short 2>&1 | tail -30`, then a step that fails if the output contains `skipped`.
   Otherwise one step echoing "no PostgreSQL module yet".
4. Keep the existing `test` job unchanged. Add `test-postgres` to the `browser` fan-in `needs:` list only if every other test job is listed there (read it first).
## 5. Do not touch
Any other job, `App/`, `docs/` other than the report.
## 6. Commands
`python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml'))"` and the repo's `workflow-lint` if runnable locally (`zizmor .github/workflows/ci.yml` if installed; otherwise skip and say so).
## 7. Acceptance
YAML parses; on main the new job is a visible no-op; the `test` job is byte-identical.
## 8. Stop and ask
Stop if the workflow uses a reusable composite action for setup that cannot be copied; report instead of inventing one.
## 9. Report
`docs/tasks/0460-report.md`: the job text, the lint result.
