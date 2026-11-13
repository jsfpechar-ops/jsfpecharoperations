# 1262: Go schema fix 1 (review findings on PR #982)

Status: todo
Depends on: 1260, 1261 (same PR #982) | Base commit: 36ab7a1 | Branch: task/1260-go-schema-migrate
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier A (migrations).

## 1. Objective

Close the five review findings on PR #982: Go check/apply must fail closed when the functions and triggers that only Python re-creates are out of date, the docs must say exactly when Go can take over, the parity test must not skip silently in CI, a failing goose file must be proven to roll back, and `migrate` must accept the option before the action like argparse.

## 2. Context

All changes are in one patch, `docs/tasks/1262-files/fix.patch` (made with `git diff` on 36ab7a1); do not open it, step 1 applies it. It was written and dry-run by the brief writer (Go 1.25.14, Python 3.13, PostgreSQL 16). What it does, for the reviewer:

1. **Python-owned DDL.** Python's apply re-runs `CREATE OR REPLACE FUNCTION` for `PG_SQLITE_DATE_FUNCTION` and the six `PG_TRIGGERS`, and re-creates the six triggers (`App/app/db_postgres.py` `install_pg_support`); Go applies goose files only. `App/scripts/pg_schema_golden.py` now also writes `functions` (name to the text between the `$$` quotes, which equals `pg_proc.prosrc` verbatim: checked on PostgreSQL 16 for all 7) and `trigger_defs` (name to `CREATE TRIGGER <name> <event> ON public.<table> FOR EACH ROW EXECUTE FUNCTION <function>()`, which equals `pg_get_triggerdef(oid)` with search_path public) into `go/internal/schema/expected_schema.json`. `expected.go` reads `pg_proc` and `pg_get_triggerdef` for the public schema; a missing function, a second function of the same name, a different body or a different trigger definition makes the status not current (`Status.PythonDDLStale()`). `migrate.go` then fails `check` and `apply` (apply rolls back) with `PostgreSQL functions or triggers differ from the app's (Python-owned DDL); run App/scripts/pg_schema.py apply once (deploy with UBYHOST_SCHEMA_APPLY=python), then switch back`. Python's own check compares trigger names only and does not see this; the new parity test shows Go failing, Python apply restoring, Go passing.
2. **Wording.** `deploy.sh` (switch comment) and `docs/LIGHTSAIL.md` (Rollback paragraph) now say: Python can always take over from Go; Go can take over from Python while those functions and triggers match; otherwise Go fails closed and the deploy stops before `up`, and one deploy with `python` fixes it.
3. **No silent skip.** `App/tests/test_go_schema_migrate.py` skips only without a PostgreSQL URL. Without `go` it skips locally but fails when env `CI` is set (GitHub sets `CI=true`). The build sets `GOTOOLCHAIN=auto` when unset, so the runner's preinstalled Go downloads the go1.25.14 toolchain that go.mod's `toolchain` line asks for (the CI `go` job already relies on this).
4. **Rollback test.** New `test_go_apply_rolls_back_a_failing_goose_file`: copies the goose files to a temp dir, adds a valid next file (creates a table) and a failing one after it (adds a column, then invalid SQL). Go apply exits 1 naming the failing version, and the `goose_db_version` rows, the probe table and the probe column are all unchanged; Go check still passes.
5. **Argument order.** `register_schema.go` replaces the Go `flag` parsing with `parseMigrateArgs`: one action and `--expect-database <db>` or `--expect-database=<db>`, in any order (the last one wins, like argparse); anything else exits 2 with the usage line. The parity test runs one Go check as `migrate --expect-database <db> check`.

Writer's dry run: `go test ./...` all ok (schema + cmd: 28 top-level tests pass); `test_go_schema_golden.py` 5 passed; `test_go_schema_migrate.py` 4 passed on PostgreSQL 16 (with `UBYHOST_TEST_DATABASE_URL` and with `UBYHOST_DATABASE_URL`), 4 errors with `CI=true` and no `go`, 4 skipped without `go`; `pg_schema_golden.py --check` exit 0; ruff (CI rules) and `shellcheck -S error` clean. CI runs PostgreSQL 17: the 4 parity tests there prove the prosrc and triggerdef forms on 17.

## 3. Files

| Path | Action | What |
|---|---|---|
| go/internal/schema/expected.go | edit (patch) | functions + trigger defs: snapshot, read, compare |
| go/internal/schema/migrate.go | edit (patch) | fail closed on Python-owned DDL |
| go/internal/schema/expected_test.go | edit (patch) | drift cases |
| go/internal/schema/expected_schema.json | regenerate (step 2) | adds `functions`, `trigger_defs` |
| go/cmd/ubyhost-web/register_schema.go | edit (patch) | `parseMigrateArgs` |
| go/cmd/ubyhost-web/register_schema_test.go | edit (patch) | order cases |
| App/scripts/pg_schema_golden.py | edit (patch) | write functions + trigger defs |
| App/tests/test_go_schema_golden.py | edit (patch) | snapshot covers the 7 functions and 6 triggers |
| App/tests/test_go_schema_migrate.py | edit (patch) | CI fail, DDL drift test, rollback test, option-first |
| deploy/lightsail/scripts/deploy.sh | edit (patch) | comment only |
| docs/LIGHTSAIL.md | edit (patch) | Rollback paragraph |
| docs/tasks/1262-report.md | new | your report |
| docs/tasks/1262-go-schema-fix-1.md, docs/tasks/1262-files/fix.patch | exist | this brief (Status line only) and the patch |

No other file may change.

## 4. Steps

**Step 1. Apply the patch** (repo root):

```bash
git apply --check docs/tasks/1262-files/fix.patch && git apply docs/tasks/1262-files/fix.patch && git status --short 2>&1 | tail -15
```

Expected: 10 files ` M` (expected_schema.json is not among them yet). If `git apply --check` fails: STOP (§8); do not use `--reject` and do not edit by hand.

**Step 2. Regenerate the snapshot** (from `App/`; create `.venv` only if it is missing: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3`):

```bash
cd App && env -u UBYHOST_DATABASE_URL -u UBYHOST_TEST_DATABASE_URL .venv/bin/python scripts/pg_schema_golden.py 2>&1 | tail -5
```

Expected: exactly `wrote: go/internal/schema/expected_schema.json`.

**Step 3. Verify** (repo root):

```bash
sha256sum -c <<'EOF' 2>&1 | tail -15
681871470fbe50c02f58b6ae43cb10060d0262a9bff4b3b0c92a256fba9fbde2  App/scripts/pg_schema_golden.py
91337acd4cbe130619a34ec70d9ccf155b21aab1e9457c4ae2613964e0869438  App/tests/test_go_schema_golden.py
f5c5904477e65576792f9662773c755039d9d456286afd28d4ae4d6dd9b98de3  App/tests/test_go_schema_migrate.py
440210a8b03f589a427f01784d12a31386dd231d52e36e4f49580f14e209df22  deploy/lightsail/scripts/deploy.sh
6fb6c1064f1b7e54ecd729eb0a0a9662d99cebb25142cba9d3eb52fd2ff992d9  docs/LIGHTSAIL.md
d5660b6b8049ce8a16444101982f1a7dc1877750f1f887f776e97b9a34af236e  go/cmd/ubyhost-web/register_schema.go
b85ae8639271cf08084f862eb9deeb88f9cd04209b480a31786ee97f7f32a55c  go/cmd/ubyhost-web/register_schema_test.go
f1d2ac190d5fc3eedef6a70070abae33ab486cf1d36d3ee943923b229fcfda47  go/internal/schema/expected.go
ab39d68a512c5661ab960ebd9b06f2c6ff326803c64460c4303ed44d55dcc87b  go/internal/schema/expected_test.go
92a1fc27a8a17c019c0e4cda0139e43dc085f90e3f3a00671824855ab5765217  go/internal/schema/migrate.go
fc8876b53e9b1b039a93c09799e65d544c109b1a842d08090690fed84f21af40  go/internal/schema/expected_schema.json
EOF
```

Expected: 11 x `OK`. A `FAILED` on expected_schema.json alone is fine if `git log --oneline 36ab7a1..HEAD -- App/migrations_pg App/app/migrations App/app/db.py App/app/db_postgres.py` lists a commit (write it in Deviations); any other `FAILED`: STOP. Then commit:

```bash
git add go/internal/schema go/cmd/ubyhost-web App/scripts/pg_schema_golden.py App/tests/test_go_schema_golden.py App/tests/test_go_schema_migrate.py deploy/lightsail/scripts/deploy.sh docs/LIGHTSAIL.md && git commit -m "1262 step 1-3" 2>&1 | tail -3
```

**Step 4.** Run §6. **Step 5.** Write the report (§9) and commit it with the message `1262 step 5: report`.

## 5. Do not touch

`go/cmd/ubyhost-web/main.go`, `go/internal/jobs/`, `App/app/**`, `App/tests/conftest.py`, `App/migrations_pg/`, `.github/workflows/ci.yml`, `go/go.mod`, `docs/context/*`, `docs/ENVIRONMENT.md`. Rules 3, 4 and 8: no secrets, no new dependency, never push to main.

## 6. Commands

```bash
cd go && test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/schema ./cmd/ubyhost-web -count=1 2>&1 | tail -5
```

Expected: two `ok` lines. From `App/`:

```bash
env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_go_schema_golden.py -q --tb=short 2>&1 | tail -3
env -u UBYHOST_DATABASE_URL .venv/bin/python scripts/pg_schema_golden.py --check; echo "check exit $?"
env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_go_schema_migrate.py -q -rs --tb=short 2>&1 | tail -6
.venv/bin/ruff check scripts/pg_schema_golden.py tests/test_go_schema_golden.py tests/test_go_schema_migrate.py --select E9,F63,F7,F82,F401,F841 2>&1 | tail -2
bash -n ../deploy/lightsail/scripts/deploy.sh && echo syntax ok
```

Expected: `5 passed`; `check exit 0`; `4 skipped` without a PostgreSQL URL (with `UBYHOST_TEST_DATABASE_URL` pointing at a disposable server: `4 passed`); `All checks passed!`; `syntax ok`. From the repo root, `python3 scripts/context_lint.py 2>&1 | tail -1` shows `context lint: OK`.

## 7. Acceptance

- [ ] Step 1: patch applied cleanly; step 3: 11 x OK (or the documented snapshot deviation).
- [ ] §6 all as expected.
- [ ] `git diff --stat 36ab7a1..HEAD` lists only §3 files.
- [ ] After push, CI `test-postgres-full`: the 4 `test_go_schema_migrate.py` tests PASS (not skip); `go`, `test` and `shellcheck` green.

## 8. Stop and ask

Stop, and write the report, if: the patch does not apply; a sha256 fails (except the step 3 case); a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a file outside §3 needs a change; §5 would be touched; a step is unclear; you need push, merge, secrets, SSH or deploy.

## 9. Report

Write `docs/tasks/1262-report.md` (600 tokens at most) and set `Status: review`. It has: the files changed (`git diff --stat 36ab7a1..HEAD`), each command with its last 5 lines, §7 ticked, Deviations, Questions, Owner steps left.

## Risk list (for the reviewer)

Full diff of `go/internal/schema/expected.go` and `migrate.go` (the new rule may only add refusals, never accept more), `go/cmd/ubyhost-web/register_schema.go` (`parseMigrateArgs`), `App/tests/test_go_schema_migrate.py` (the CI fail path; the probe migrations live in a temp dir only).

## Owner steps

None new. Brief 1261's owner steps stay valid; the LIGHTSAIL Rollback paragraph now names the one case that needs a Python deploy.

## Notes for the coordinator

- `docs/context/known-issues.md` or decisions: `[schema] Go migrate applies goose files only; a PR that changes ubyhost_sqlite_date or an invoice guard in App/app/db_postgres.py (function body or trigger) makes Go check/apply fail closed until one deploy with UBYHOST_SCHEMA_APPLY=python. Brief 1262.`
