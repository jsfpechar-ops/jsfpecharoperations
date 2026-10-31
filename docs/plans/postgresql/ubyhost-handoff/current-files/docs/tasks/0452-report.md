# 0452 implementation report

Status: review

## Files changed

- `App/app/db.py`: added `readonly_cursor()` using SQLite URI `mode=ro` with a deferred read transaction.
- `App/scripts/export_billing_analytics.py`: added bounded current-quote and invoice-month export to one atomic JSON file, with DB/sidecar collision checks.
- `App/tests/test_db_readonly_cursor.py`: tests read-only enforcement, unchanged main database bytes/mode/journal mode, and WAL snapshot consistency.
- `App/tests/test_billing_analytics_export.py`: tests legacy quote math, status inclusion, exact minor-unit aggregates, range filtering, privacy, aliases, repeated runs, and pre/post-replace failures.
- `docs/tasks/0452-read-only-billing-extract.md`: updated brief and status.

## Commands

- `.venv/bin/python -m pytest tests/test_db_readonly_cursor.py tests/test_db_upgrade.py tests/test_db_update_if.py tests/test_billing_analytics_export.py tests/test_billing_analytics.py -q --tb=short -x 2>&1 | tail -30`
  - `50 passed in 2.39s`
- `python3 scripts/context_lint.py 2>&1 | tail -30`
  - Fails on concurrent `docs/tasks/0455-postgresql-runtime-and-transfer.md` missing required template sections. Existing plan-conflict and status-update warnings remain. 0452 also initially lacked this report; that requirement is now satisfied.
- `git diff --check -- App/app/db.py docs/tasks/0452-read-only-billing-extract.md`
  - No output; passed.

## Acceptance and deviations

- [x] Read-only mode, bounded projections, consistent read transaction, atomic one-file publish, output collision protection, metric labels, privacy and focused tests implemented.
- [ ] Context lint remains blocked by the concurrent incomplete 0455 brief.
- SQLite may create/refresh its WAL `-shm` coordination sidecar for a read-only WAL snapshot. Tests verify main database bytes, permissions and journal mode remain unchanged; no data writes, `init_db()`, `_open()`, chmod or journal-mode changes occur in the read-only helper.
- Pre-replace failures leave an existing export intact. A directory fsync failure after `os.replace()` reports that the new complete file is already published and directory durability is uncertain.

## Owner steps

1. Review the four App files and the metric-label/sidecar behavior.
2. Use only an explicitly selected non-production database and output path for manual validation; production use requires separate authorization.
