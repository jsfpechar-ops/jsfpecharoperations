# 0991 report

Status: review

## Files changed
- `App/migrations_pg/00008_full_scan_indexes.sql` (new): 4 `CREATE INDEX IF NOT EXISTS`, Down drops all 4.
- `docs/tasks/0991-full-scan-indexes.md`: Status line only (todo, then in-progress, then review).
- `docs/tasks/0991-report.md` (new): this report.

## Preflight
- Highest goose file was `00007_stay_fee_guest_default_rail.sql`; no `00008` existed before.
- All four anchors found verbatim: `property_health.py:34`, `icalsync.py:1016`, `admin_ops.py:71`, `admin_ops.py:218`.
- No existing `idx_alert_open*`, `idx_ical_feed_apartment*` or `idx_guest_submit_state*` in `App/migrations_pg` or `App/app/db.py`.
- `ical_feed.active` is `bigint DEFAULT 1 NOT NULL` (`00001_baseline.sql`). It is an integer type, so the `WHERE active = 1` predicate is valid and the §8 stop rule does not apply.

## Commands
1. `cd App && .venv/bin/python -m pytest tests/test_goose_migrations.py tests/test_migrations.py -q --tb=short -x -rs 2>&1 | tail -30`
   Last 5 lines:
   ```
   SKIPPED [1] tests/test_goose_migrations.py:81: PostgreSQL integration tests need UBYHOST_DATABASE_URL (or UBYHOST_TEST_DATABASE_URL) for a disposable target whose database name contains 'test'; this pytest process runs the SQLite row
   SKIPPED [1] tests/test_goose_migrations.py:90: PostgreSQL integration tests need UBYHOST_DATABASE_URL (or UBYHOST_TEST_DATABASE_URL) for a disposable target whose database name contains 'test'; this pytest process runs the SQLite row
   16 passed, 4 skipped in 3.39s
   ```
   The 4 skips are the PostgreSQL integration tests. No local PG was configured, so `00008` was not applied locally. CI job `test-postgres-full` applies it on PG 17.
2. `python3 scripts/context_lint.py 2>&1 | tail -30`
   Last 5 lines:
   ```
   WARN  test_0705_v2_shell_browser.py::test_non_v2_dashboard_still_loads_the_old_stylesheets_and_sidebar is named by open briefs 0784-settings-area-v2-old-shell-tests.md, 0851-fix-725-ci-and-savebar.md; say which goes first
   WARN  test_signed_in_chrome.py::test_the_support_line_is_not_part_of_the_legal_link_row is named by open briefs 0784-settings-area-v2-old-shell-tests.md, 0851-fix-725-ci-and-savebar.md; say which goes first
   WARN  1 commit(s) touched App/ after the last status.md update. Orchestrator: update docs/context/status.md at review.
   next free: task 0992 | migration 0038
   context lint: OK
   ```
   The WARN lines were already there before this change.

## Section 7 acceptance
- [x] `00008_full_scan_indexes.sql` exists, 4 `IF NOT EXISTS` indexes, Down drops all 4.
- [x] Only the three §3 paths are in the commit (checked with `git diff --stat f0a7fa3f HEAD`).
- [x] Test command passes: 16 passed, 4 skipped (PG only, see command 1).
- [x] Pushed to `claude/zealous-planck-raxu4v`.

## Deviations
- No PR opened. The owner's instruction for this run overrides brief §4 step 5 and executor.md.
- One commit for all three files, not one per step. The commit message is the brief's subject line.
- The 4 PG integration tests skipped because no local PostgreSQL was set up. Not run.

## Questions
- None.

## Follow-ups from brief §2 (not in scope, not done)
- `App/app/alerts.py:558` `open_alerts`: `(? IS NULL OR owner_user_id = ? OR kind IN (...))` with a Python sort defeats `idx_alert_owner`.
- `App/app/reporting.py:1410` and `App/app/stay_fee.py:307`: guest filter through `r.apartment_id` needs an index on `reservation (apartment_id)`.
- The `g.submit_state != 'sent'` branch in `reporting.py:1566` may not use the new guest index. EXPLAIN was not run.

## Owner steps left
1. Merge as usual and deploy.
2. If the deploy notes mention a goose file, run on the server: `docker compose run --rm --no-deps ubyhost python scripts/pg_schema.py apply --expect-database ubyhost`.
