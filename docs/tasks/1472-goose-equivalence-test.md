# 1472: goose-only schema equals Python's apply (PostgreSQL test in CI)

Status: todo
Depends on: 1471 (its `1471 step` commits on this branch) | Base: the current branch (claude/happy-babbage-2zeeam; writer verified on d3817813d plus 1471) | Branch: none, see below
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier A (migrations). Plan: [sqlite-retirement](../plans/sqlite-retirement.md) step S3.

**One big PR mode.** Work on the current branch. Commit `1472 step k` after each step. Never create a branch, never push, never open a PR. Acceptance uses `git log --oneline --grep='^1472 step'` and `git show --stat`, not a base commit.

## 1. Objective

Add `App/tests/test_goose_equivalence.py`, which builds one database with Python's apply and one from the goose files alone, and fails when their `pg_dump --schema-only --no-owner` output or their version rows differ. Run it in the CI job `test-postgres`, so that from now on the goose files can only drift from production's schema through a red check.

## 2. Context

**What the test does** (`docs/tasks/1472-files/test_goose_equivalence.py`, copied verbatim in step 1):

- Runs only when `UBYHOST_TEST_DATABASE_URL` is set (skips otherwise, like `test_db_postgres.py`), on two throwaway databases `ubyhost_test_goose_eq_<pid>_a` and `_b`, dropped afterwards.
- A: `scripts/pg_schema.py apply --expect-database <a>` in a subprocess (translated SQLite migrations, then goose files: how production was built).
- B: the goose files alone. Main has no goose-only runner (Python's apply always runs the SQLite pass first, its goose parser refuses the `00001` pg_dump file, and Go `migrate apply` refuses an empty database). So the test does what every Go test helper does (`go/internal/jobs/queue_test.go` `applyMigrations`): it runs the text between `-- +goose Up` and `-- +goose Down` of each file, in version order, one transaction per file, and writes `goose_db_version` as goose does (the same DDL as `db._goose_ensure_table`, row 0, then one row per file). No new dependency (psycopg is already used).
- Dumps both with `pg_dump --schema-only --no-owner` and compares after `normalise()`, which drops `--` comment lines, blank lines and the `\restrict`/`\unrestrict` lines (a random key per dump), and **sorts the column lines inside each `CREATE TABLE (...)` block** (trailing comma removed). That is the only schema difference allowed: column order (a goose `ADD COLUMN` lands last). A table whose order differs is reported with `warnings.warn`, never a failure. Any other line difference fails with a unified diff (first 200 lines).
- Data: `SELECT version, name FROM schema_migrations ORDER BY version` and `SELECT version_id, is_applied FROM goose_db_version ORDER BY id` must be equal (`applied_at`, `id` and `tstamp` are written at apply time and are not compared).
- `pg_dump` must be on PATH and its major version at least the server's; otherwise the test **fails** (`pg_dump 16 is older than PostgreSQL server 17; ...`), never skips.

Not seen (plan "What the S3 diff cannot see"): rows outside the two version tables (backfills do nothing on an empty database), sequence values, grants and ownership (`pg-app-role.sh check` covers them).

**Writer's run** (PostgreSQL 16, pg_dump 16.15): with 1471's 00017, `1 passed in 2.34s`, no column order warning. Without 00017 it failed on the 6 FKs and the 19 `COLLATE "C"` columns that 1471 fixes; nothing else differed. Mutation (00016 `DEFAULT 1` to `DEFAULT 0`): `1 failed`, diff lines `-    guest_details_mail bigint DEFAULT 1 NOT NULL` / `+    guest_details_mail bigint DEFAULT 0 NOT NULL`. A fake `pg_dump 15.4` gave `Failed: pg_dump 15 is older than PostgreSQL server 16`. No URL: `1 skipped`. ruff: `All checks passed!`.

**CI** (`.github/workflows/ci.yml`, job `test-postgres`): its service is `postgres:17-alpine`, and it already sets `UBYHOST_TEST_DATABASE_URL` for `test_db_postgres.py` and fails on any skip ("Fail if PostgreSQL tests were skipped"). The runner's own `pg_dump` (Ubuntu package) may be older than 17, so the patch adds a step that puts a `pg_dump` wrapper on PATH (`$RUNNER_TEMP/bin`, already on PATH from the goose install step) which runs the service container's own `pg_dump` (`docker exec -i <service id> pg_dump "$@"`; `localhost:5432` inside the container is the server itself). Same image, no new package. It then adds the test file to the existing pytest line. `test-postgres-full` sets only `UBYHOST_DATABASE_URL`, so the test skips there and adds nothing to that job. The writer could not run GitHub Actions: the wrapper is proven only by the first CI run (§7).

No file under `App/app/` changes, so no go-first exception is needed.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/tests/test_goose_equivalence.py | new (copy) | the test |
| .github/workflows/ci.yml | edit (patch) | `test-postgres`: pg_dump wrapper step; test added to the pytest line |
| docs/tasks/1472-report.md | new | your report |
| docs/tasks/1472-goose-equivalence-test.md | exists | Status line only |
| docs/tasks/1472-files/* | exist | sidecars; do not edit |

No other file may change.

## 4. Steps

From the repo root unless a step says `App/`.

**Step 0. Check 1471 is on this branch.**

```bash
git status --short | wc -l; git log --oneline --grep='^1471 step' | wc -l
test -f App/migrations_pg/00017_goose_parity.sql && echo has-00017; test -f App/tests/test_goose_equivalence.py && echo test-exists
```

Expected: `0` (clean tree), `4` or more, `has-00017`, and no `test-exists`. Otherwise STOP (1471 is not done, or this brief already ran).

**Step 1. Add the test.**

```bash
cp docs/tasks/1472-files/test_goose_equivalence.py App/tests/test_goose_equivalence.py
sha256sum App/tests/test_goose_equivalence.py | cut -c1-64
git add App/tests/test_goose_equivalence.py && git commit -m "1472 step 1" 2>&1 | tail -1
```

Expected hash: `3d73ecb56f59ba05d49e3cc8b0517020d3a4bf221b2b20d3260b47e758bbde77`. Different: STOP.

**Step 2. Patch CI.**

```bash
grep -cF 'python -m pytest tests/test_db_postgres.py -q -rs --tb=short 2>&1 | tee "$RUNNER_TEMP/pg-tests.log" | tail -30' .github/workflows/ci.yml
git apply --check docs/tasks/1472-files/ci.patch && git apply docs/tasks/1472-files/ci.patch && git diff --stat 2>&1 | tail -2
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('yaml ok')"
sha256sum .github/workflows/ci.yml | cut -c1-64
```

Expected: `1`; `1 file changed, 10 insertions(+), 1 deletion(-)`; `yaml ok`; hash `f2d116644ebc7bd0fb8cce08ae6b773403e3928e7add4824d8e883251e55d390` (a different hash after a clean apply means a later commit changed `ci.yml`: write it under Deviations and go on). `git apply --check` fails: STOP, never `--reject`, never edit by hand. Commit: `git add .github/workflows/ci.yml && git commit -m "1472 step 2" 2>&1 | tail -1`.

**Step 3.** Run §6, including the mutation check. **Step 4.** Write the report (§9), commit it as `1472 step 4: report`.

## 5. Do not touch

`App/migrations_pg/**` (the mutation in §6 is reverted before any commit), `App/app/**`, `App/scripts/**`, `App/tests/conftest.py`, every other job in `ci.yml`, `go/**`, `deploy/**`, `docs/context/*`. Rules 3, 4 and 8: no secrets, no new dependency, never push. Never connect to any database but the disposable one below.

## 6. Commands

From `App/` (create `.venv` only if missing: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3`):

```bash
env -u UBYHOST_DATABASE_URL -u UBYHOST_TEST_DATABASE_URL .venv/bin/python -m pytest tests/test_goose_equivalence.py tests/test_migrations.py -q -rs --tb=short 2>&1 | tail -3
.venv/bin/ruff check tests/test_goose_equivalence.py 2>&1 | tail -1
```

Expected: `14 passed, 1 skipped` (the skip reason names `UBYHOST_TEST_DATABASE_URL`); `All checks passed!`.

**Disposable PostgreSQL 16** (required; data dir under `/var/tmp`, port 5472, removed at the end):

```bash
B=/usr/lib/postgresql/16/bin; mkdir -p /var/tmp/pg1472 && chown postgres /var/tmp/pg1472
runuser -u postgres -- $B/initdb -D /var/tmp/pg1472/data -A trust -E UTF8 --locale=C.UTF-8 2>&1 | tail -1
runuser -u postgres -- $B/pg_ctl -D /var/tmp/pg1472/data -o '-p 5472 -k /var/tmp/pg1472 -c listen_addresses=' -l /var/tmp/pg1472/log start 2>&1 | tail -1
psql -h /var/tmp/pg1472 -p 5472 -U postgres -qc 'CREATE DATABASE ubyhost_test' && echo created; pg_dump --version
```

Expected: `server started`, `created`, `pg_dump (PostgreSQL) 16.x`. `-E UTF8` is required (Python refuses a non-UTF8 server). Then, from `App/`:

```bash
export UBYHOST_TEST_DATABASE_URL="postgresql://postgres@/ubyhost_test?host=/var/tmp/pg1472&port=5472"
env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_goose_equivalence.py -q -rs --tb=short 2>&1 | tail -3
```

Expected: `1 passed` and no `column order differs` warning. Then the **mutation check** (one line of goose 00016, then reverted):

```bash
grep -cF 'guest_details_mail BIGINT NOT NULL DEFAULT 1;' migrations_pg/00016_guest_details_mail.sql
sed -i 's/guest_details_mail BIGINT NOT NULL DEFAULT 1;/guest_details_mail BIGINT NOT NULL DEFAULT 0;/' migrations_pg/00016_guest_details_mail.sql
env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_goose_equivalence.py -q --tb=short 2>&1 | grep -E 'guest_details_mail bigint|passed|failed' | tail -4
git checkout -- migrations_pg/00016_guest_details_mail.sql; git status --short migrations_pg | wc -l
env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_goose_equivalence.py -q --tb=short 2>&1 | tail -1
```

Expected: `1`; then `-    guest_details_mail bigint DEFAULT 1 NOT NULL`, `+    guest_details_mail bigint DEFAULT 0 NOT NULL` (plus one `assert not [...]` line naming them) and `1 failed`; then `0`; then `1 passed`. If the mutated run passes, the test is broken: STOP. Then stop and delete the server:

```bash
runuser -u postgres -- /usr/lib/postgresql/16/bin/pg_ctl -D /var/tmp/pg1472/data stop 2>&1 | tail -1; rm -rf /var/tmp/pg1472; unset UBYHOST_TEST_DATABASE_URL
```

If PostgreSQL cannot be started, write "PostgreSQL run: not done" in the report and set `Status: blocked`.

From the repo root: `python3 scripts/context_lint.py 2>&1 | grep -v '^WARN' | tail -3` shows `context lint: OK`.

## 7. Acceptance

- [ ] Step 0 `has-00017`; step 1 hash matches; step 2 applied and `yaml ok`.
- [ ] §6: skip without URL; `1 passed` on PostgreSQL; the mutation made it fail with the two `guest_details_mail` lines and was reverted (`git status --short migrations_pg` empty); server stopped and `/var/tmp/pg1472` gone.
- [ ] `git log --oneline --grep='^1472 step'` lists steps 1, 2 and 4; `git show --stat` of step 1 = only the test file, step 2 = only `ci.yml` (10+, 1-), step 4 = only the report and this brief's Status line.
- [ ] When the branch's PR runs CI, `test-postgres`: step "pg_dump from the PostgreSQL service image" prints `pg_dump (PostgreSQL) 17`; "Run PostgreSQL tests" passes with 0 skipped and the log names `test_goose_equivalence.py` as passed (one more test than on main).

## 8. Stop and ask

Stop, and write the report, if: a step's expected value differs where it says STOP; a test fails twice (the new test failing on main with the mutation reverted means a real drift: copy its diff lines into the report and never add an allowlist); the CI wrapper step fails (report its log lines; do not install a PostgreSQL client package, that is a new dependency); you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1472-report.md` (600 tokens at most) and set `Status: review`. It has: the files changed (`git show --stat` of each `1472 step` commit), each command with its last 5 lines, §7 ticked, Deviations, Questions, Owner steps left.

## Risk list (for the reviewer)

Full diff of `App/tests/test_goose_equivalence.py` (only throwaway databases; `normalise()` sorts column lines only inside `CREATE TABLE` blocks and drops only comments, blanks and `\restrict` lines; a too-old or missing `pg_dump` fails, never skips) and `.github/workflows/ci.yml` (only job `test-postgres` changes; the wrapper runs the service image's `pg_dump`; the skip check still covers the new file).

## Owner steps

None. Merge with `scripts/merge-pr-on-green.sh` once CI is green.
