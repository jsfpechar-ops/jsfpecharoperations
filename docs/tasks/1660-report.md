# 1660 report

Status: review

## Files changed
- `App/app/db.py` — parse goose-only ADD COLUMN from migrations_pg (>17, no schema_migrations twin)
- `App/scripts/pg_schema_golden.py` — comment ties golden to parsed expectations
- `App/scripts/sqlite_to_postgres.py` — `goose_only_columns()`
- `App/tests/test_goose_only_columns.py` — parsing + PostgreSQL cases

## Commands
```text
cd App && .venv/bin/python -m pytest tests/test_goose_only_columns.py::test_goose_only_columns_parsed_from_migrations tests/test_go_schema_golden.py tests/test_migrations.py -q --tb=short -x
# 20 passed in 3.59s (tail)

cd go && go test ./internal/schema/...
# ok github.com/.../go/internal/schema 0.058s (tail)

cd App && .venv/bin/python -m pytest tests/test_goose_only_columns.py tests/test_db_postgres.py tests/test_goose_migrations.py -q --tb=short -x
# 3 passed, 61 skipped (no UBYHOST_DATABASE_URL)
```

## Acceptance (§7)
- [x] Goose-only ADD COLUMN parsed and included in `postgres_expected_columns` / Go golden
- [x] Unit + go schema tests green
- [ ] PostgreSQL integration cases (need test DB URL in environment)

## Deviations
Brief §6 had no commands (precut); used test-map database row. PG-only tests skipped without `UBYHOST_DATABASE_URL`.

## Questions
None.

## Owner steps
Run PostgreSQL test subset with `UBYHOST_DATABASE_URL` before merge.