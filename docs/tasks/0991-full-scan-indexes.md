# 0991: indexes for the full-scan tables (alert, ical_feed, guest)

Status: review
Depends on: none | Base commit: origin/main | Branch: claude/zealous-planck-raxu4v
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Add one additive PostgreSQL goose file with 4 indexes so the hot loop queries on `alert`, `ical_feed` and `guest` have a usable index at about 1000 properties (100x today's rows). No Python changes.

## 2. Context

Production measurement (pg_stat_user_tables, 6 days, 9 properties): guest 257,120 seq_scan vs 41,781 idx_scan; alert 119,405 vs 797; ical_feed 14,531 vs 133; cleaning_event 157,144 vs 157,836 (already indexed, see below). Tables are tiny today (88 / 99 / 15 rows), so this costs nothing now and Postgres may still pick seq scans on tiny tables. The goal is readiness, not a speed-up today.

Rules (docs/context/rules.md § Database): goose files in `App/migrations_pg/NNNNN_name.sql`, next number = highest + 1 (highest is 00007, so this is **00008**), applied by `scripts/pg_schema.py apply`. Files must be additive so the previous image keeps working. `App/app/migrations/` is frozen at 0033; `db.SCHEMA` and `db.ADDED_COLUMNS` never change.

SQLite twin: NOT needed. Rules say a twin is needed only for "a column the Python code reads"; an index adds no column, and precedent `App/migrations_pg/00002_poll_indexes.sql` (also indexes only) has no twin and no `schema_migrations` row. Copy its shape. No `CONCURRENTLY` (00002 and 00003 do not use it, and goose wraps each file in a transaction); tables are tiny so the lock is instant.

Existing indexes (baseline `00001_baseline.sql` lines ~3077-3206, and 00002-00004):
- alert: `idx_alert_dedupe` UNIQUE (dedupe_key) WHERE resolved_at IS NULL; `idx_alert_owner` (owner_user_id, resolved_at). Nothing on apartment_id or kind.
- cleaning_event: `idx_cleaning_schedule` (apartment_id, scheduled_date, state); UNIQUE (source_reservation_id). Covers `App/app/cleaning.py:230` and the /cleaning/schedule JSON. No new index (its 157k seq scans are the point-lookups on a 172-row table; leave it).
- ical_feed: only the primary key. Nothing on apartment_id.
- guest: reservation_id, submission_id, receipt_submission_id. Nothing on submit_state.

Proposed indexes, each with the query that lacks one today:

1. `idx_alert_open_apartment` ON alert (apartment_id) WHERE resolved_at IS NULL.
   `App/app/property_health.py:33-36`: `SELECT kind FROM alert WHERE apartment_id = ? AND resolved_at IS NULL` (run per property on the dashboard/health loop).
2. `idx_alert_open_kind` ON alert (kind) WHERE resolved_at IS NULL.
   `App/app/admin_ops.py:216-219`: `... FROM alert WHERE kind = 'job_failed' AND resolved_at IS NULL LIMIT ?`; and `App/app/admin_ops.py:279-282`: `... FROM alert WHERE resolved_at IS NULL GROUP BY kind, level`.
3. `idx_ical_feed_apartment_active` ON ical_feed (apartment_id) WHERE active = 1.
   `App/app/icalsync.py:1015-1017`: `SELECT * FROM ical_feed WHERE active = 1 AND apartment_id = ?`; also joins `f.apartment_id = a.id AND f.active = 1` at `App/app/onboarding.py:35`, `:124` and `icalsync.py:969`.
4. `idx_guest_submit_state_open` ON guest (submit_state) WHERE archived_at IS NULL.
   `App/app/admin_ops.py:66-72` (`_FILING_FROM`): `FROM guest g ... WHERE g.archived_at IS NULL AND r.archived_at IS NULL AND (g.submit_state IN (?, ?) OR ...)`; also `App/app/reporting.py:1566-1568` (`g.archived_at IS NULL AND g.submit_state != 'sent'`) and `App/app/filing_watchdog.py:117`. Note: `!=` and the `OR` branch may not use it; the `IN (?, ?)` filter can. Say so in the report if EXPLAIN is not run.

Python narrowing (step 3 of the task): none. Follow-ups, not part of this brief: `App/app/alerts.py:558` `open_alerts` uses `(? IS NULL OR owner_user_id = ? OR kind IN (...))` and sorts in Python, which defeats `idx_alert_owner`; `App/app/reporting.py:1410` and `stay_fee.py:307` filter guests by `r.apartment_id` through a join (needs `reservation (apartment_id)`, not in scope).

How the file reaches production (docs/LIGHTSAIL.md:224): "`docker compose run --rm --no-deps ubyhost python scripts/pg_schema.py apply --expect-database ubyhost` | Apply pending PostgreSQL goose migrations (`App/migrations_pg/`) after a deploy whose notes mention a goose file; the app will not start while one is pending". CI job `test-postgres-full` applies every goose file on PG 17.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/migrations_pg/00008_full_scan_indexes.sql | create | 4 `CREATE INDEX IF NOT EXISTS`, Down drops them |
| docs/tasks/0991-full-scan-indexes.md | edit | Status line only |
| docs/tasks/0991-report.md | create | report |

No other file may change.

## 4. Steps

1. Set `Status: in-progress` in this brief. Confirm the highest file: `ls App/migrations_pg | tail -3 | tail -30` must end with `00007_stay_fee_guest_default_rail.sql`. If a `00008` exists, STOP (§8).
2. Confirm the four anchors still hold: `grep -n "FROM alert WHERE apartment_id\|FROM ical_feed WHERE active\|kind = 'job_failed'\|g.submit_state IN" App/app/property_health.py App/app/icalsync.py App/app/admin_ops.py | tail -30` shows all four. Confirm no index exists yet: `grep -rn "idx_alert_open\|idx_ical_feed_apartment\|idx_guest_submit_state" App/migrations_pg App/app/db.py | tail -30` prints nothing.
3. Create `App/migrations_pg/00008_full_scan_indexes.sql` with exactly:

```sql
-- +goose Up
-- Indexes for the hot loops on alert, ical_feed and guest (0991), ready for ~1000 properties.
-- Index-only and additive: no SQLite twin (no column is read by Python), the previous image keeps working.
CREATE INDEX IF NOT EXISTS idx_alert_open_apartment ON alert (apartment_id) WHERE resolved_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_alert_open_kind ON alert (kind) WHERE resolved_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_ical_feed_apartment_active ON ical_feed (apartment_id) WHERE active = 1;
CREATE INDEX IF NOT EXISTS idx_guest_submit_state_open ON guest (submit_state) WHERE archived_at IS NULL;

-- +goose Down
DROP INDEX IF EXISTS idx_guest_submit_state_open;
DROP INDEX IF EXISTS idx_ical_feed_apartment_active;
DROP INDEX IF EXISTS idx_alert_open_kind;
DROP INDEX IF EXISTS idx_alert_open_apartment;
```

   Check the column types accept those predicates: `grep -n "active integer\|active smallint\|active boolean" App/migrations_pg/00001_baseline.sql | tail -30` on the `ical_feed` table. If `ical_feed.active` is boolean, STOP (§8); the queries use `= 1`, so it should be integer.
4. Run the tests (from `App/`): `cd App && .venv/bin/python -m pytest tests/test_goose_migrations.py tests/test_migrations.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass (PG-backed tests may skip without a local PG; CI `test-postgres-full` applies the file on PG 17). From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.
5. Git: `git add App/migrations_pg/00008_full_scan_indexes.sql docs/tasks/0991-full-scan-indexes.md docs/tasks/0991-report.md`, then commit on branch `claude/zealous-planck-raxu4v` with the message `0991: indexes for alert, ical_feed and guest hot queries` and the trailers:
   `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
   `Claude-Session: https://claude.ai/code/session_014N5J8K21RfgG5itpXC8Mic`
   Then `git push -u origin claude/zealous-planck-raxu4v 2>&1 | tail -30`. No PR.

## 5. Do not touch

`App/app/**` (briefs 0990 and 0992 own db.py, a worker, main.py and templating), `App/app/migrations/`, `db.SCHEMA`, any existing goose file. Hard rules 3, 4 and 5 of AGENTS.md apply. No new dependency, no data, no secrets.

## 6. Commands

Only those in §4. Do not run the full suite.

## 7. Acceptance

- [ ] `App/migrations_pg/00008_full_scan_indexes.sql` exists, 4 `IF NOT EXISTS` indexes, Down drops all 4.
- [ ] `git diff --stat origin/main` shows only the three §3 paths.
- [ ] Test command from §4 step 4 passes (or skips only for missing local PG; say which).
- [ ] Pushed to `claude/zealous-planck-raxu4v`.

## 8. Stop and ask

Stop, and write the report as `blocked`, if: an anchor is not found; a `00008` file already exists; `ical_feed.active` is not an integer; a test fails twice; a file outside §3 needs a change; you reach 25 tool calls or about 50k tokens.

## 9. Report

Write `docs/tasks/0991-report.md` (600 tokens at most), set `Status: review`. It lists: files changed, each command with its last 5 lines, §7 ticked, deviations, the follow-ups from §2, owner steps left.

## Risk list (for the reviewer)

`App/migrations_pg/00008_full_scan_indexes.sql` only.

## Owner steps

1. Merge as usual and deploy.
2. If the deploy notes mention a goose file, run on the server: `docker compose run --rm --no-deps ubyhost python scripts/pg_schema.py apply --expect-database ubyhost`. Building four tiny-table indexes takes well under a second. Rolling back the image is safe: the indexes are additive.
