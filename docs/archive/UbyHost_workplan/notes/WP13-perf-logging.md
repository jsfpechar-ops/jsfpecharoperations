# WP13: Per-request query, DB-time and lock-time logging

## Summary
`db.py` keeps a per-request counter in a contextvar: statements run, wall time in the database helpers, and time spent waiting in `BEGIN IMMEDIATE`. The access middleware starts a fresh counter per request and `_log_access` appends `q=`, `db_ms=` and `lock_ms=` to the existing PII-free line. Every scheduler job logs one `job run job=<id> ok=<0|1> ms=<n> key=<int>...` line. New `App/tools/perf_report.py` reads a log file or stdin and prints p50/p99 per route group, queries per request, DB time and lock wait p99, error rate, per-job run times and the iCal changed ratio.

Stacked on WP10.

## Files changed
- `App/app/db.py`: `RequestStats`, `start_request_stats()`, `current_request_stats()`; trace-callback statement count (only when a counter is active); timing in `query`, `execute`, `update_if`, `cursor()`, `immediate()`; lock wait around `BEGIN IMMEDIATE`.
- `App/app/main.py`: middleware starts the counter; `_log_access` prints the three fields.
- `App/app/scheduler.py`: `_log_run` and a timed line for each job (calendar, submit, deadlines, mail, photo sweep, retention).
- `App/app/icalsync.py`: `sync_all` totals gain `changed` (feeds whose sync created, updated or cancelled a stay).
- `App/tools/perf_report.py`: new.
- `App/tests/test_perf_logging.py`: new.

## Tests added
`tests/test_perf_logging.py` (9): the access line has `q`, `db_ms`, `lock_ms`; the counter resets per request (three identical requests do not grow); `start_request_stats` gives a new object; lock wait is measured when another connection holds the write lock; no token, query string, e-mail or surname in the line; the calendar job logs its run line with counts; the report groups routes, skips lines older than the window, computes error rate and changed ratio, never prints a route; stdin input; route grouping and percentile helper.

## Test commands and results
- `python -m pytest -q tests/test_perf_logging.py`: 9 passed.
- With `tests/test_access_log.py tests/test_scheduler.py tests/test_icalsync.py`: 70 passed.
- Broad run at this commit (central files changed): `[a-f]` 606 passed, 2 skipped; `[g-o]` 774 passed, 1 skipped, 1 failed; `[p-z]` plus guest browser e2e 798 passed, 4 skipped, 1 failed. Same two pre-existing failures as in WP10 (also fail on `wpbase`).
- Ruff: all checks passed.

## Deviations from the spec and why
- `db_ms` is wall time inside the helpers, including opening the connection, and for `cursor()`/`immediate()` the whole block (Python work inside the transaction counts). Hydration and decryption of guest rows in `query()` are excluded. One raw `db.connect()` call in `routes/admin.py` is counted in `q` but not timed.
- `q` counts statements through `sqlite3` trace callbacks, excluding the connection PRAGMAs, `BEGIN`/`COMMIT`/`ROLLBACK` and trigger sub-statements.
- Route group "public" covers the marketing, legal, guide, login and invoice-download routes. `/` counts as host because signed-in it is the dashboard. Requests that match no route go to "other".
- The report filters by timestamp against the current time (`--now` and `--days` to override). Lines without a timestamp are kept.

## What Cursor must verify or adapt when applying on the real main
- If WP14 (one connection per thread) lands first or later, the counter has to move to the new connection helper: keep `set_trace_callback` wherever a connection is opened or reused, and keep the `_timed()` wrappers around the public helpers. The `BEGIN IMMEDIATE` timing must stay around the statement that takes the lock.
- If WP06 runs the scheduler in its own process, the job lines are in that process's log; feed both logs to `perf_report.py`.
- Check that the production log line format still contains `ubyhost.access:` and `ubyhost.scheduler:` (the report matches on those names).

## Manual steps for the owner
Weekly, on the server: `docker compose logs --no-color --since 168h app | python3 App/tools/perf_report.py` (adjust the service name). Compare lock wait p99 with the 50 ms trigger in review 7.2.5.
