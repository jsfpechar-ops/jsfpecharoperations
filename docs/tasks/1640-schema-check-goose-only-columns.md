# 1640: Python and Go schema checks accept columns that only a goose file adds

Status: blocked — owner decision: run this as port plumbing (go-first exception 1) now, or wait for 1474 (sqlite-retirement S6, not written yet). Not runnable until the owner picks.
Depends on: owner decision above | Base commit: bdfaa4d4 when cut | Branch: none yet
Executor: Haiku 5.5 | Not runnable. Tier A (schema check; a wrong change stops the app at boot). The brief writer is Opus (go-first: tier A).

## 1. Objective

Make a goose-only `ALTER TABLE ... ADD COLUMN` (no SQLite twin) pass Python's `db.postgres_schema_status()` and Go's embedded check, so [1641](1641-entry-code-schema.md) can add four `apartment` columns without the Python app refusing to start. Without this, every goose-only column is a production outage (rules.md §Database: "A goose-only file that adds a column is untried against Python's schema check until plan step S6").

## 2. Context (verified on bdfaa4d4)

The expected columns come from SQLite only, `App/app/db.py:1288`:

```python
        expected = _expected_sqlite_columns()
```

and any column-count difference is a mismatch, `App/app/db.py:1311-1313`:

```python
            if len(expected_cols) != len(actual_cols):
                column_mismatches += abs(len(expected_cols) - len(actual_cols)) or 1
                continue
```

`"current"` (`db.py:1357`) needs `column_mismatches == 0`; when it is false, startup raises `"PostgreSQL schema is absent, outdated, or incompatible; ..."` (`db.py:1427-1430`). `go/internal/schema/expected_schema.json` is "the schema postgres_schema_status expects" (`App/scripts/pg_schema_golden.py` docstring), so Go's check has the same gap. No goose file so far adds a column without a SQLite twin: `00017_goose_parity.sql` only alters constraints and collations; `00016` is a twin (inserts its `schema_migrations` row).

## 3. Files

`App/app/db.py` (exception 1: port plumbing a Go brief needs), `App/scripts/pg_schema_golden.py` and its outputs under `go/internal/schema/`, one test in `App/tests/test_db_postgres.py` or a new `App/tests/test_goose_only_columns.py`.

## 4. Steps

Proposed cut (tier A, written by Opus when approved):

1. In `postgres_schema_status`, after `expected = _expected_sqlite_columns()`, append the columns that goose-only files add, in file order (goose-only = a file under `App/migrations_pg/` numbered above 17 that does not insert a `schema_migrations` row), parsed from `ALTER TABLE <t> ADD COLUMN [IF NOT EXISTS] <name> <TYPE>` with the type mapped like `expected_types`. Order matters: the check zips by position, and PostgreSQL appends added columns at the end.
2. Same list in `pg_schema_golden.py` so `expected_schema.json` carries them; `go test ./internal/schema/...` green.
3. Test on a throwaway PostgreSQL: a temporary goose-only file with one `ADD COLUMN` → `current` stays true; a column added by hand without a goose file → still a mismatch.
4. Check against 1474 (S6) so the two do not fight; if 1474 is written first and covers this, close 1640.

## 5. Do not touch

Everything until the owner decides. Do not run this brief.

## 6. Commands

None until cut.

## 7. Acceptance

- [ ] Not applicable until the brief is cut.

## 8. Stop and ask

Stop at once: the brief is blocked.

## 9. Report

None.

## Risk list (for the reviewer)

`App/app/db.py` `postgres_schema_status` (boot gate), `go/internal/schema/expected_schema.json`.

## Owner steps

1. Decide: approve 1640 as go-first exception 1 (plumbing), or wait for 1474 (S6). Write the line in `docs/context/decisions.md`.
