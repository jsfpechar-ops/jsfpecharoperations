# 0644: Go: sync one iCal feed into the reservation table
Status: todo
Depends on: 0643 (PR #677) | Base commit: task/0643-go-ical-sync-helpers | Branch: task/0644-go-ical-sync-feed
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 90k tokens
## 1. Objective
Fifth slice of porting the `ical` job to Go: `sync_feed` (`App/app/icalsync.py` 664-953) with `body_digest`, `_trusted_for_skip`, `_download`, `_validator_values` (146-192). Same rows, alerts and stats as Python. Nothing calls it yet; nothing changes in production.
## 2. Context
- Read `App/app/icalsync.py` 117-192 and 664-953 whole. The helpers it calls are already ported in `go/internal/ical/reconcile.go` (0643); `Fetch` is in `fetch.go`, `ParseEvents` and `PlatformOf` in `parse.go`. Reuse them; extend `Feed` and `SyncStats` in place.
- Alerts: `ubyport.RaiseAlert`, `ubyport.ResolveAlert`. `feed_incomplete` copy: `App/app/host_i18n.py` 8196-8197, language `en`; add it next to `importLimitCopy`.
- **Traps:**
  - One `now := ubyport.UTCNow()` for the whole call: every `updated_at`, `created_at`, `last_checked_at`, `last_sync_at` written by `SyncFeed` itself uses it.
  - `body_digest`: drop `\r\n` to `\n` first, then remove whole lines matching `(?im)^DTSTAMP[;:].*\n?`, sha256 hex of the UTF-8 bytes.
  - Fetch or parse error: `recordFeedFailure`, return stats with `Error` set and a nil Go error. Errors after that point (DB) return a Go error; the 0645 caller records them.
  - 304: write only `last_checked_at` plus non-empty validators, outcome `not_modified`. Same digest on a trusted feed: same write, outcome `unchanged`. Validators are sent only when trusted and at least one is non-empty.
  - Duplicate UID: second one skipped and listed. Block: `blocks_skipped++`; an existing active row with that uid counts as seen. Cancelled event: `cancelExistingStay`. Ignored stays are never touched.
  - `changed` compares each payload column with the stored value, NULL-safe (`summary` is `summary or name_hint or None`: empty string is NULL). A cancelled stay revived gets `status=active` and `reopenGuestAccess`.
  - Date move while `sendInFlight`: keep the stored dates, and at the end do not write `body_sha256`, `etag`, `last_modified`.
  - `moved_after_report` alert text and detail exactly as Python, no params. `guest_email` filled only when the stored one is NULL or empty.
  - New stay: `source` is `PlatformOf(feed.URL, text)`.
  - Completeness: candidates are active rows of this feed with `date_from >= today in Europe/Prague`; matched = candidate uids that were seen; if candidates exist and `matched < 0.5 * candidates`: feed `last_status='suspect'`, `last_error=NULL`, plus read values; raise `feed_incomplete`; return. Else resolve it and cancel unseen candidates as Python does (variant `disappeared`; `cancelled_after_report` when a guest is sent).
  - Final feed write `last_status='ok'`, `last_error=NULL`.
## 3. Files
- Edit `go/internal/ical/reconcile.go`: `Feed` gains `URL string; LastStatus, BodySHA256, ETag, LastModified *string`; `SyncStats` gains `Created, Updated, BlocksSkipped int; Outcome, Error string`.
- New `go/internal/ical/syncfeed.go`: `BodyDigest(text string) string` and `SyncFeed(ctx, pool, getenv, feed Feed, opt FetchOptions, icsText *string) (SyncStats, error)` (`icsText` non-nil skips the download, like Python's `ics_text`).
- New `go/internal/ical/syncfeed_test.go`: `BodyDigest` against values printed by Python (`cd App && .venv/bin/python -c 'from app.icalsync import body_digest; print(body_digest(...))'`; create `.venv` first if missing: `python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt`), and DB tests with `icsText` set (no network): create, update, revive, block keeps stay, cancel event, duplicate UID alert, date move with a sent guest raises `moved_after_report`, date move in flight keeps dates and digest, incomplete feed keeps stays, vanished stay cancelled, unchanged on second identical run of a trusted feed. One 304 test through `Fetch` with the test `Dial` used in `fetch_test.go`.
- Write `docs/tasks/0644-report.md`.
## 4. Steps
1. `BodyDigest` and its test.
2. `SyncFeed` and the DB tests, one behaviour at a time.
3. Commit: `0644: Go syncs one iCal feed like Python (off, nothing calls it yet)`.
## 5. Do not touch
`App/` (all), `go/internal/ubyport/`, other `go/internal/` packages except `ical`, `go/cmd/`, `go.mod`/`go.sum`, compose, CI, templates/CSS/JS.
## 6. Commands
- Local Postgres: `pg_ctlcluster 16 main start; su postgres -c "psql -c \"ALTER USER postgres PASSWORD 'ubyhost'\""`, then `export UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/postgres`.
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/ical/ -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL|PASS)' | tail -40`.
- From the repo root: `git diff --stat task/0643-go-ical-sync-helpers`, `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
The diff against the 0643 branch lists only section 3 files and this brief. gofmt, vet and tests pass with the DB URL set, 0 skipped in the new tests. Existing ical tests unchanged and green.
## 8. Stop and ask
Stop if `SyncFeed` needs a change in `ubyport` or a new dependency, or Python behaviour cannot be matched.
## 9. Report
`docs/tasks/0644-report.md`: command tails, diff stat, any difference from Python.
