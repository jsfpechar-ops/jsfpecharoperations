# WP15: Skip unchanged iCal feeds

Commit `a4542ee` on branch `wp14`, stacked on WP14 (`e97b048`). Apply WP14 first. The patch touches `db.py` next to WP14's changes, and its tests use `db.close_connections()`.

## Summary

- Four new `ical_feed` columns, added through the existing `ADDED_COLUMNS` migration: `etag`, `last_modified`, `body_sha256`, `last_checked_at`.
- `feed_fetch.fetch_calendar(url, etag, last_modified)` sends `If-None-Match` / `If-Modified-Since` when validators are given. It returns the text with the server's validators, or `not_modified=True` on a 304.
  - A 304 without conditional headers is still an error, as before.
  - Validators are only stored and sent back when they are printable ASCII and at most 256 characters, so a server cannot inject a header and `requests` never rejects the value.
  - `fetch_calendar_text` is unchanged for its callers.
- `icalsync.fetch_feed(url, etag=None, last_modified=None)` still returns a `str`. It is now a `FeedText` subclass that carries `etag`, `last_modified` and `not_modified`. Existing callers and the many test stand-ins `lambda url: text` keep working, because the validators are only passed when the feed has some.
- `sync_feed`:
  - On a 304: writes only `last_checked_at` (and refreshed validators), then returns `outcome="not_modified"`.
  - When the body's SHA-256 equals the stored one: writes only `last_checked_at` and skips parsing (`outcome="unchanged"`).
  - Otherwise: parses and reconciles exactly as before (`outcome="changed"`). The hash and validators are written together with the final `ok` or `suspect` status, so a reconciliation that crashes part-way never looks like a good read.
- A feed is only skipped (and only sent validators) when its last status is `ok` and a hash is stored. After an error or a `suspect` (incomplete) answer, the calendar is always read and reconciled again, so the existing error and incomplete alerts are re-checked and still clear the way they did.
- `last_sync_at` keeps its meaning: the last time the calendar was read. Exception: the error path, which already wrote it before this WP and still does. `last_checked_at` is written on every outcome, including errors.
- "Sync now" (`POST /sync`) and the hourly job both go through `sync_all`, so both always fetch and both use conditional headers.
- `sync_all` returns `not_modified`, `unchanged` and `changed` counts and logs one line per run: `ical_sync_run feeds=N not_modified=N unchanged=N changed=N errors=N`. No URLs and no guest data in the line.
- The property page's feed table shows `last_checked_at`, falling back to `last_sync_at`, under the status pill. A quiet calendar therefore does not look hours old. No new strings.

## Files changed

- `App/app/db.py`: four `ADDED_COLUMNS` entries for `ical_feed`.
- `App/app/feed_fetch.py`: `clean_validator`, `FetchedCalendar`, `fetch_calendar` with conditional headers and 304 handling.
- `App/app/icalsync.py`: `FeedText`, conditional `fetch_feed`, `body_digest`, skip logic in `sync_feed`, counts and log line in `sync_all`, `last_checked_at` on failure.
- `App/app/templates/apartment_form.html`: shows the latest check time.
- `App/tests/test_p1_review.py`: `test_G_mid_sync_exception_is_recorded` now serves a changed calendar on its second sync. With the same calendar, the reconciliation it wants to crash is (correctly) skipped. The test's intent is unchanged.
- `App/tests/test_ical_skip_unchanged.py`: new.

## Tests added

`tests/test_ical_skip_unchanged.py`, 9 tests:

- unchanged hash: no parse, only `last_checked_at` written, `last_sync_at` kept
- changed body: reservations written as today, hash and `last_sync_at` updated
- 304 path: stored validators sent, no parse, `last_sync_at` kept
- failing feed: still raises the `feed_error` alert, and the next read of the same calendar is reconciled in full and clears the alert
- a `suspect` feed is never skipped
- `sync_all` counts and log line
- migration of a legacy `ical_feed` table
- `clean_validator` rejects CR/LF and over-long values
- real HTTP server: the conditional headers are sent, a 304 is read as not modified, and a 304 without validators is still an error

## Test commands and results (exact counts)

Run from `/tmp/wp/wp14/App`:

- `.venv/bin/python -m pytest -q tests/test_ical_skip_unchanged.py`: 9 passed.
- Related files: `test_icalsync.py`, `test_feed_dns_pinning.py`, `test_p1_review.py`, `test_zz_review.py`, `test_calendar_sync_ui.py`, `test_guest_navigation.py`, `test_efficiency.py`, `test_db_upgrade.py`: all passed.
- `test_demo_seed.py`: passes alone and in the full suite. It fails on `wpbase` too when run straight after the other files listed above, because a leftover apartment makes the seed return None. That is an order dependency that already exists.
- Whole suite in one process (WP14 + WP15): 2192 passed, 7 skipped, 2 failed. Both failures already happen on `wpbase`; see the WP14 notes (Chromium cannot start in the sandbox, and the order-dependent `test_stale_submission`).
- Ruff (`E9,F63,F7,F82,F401,F841`): all checks passed.

## Deviations from the spec and why

- The spec says "skip ... when the body hash is unchanged". I only skip when the last status was `ok`. Skipping after an error or a `suspect` answer would freeze that state and its alert until the calendar changed.
- `last_checked_at` is written on every check, not "once per hour at most". The sync runs hourly anyway, and "Sync now" is a deliberate host action.
- The Operations page (WP10) is not in this base, so there was nothing to switch there. Alerts never read `last_sync_at` (checked by grep); the feed error alert is unchanged.
- `fetch_feed` returns a `str` subclass rather than a new result type, to keep its call sites and about 25 test stand-ins unchanged.

## What Cursor must verify or adapt when applying on the real main

- If WP10 (Operations page) is merged: its rule "no successful sync for more than 3 hours" must use `last_checked_at` together with `last_status = 'ok'`, not `last_sync_at`. Otherwise every quiet calendar shows up as stale.
- If WP13 is merged: the scheduler's calendar job can log `changed` / `unchanged` / `not_modified` from the `sync_all` totals. The `perf_report.py` "iCal changed ratio" should read the new `ical_sync_run` line.
- Confirm no new code on main writes `ical_feed.url` in place. If a URL edit is added, it must clear `etag`, `last_modified` and `body_sha256`.
- After a week in production, check the `ical_sync_run` lines to see whether Airbnb and Booking send ETag or Last-Modified (review 7.1 marks this as an assumption).

## Manual steps for the owner

- None. The columns are added automatically at startup. The first sync after deploy reads every feed in full, once, to store its hash and validators.
