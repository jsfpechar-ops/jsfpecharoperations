# 0461 review findings: PR #592 runtime half (2026-10-31)

Read-only review (Opus pass, Fable verification of the TLS, timeout and lock items). Scope: `db.py`, `db_postgres.py`, `config.py`, `pg_schema.py`, `sqlite_to_postgres.py`, `test_db_postgres.py`. The ops half is out of scope (removed by D1).

Verdict: no blocker. Mergeable behind the `UBYHOST_DATABASE_URL` flag once the should-fix items below are done (brief 0461). The flag is not set in production until the full test suite has run green on PostgreSQL (brief 0462).

| Severity | Where | Issue | Fix |
|---|---|---|---|
| should-fix | config.py `_postgres_target`, db_postgres.py `connect` | Any `sslmode` accepted; a managed database over TCP could carry guest data in clear | Require `sslmode=verify-full` (or `require`) for TCP hosts |
| should-fix | db_postgres.py `connect` | No `connect_timeout`, no `statement_timeout` | `connect_timeout=10`, `statement_timeout=60000` |
| should-fix | db.py `_open`, `readonly_cursor` | One connection per thread plus one per read-only block, no pool | Write the connection budget (uvicorn workers × threads + worker + 2) into the managed-tier choice (step 8 brief) |
| should-fix | tests | No test runs the real app suite on PostgreSQL; dialect errors (`GROUP BY` bare columns, text vs int comparison, NULL ordering, `LIKE` → `ILIKE` on Czech letters) can only surface there | Brief 0462: CI job running `pytest tests` against PostgreSQL, made green, then required |
| note | db.py `cursor()` | Deferred `BEGIN` takes the writer lock on the first write; same semantics as SQLite's deferred BEGIN today | Documented in known-issues K-PG03 |
| note | db_postgres.py | Failing SELECT inside a transaction aborts it on PostgreSQL; writes use savepoints | Accept |
| note | sqlite_to_postgres.py | Per-table `fetchall()` for hashing; no memory bound | Fine at current size; stream later |
| dead code | see brief 0461 step 4 | `_typed_column_kinds`, `_validate_pg_values` arg, `_begin_immediate`, `current_schema()`, `PostgresCursor.fetchmany`, `database_label()`, `_record_backup_receipt` | Delete |

Verified sound: fail-fast startup on an unreachable URL (`ConnectionError` in `init_db`), both backends set at once refused, transfer refuses a non-empty target and copies schema + data + sequences + triggers in one transaction, typed length-prefixed per-row hashes per table in `--verify-only`, `IS ?` → `IS NOT DISTINCT FROM`, `?` → `%s` via a quote-aware lexer, TEXT columns `COLLATE "C"`, identity columns with `setval` restore.
