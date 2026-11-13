# 1260: Go schema command `ubyhost-web migrate plan|check|apply`

Status: review
Depends on: none | Base commit: a83df54 | Branch: task/1260-go-schema-migrate
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens
Tier A (migrations). Plan: docs/plans/go-full-move.md Lane D, step D1. Next: brief 1261 (deploy switch).

## 1. Objective

Add a Go port of `App/scripts/pg_schema.py plan|check|apply --expect-database <db>` as `ubyhost-web migrate ...`, with Python golden fixtures and a PostgreSQL parity test that runs Python and Go on the same database. Nothing calls the Go command yet (brief 1261 adds the deploy switch, default off), so this PR changes no production behaviour.

## 2. Context

The code lives in `docs/tasks/1260-files/code.md` (outside the brief token cap); do not open it: the step 1 command reads it for you. All code was written and dry-run by the brief writer on base a83df54 (Go 1.25.14, Python 3.13, PostgreSQL 16). You only copy it: the step 1 command extracts every file from code.md, and step 2 checks each sha256. Do not retype any file by hand.

What the code does (for the reviewer; you need not read further than this):

- `go/internal/schema/statements.go`: exact port of `App/app/db.py` `_goose_up_statements`, `_plain_goose_statements`, `_statements` and SQLite's `sqlite3_complete` (used by Python through `sqlite3.complete_statement`).
- `target.go`: exact port of `App/app/config.py` `_postgres_target` and `_database_target_fingerprint` (with the needed parts of Python's `urlsplit`, `parse_qsl`, `unquote`, `posixpath.normpath`, `json.dumps`). Non-ASCII hosts are refused (Python accepts them after an NFKC check); a refusal can never let a wrong target through.
- `authority.go`: the marker checks of `pg_schema.py` plus `config.assert_database_authority` (format_version 1, backend postgresql, database, schema public, target_fingerprint). Go reads `UBYHOST_DATA_DIR/database-authority.json`; no marker means no fence, as in Python. Go runs the full marker check for plan, check and apply (Python's check skips the fingerprint; Go is stricter).
- `expected.go`: port of the `current` rule of `db.postgres_schema_status` against an embedded snapshot `expected_schema.json` (Go has no SQLite). The snapshot is written by `App/scripts/pg_schema_golden.py` from Python's own `_expected_sqlite_columns`, `expected_schema_version`, `migration_files`, `SCHEMA`.
- `migrate.go`: `Run`. Connects with pgx, sets the same session settings as `db_postgres` (statement_timeout 60000, lock_timeout 30s, UTC, search_path public), requires current_schema public, checks the marker, requires current_database == --expect-database. `plan` prints pending goose versions. `check` = status current and no goose pending. `apply` takes session advisory locks 593217222 then 593217221, BEGIN, refuses unless `goose_db_version` and `schema_migrations` exist and version 1 is applied ("legacy schema not set up; run App/scripts/pg_schema.py apply once"), runs each pending goose file's Up statements one by one and inserts `goose_db_version (version_id, is_applied) VALUES (v, true)`, then checks the schema inside the transaction and COMMITs only when it is current. Any error rolls back and exits 1. A fresh empty database stays a Python-only job.
- `goose.go`: one line, `appliedVersions` takes the new `Querier` interface (a `*pgx.Conn` or a `pgx.Tx`) so apply can read inside its transaction. `Files` and `Pending` are unchanged.
- `go/cmd/ubyhost-web/register_schema.go`: `checkSchema` unchanged; adds an `init()` that runs `runMigrate` and exits when `os.Args[1] == "migrate"`, so `main.go` stays untouched. Output lines match `pg_schema.py` ("PostgreSQL schema apply OK: database=..., version=..., tables=..., goose=N."; errors "PostgreSQL schema <action> failed: ..." with the URL redacted). Usage errors exit 2. Default migrations dir `App/migrations_pg` like main.go; the image sets `UBYHOST_MIGRATIONS_DIR=/app/migrations_pg`.
- `App/scripts/pg_schema_golden.py`: writes the 3 JSON fixtures; `--check` writes nothing and exits 1 when one is stale. `App/tests/test_go_schema_golden.py` fails when they are stale (message names the regen command) and proves, with a fake connection, that the snapshot satisfies Python's own `postgres_schema_status`.
- `App/tests/test_go_schema_migrate.py`: parity test. Skips unless `UBYHOST_TEST_DATABASE_URL` or a PostgreSQL `UBYHOST_DATABASE_URL` is set and `go` is on PATH. In CI it runs in job `test-postgres-full` (it sets `UBYHOST_DATABASE_URL`, and ubuntu-latest has Go). It builds ubyhost-web, makes its own throwaway databases, runs Python apply + seal-authority, undoes the last two goose files (Down + their goose_db_version rows), then: Go plan lists exactly those two, Go apply restores them, Python check and Go check pass with identical output, the applied set equals Python's, a second Go apply is a no-op, a wrong --expect-database fails, a URL with another loopback host fails the fingerprint, a dropped column fails both checks, and Go apply on an empty database refuses and creates nothing.

`App/migrations_pg/00001_baseline.sql` cannot be parsed by Python's `_goose_up_statements` ("migration ends with an incomplete statement"); Python never parses it (apply records version 1 directly). The golden records that error and Go reproduces it; Go apply never runs version 1.

## 3. Files

| Path | Action | What |
|---|---|---|
| go/internal/schema/goose.go | edit | one line: `appliedVersions(ctx, conn Querier)` |
| go/internal/schema/statements.go | new | goose/SQLite statement splitter |
| go/internal/schema/target.go | new | URL target + fingerprint |
| go/internal/schema/authority.go | new | authority marker checks |
| go/internal/schema/expected.go | new | snapshot + status compare |
| go/internal/schema/migrate.go | new | plan/check/apply |
| go/internal/schema/golden_test.go | new | parser, SQLite-complete, fingerprint vs Python golden |
| go/internal/schema/expected_test.go | new | compare, authority, refusal tests |
| go/internal/schema/expected_schema.json | new (generated, step 3) | embedded snapshot |
| go/internal/schema/testdata/goose_statements_golden.json | new (generated, step 3) | parser golden |
| go/internal/schema/testdata/fingerprint_golden.json | new (generated, step 3) | fingerprint golden |
| go/cmd/ubyhost-web/register_schema.go | edit (full content below) | migrate dispatch + runMigrate |
| go/cmd/ubyhost-web/register_schema_test.go | new | arg parsing, usage, redaction |
| App/scripts/pg_schema_golden.py | new | golden writer |
| App/tests/test_go_schema_golden.py | new | fixtures fresh + Python cross-check |
| App/tests/test_go_schema_migrate.py | new | PostgreSQL parity test |
| docs/tasks/1260-report.md | new | your report |
| docs/tasks/1260-files/code.md | exists (read by step 1 only) | code payload; do not edit |
| docs/tasks/1260-go-schema-migrate.md, docs/tasks/1261-go-schema-deploy-switch.md | exist | the briefs; only the Status line of 1260 changes |

No other file may change.

## 4. Steps

**Step 1. Extract the files.** From the repo root, run exactly:

```bash
python3 - docs/tasks/1260-files/code.md <<'EOF' 2>&1 | tail -30
import re, sys, pathlib
text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
blocks = re.findall(r"<!-- file: (\S+) -->\n~~~~[a-z]*\n(.*?)\n~~~~\n", text, re.S)
assert len(blocks) == 12, len(blocks)
for path, body in blocks:
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body + "\n", encoding="utf-8")
    print("wrote", path)
EOF
```

Expected: 12 lines `wrote <path>`. Then make the one-line goose.go edit:

```bash
grep -nF 'func appliedVersions(ctx context.Context, conn *pgx.Conn) (map[int]bool, error) {' go/internal/schema/goose.go 2>&1 | tail -3
sed -i 's/^func appliedVersions(ctx context.Context, conn \*pgx.Conn) (map\[int\]bool, error) {$/func appliedVersions(ctx context.Context, conn Querier) (map[int]bool, error) {/' go/internal/schema/goose.go
```

The grep must print line 72. Not found: STOP (§8).

**Step 2. Verify every file.** Run:

```bash
sha256sum -c <<'EOF' 2>&1 | tail -30
d4f09194d8fc1c436abc50aa9f430792c138303f486cdec4780cc3401cc80fcc  go/internal/schema/goose.go
ea0cdb5b6ed8d2fff27914f397f4a1403647b65177f6ad5ace49e25cf14305f6  go/internal/schema/statements.go
75093ff7865d295db55fa635ab46a225678588b5ffe0e5a3ff305fe18b75543b  go/internal/schema/target.go
f35fec4aee168718143430c55f80e7f22c6b14251109b62cc61edf8f89dfa3e3  go/internal/schema/authority.go
8b83c6bebf4b5a713fa63780706cd6350761466e8df663e3673f374a5f02240c  go/internal/schema/expected.go
891bed5bfff44b318727aaacd59632fda729edbcfe80e8a5fc5681aca5651ffc  go/internal/schema/migrate.go
16a42c738a2ca547415a381bd771f58cf71a69c439218dd4cc29963b8a480388  go/internal/schema/golden_test.go
0d1747f698863db1942901ec111c84c0884442355e0e3ac3a6d4de78ab0a42c3  go/internal/schema/expected_test.go
90eb051df6e55d321bcf3735e9f2baefda053c1b9b264d6d12467b6b7a988c2c  go/cmd/ubyhost-web/register_schema.go
eac3be713c84427f1d040930c15d48b00c565e9963294c8b2768ac8573904a80  go/cmd/ubyhost-web/register_schema_test.go
ea6cd6b0e9471fc8ce2022a65b1bf88db3fc942adfbba92cf0711946782e6ed4  App/scripts/pg_schema_golden.py
1e384bb4034dd26f1601e4ac99f75ab9302c3d6ff47734b7f705946ca87b9254  App/tests/test_go_schema_golden.py
13d70cbfd7b214c858336b07633b3eb1df200df24292391d02a2c399d94a101b  App/tests/test_go_schema_migrate.py
EOF
```

Expected: 13 lines ending `OK`. Any `FAILED`: rerun step 1 once for that file; still failing: STOP. Commit: `git add go/internal/schema go/cmd/ubyhost-web/register_schema.go go/cmd/ubyhost-web/register_schema_test.go App/scripts/pg_schema_golden.py App/tests/test_go_schema_golden.py App/tests/test_go_schema_migrate.py && git commit -m "1260 step 1-2"`.

**Step 3. Generate the fixtures.** From `App/` (create the venv first only if `App/.venv` is missing: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt 2>&1 | tail -3`):

```bash
cd App && env -u UBYHOST_DATABASE_URL -u UBYHOST_TEST_DATABASE_URL .venv/bin/python scripts/pg_schema_golden.py 2>&1 | tail -5
```

Expected: three lines `wrote: go/internal/schema/...json`. Then from the repo root:

```bash
sha256sum -c <<'EOF' 2>&1 | tail -5
36f344cb17fbe23e6e626f18dd5fe233e1418d3ee0f6eee4ad11553e4648bff3  go/internal/schema/expected_schema.json
08e06479b256bcff21ce6af4c350e77383701913e82f04ade8ddf29dd243e341  go/internal/schema/testdata/goose_statements_golden.json
2559691f70839427afbeceee6c20777d24eea834677e82b52d34a03ed3880e9d  go/internal/schema/testdata/fingerprint_golden.json
EOF
```

Expected: 3 x `OK`. A mismatch means main changed under you (a new goose or migrations file): that is fine only if `git log --oneline a83df54..HEAD -- App/migrations_pg App/app/migrations App/app/db.py` lists a commit; write that in Deviations and go on. Otherwise STOP. Commit: `git add go/internal/schema && git commit -m "1260 step 3"`.

**Step 4. Go checks** (from `go/`; the go.mod toolchain line may download go1.25.14 the first time):

```bash
cd go && test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/schema ./cmd/ubyhost-web -count=1 2>&1 | tail -30
```

Expected: `ok .../internal/schema` and `ok .../cmd/ubyhost-web`. Then `go build ./cmd/ubyhost-web && rm -f ubyhost-web`.

**Step 5. Python checks** (from `App/`): run the §6 commands. Commit anything left with `git commit -am "1260 step 5"` (normally nothing).

**Step 6.** Write the report (§9).

## 5. Do not touch

- `go/cmd/ubyhost-web/main.go`, `go/internal/jobs/`, `go/internal/hostweb/`, `go/internal/session/`, `App/app/**`, `App/tests/conftest.py`, `App/migrations_pg/`, `App/scripts/pg_schema.py`, `.github/workflows/ci.yml`, `go/go.mod`, `go/go.sum`, `deploy/` (brief 1261).
- `docs/ENVIRONMENT.md`, `docs/context/*` (coordinator-only).
- Hard rules: 3 (no secrets, no database files: never `git add` anything under `/var/tmp` or a `.env`), 4 (no new dependency: pgx v5 is already in go.mod), 8 (never push to main).

## 6. Commands

From `App/`:

```bash
env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_go_schema_golden.py -q --tb=short -x 2>&1 | tail -30
```

Expected: `4 passed`.

```bash
env -u UBYHOST_DATABASE_URL .venv/bin/python scripts/pg_schema_golden.py --check; echo "check exit $?" 2>&1 | tail -3
```

Expected: `check exit 0`.

```bash
env -u UBYHOST_DATABASE_URL .venv/bin/python -m pytest tests/test_go_schema_migrate.py -q -rs --tb=short 2>&1 | tail -30
```

Expected without a PostgreSQL URL: `2 skipped` (CI job `test-postgres-full` runs it). If you have a disposable PostgreSQL, run it with `UBYHOST_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:<port>/ubyhost_test` instead: expected `2 passed`. The writer's dry run: `2 passed` on PostgreSQL 16.

```bash
.venv/bin/ruff check scripts/pg_schema_golden.py tests/test_go_schema_golden.py tests/test_go_schema_migrate.py --select E9,F63,F7,F82,F401,F841 2>&1 | tail -3
```

Expected: `All checks passed!`. From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -3` ends `context lint: OK`.

## 7. Acceptance

- [ ] Step 2: 13 x OK; step 3: 3 x OK (or the documented goose-change deviation).
- [ ] `gofmt -l .` empty, `go vet ./...` clean, `go test ./internal/schema ./cmd/ubyhost-web` ok.
- [ ] `test_go_schema_golden.py` 4 passed; `pg_schema_golden.py --check` exit 0; `test_go_schema_migrate.py` 2 skipped (or 2 passed with PostgreSQL).
- [ ] `git diff --stat a83df54..HEAD` lists only §3 files.
- [ ] After push: CI `go`, `test` and `test-postgres-full` green; in `test-postgres-full` the two `test_go_schema_migrate.py` tests PASS, not skip (orchestrator checks the junit artifact or log).

## 8. Stop and ask

Stop, and write the report, if:

- an anchor or sha256 does not match (except the step 3 case named there);
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1260-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat a83df54..HEAD`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read the full diff of: `go/internal/schema/migrate.go` (locks, transaction, legacy refusal, commit-only-when-current), `authority.go`, `target.go` (fingerprint must equal Python's or every Go run is refused on production), `statements.go` (statement split = what runs), `go/cmd/ubyhost-web/register_schema.go` (init dispatch must not fire for normal starts), `App/tests/test_go_schema_migrate.py` (drops only its own `ubyhost_go_migrate_<pid>_*` databases).

## Owner steps

None for this PR: nothing calls `ubyhost-web migrate` until brief 1261. Merge when CI is green (the orchestrator gives the link).

## Notes for the coordinator (lines to add; threads do not edit these files)

- `docs/context/test-map.md` new row: `| Go schema command (go/internal/schema, ubyhost-web migrate) | go test ./internal/schema ./cmd/ubyhost-web; tests/test_go_schema_golden.py; tests/test_go_schema_migrate.py (needs a PostgreSQL URL and go; runs in CI test-postgres-full) |`
- `docs/context/rules.md#database` (or test-map) one line: `A new goose file or App/app/migrations file: also run cd App && .venv/bin/python scripts/pg_schema_golden.py and commit the three JSON files in go/internal/schema, or test_go_schema_golden.py and the Go tests fail.` Tell every running thread that adds a goose file.
- `docs/context/decisions.md`: `[schema] 2026-11-13 Go ubyhost-web migrate ports pg_schema.py plan/check/apply (goose files only, expected schema as an embedded Python-made snapshot, commit only when current); fresh databases and pg-cutover stay Python. Brief 1260.`