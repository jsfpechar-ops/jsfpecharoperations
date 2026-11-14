# 1641: Goose 00018 — apartment entry code + external guide URL columns, export guard

Status: blocked — waits for 1640 (or 1474) so the new columns do not stop the Python app at boot
Depends on: 1640 | Base commit: bdfaa4d4 | Branch: task/1641-entry-code-schema
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens | Tier A (migrations): brief reviewed as exact diff

## 1. Objective

Add four nullable columns to `apartment` with one additive goose file, regenerate the schema golden, prove both schema checks still pass on the migrated database, and add a Go guard test that no export can carry `entry_code_enc`. No reader yet: Go briefs 1642-1647 use the columns. Python does not read them (owner 2026-11-14: Go only).

## 2. Context (verified on bdfaa4d4)

Rules (`docs/context/rules.md` §Database): schema changes are goose files only, next number = highest + 1. Highest today is `App/migrations_pg/00017_goose_parity.sql`, so this is `00018`. Goose files must be additive (the previous image keeps working; rules.md:47). `App/app/migrations/` is frozen at 0045; `db.SCHEMA` and `db.ADDED_COLUMNS` never change. After the file, rerun `App/scripts/pg_schema_golden.py` (no database needed; "Run from App/ after adding a goose or migrations file").

Goose header style, `App/migrations_pg/00017_goose_parity.sql:1-2`:

```sql
-- +goose Up
-- Goose parity (brief 1471, plan sqlite-retirement S2). Goose-only: no SQLite twin, no
```

Exports: no export reads `apartment` wholesale. Go `go/internal/web/exports/archived.go:45-47` selects named columns only:

```go
	archivedPropertiesSQL = `SELECT a.id, a.internal_name, a.archived_at,
		(SELECT COUNT(*) FROM reservation r WHERE r.apartment_id = a.id) AS reservations
		FROM apartment a
```

The `SELECT *` queries in that package read `guest` only (`form_pdf.go:91`, `guest_json.go:104`, `housebook.go:254`). Python `App/app/workspace_export.py` joins `apartment` only for filters and writes no apartment row. So this brief adds a guard test only, no export change.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/migrations_pg/00018_apartment_entry_code_guide_url.sql` | new | the SQL in step 1 |
| `go/internal/schema/expected_schema.json` and files under `go/internal/schema/testdata/` the script rewrites | regenerated | `App/scripts/pg_schema_golden.py` |
| `go/internal/web/exports/entry_code_guard_test.go` | new | step 4 |

No `App/app/` file changes. No other file may change.

## 4. Steps

1. Write the goose file exactly:

```sql
-- +goose Up
-- Building entry code and external guide link per apartment (brief 1641, plan entry-code-external-guide).
-- Goose-only: no SQLite twin, no schema_migrations row. Additive: the previous image ignores the columns.
-- entry_code_enc is Fernet ciphertext (never plaintext); entry_code_until is an ISO date or NULL.
ALTER TABLE apartment ADD COLUMN IF NOT EXISTS entry_code_enc TEXT;
ALTER TABLE apartment ADD COLUMN IF NOT EXISTS entry_code_label TEXT;
ALTER TABLE apartment ADD COLUMN IF NOT EXISTS entry_code_until TEXT;
ALTER TABLE apartment ADD COLUMN IF NOT EXISTS guide_external_url TEXT;

-- +goose Down
ALTER TABLE apartment DROP COLUMN IF EXISTS guide_external_url;
ALTER TABLE apartment DROP COLUMN IF EXISTS entry_code_until;
ALTER TABLE apartment DROP COLUMN IF EXISTS entry_code_label;
ALTER TABLE apartment DROP COLUMN IF EXISTS entry_code_enc;
```

2. From `App/`: `.venv/bin/python scripts/pg_schema_golden.py 2>&1 | tail -5`, then `git status -s | tail -20`. Only files under `go/internal/schema/` may change; anything else: STOP (§8). Then `cd ../go && go test ./internal/schema/... 2>&1 | tail -10`.
3. Boot check on a throwaway PostgreSQL 16 (the sandbox has the binaries; recipe from brief 1471 §2):

```bash
B=/usr/lib/postgresql/16/bin; rm -rf /tmp/pgt && mkdir -p /tmp/pgt/sock && chown -R postgres /tmp/pgt
runuser -u postgres -- $B/initdb -D /tmp/pgt/data -U postgres --auth=trust -E UTF8 >/dev/null
runuser -u postgres -- $B/pg_ctl -D /tmp/pgt/data -o "-k /tmp/pgt/sock -p 55433 -c listen_addresses=''" -l /tmp/pgt/log -w start
psql -h /tmp/pgt/sock -p 55433 -U postgres -c "CREATE DATABASE ubyhost_test"
export UBYHOST_TEST_DATABASE_URL='postgresql://postgres@/ubyhost_test?host=/tmp/pgt/sock&port=55433'
```

   From `App/`: `UBYHOST_DATABASE_URL="$UBYHOST_TEST_DATABASE_URL" .venv/bin/python scripts/pg_schema.py apply --expect-database ubyhost_test 2>&1 | tail -3`, then the same with `check`. Both must succeed (this is the Python boot gate; it fails before 1640). Then run the §6 PostgreSQL row with the variable set.
4. Guard test `go/internal/web/exports/entry_code_guard_test.go`: read every non-test `.go` file of the package (`os.ReadDir(".")`) and fail if any contains `entry_code` or matches `(?i)SELECT\s+(a\.)?\*\s+FROM\s+apartment`. Name it `TestNoExportReadsEntryCode`. `cd go && go test ./internal/web/exports/ -run TestNoExportReadsEntryCode 2>&1 | tail -10`.
5. Run §6, commit per step (`1641 step k`).

## 5. Do not touch

`App/app/` (all of it: Python does not read the columns), `App/app/migrations/` (frozen), any guest template, mail, retention (brief 1642), `.env`, secrets. Never `git add -A`; before each commit run `git diff --cached | grep -iE 'secret|token|api[_-]?key|password|AKIA|ghp_'` (expect nothing).

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_migrations.py tests/test_db_*.py tests/test_sqlite_migrations_frozen.py -q --tb=short -x 2>&1 | tail -30`
From `App/`, with `UBYHOST_TEST_DATABASE_URL` set: `.venv/bin/python -m pytest tests/test_go_schema_migrate.py tests/test_db_postgres.py -q --tb=short -x -rs 2>&1 | tail -30` (0 skipped; if PostgreSQL cannot start, say so in the report: CI `test-postgres-full` runs it)
From `App/`: `.venv/bin/python scripts/pg_schema_golden.py --check 2>&1 | tail -5`
From `go/`: `go test ./internal/schema/... ./internal/web/exports/... 2>&1 | tail -30`
From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -10`

## 7. Acceptance

- [ ] `00018_apartment_entry_code_guide_url.sql` is additive (only `ADD COLUMN IF NOT EXISTS`, nullable, no default) and has a Down section.
- [ ] `pg_schema.py apply` and `check` succeed on a fresh database; golden `--check` clean; `go test ./internal/schema/...` green.
- [ ] `TestNoExportReadsEntryCode` green; no `App/app/` file in `git diff --stat origin/main`.
- [ ] Secret grep of the staged diff prints nothing.

## 8. Stop and ask

Stop and write the report if: 1640 (or 1474) is not on main; `pg_schema.py check` reports a column mismatch (the boot gate would stop production); the golden script rewrites files outside `go/internal/schema/`; an excerpt is not found; a test fails twice; 25 tool calls or ~50k tokens; a file outside §3 needs a change; you need push, merge or deploy.

## 9. Report

`docs/tasks/1641-report.md` (≤600 tokens): `git diff --stat`, each command with its last 5 lines, §7 ticked, deviations, owner steps left. `Status: review`, one PR.

## Risk list (for the reviewer)

`App/migrations_pg/00018_apartment_entry_code_guide_url.sql` (runs on production at deploy), `go/internal/schema/expected_schema.json`.

## Owner steps

1. Nothing by hand: the deploy runs `pg_schema.py apply` (`deploy/lightsail/scripts/deploy.sh`, `UBYHOST_SCHEMA_APPLY` unset = python). The app refuses to start while a goose file is pending, so merge only on green.
