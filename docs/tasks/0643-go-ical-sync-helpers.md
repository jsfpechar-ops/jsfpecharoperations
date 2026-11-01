# 0643: Go: the iCal sync helpers (cancel, re-key, window fit, feed alerts)
Status: review
Depends on: 0642 (merged) | Base commit: origin/main | Branch: task/0643-go-ical-sync-helpers
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 90k tokens
## 1. Objective
Fourth slice of porting the `ical` job to Go. Port the helpers `sync_feed` uses, `App/app/icalsync.py` 249-300 (synthetic aliases) and 372-663, so slice 0644 can port `sync_feed` itself. Nothing calls them yet; nothing changes in production.
## 2. Context
- Read `App/app/icalsync.py` 249-300 and 372-663 whole. Also `App/app/claim.py` 695-722 (`reopen_guest_access`, `expire_on_cancel`; `_row` is a plain `SELECT * FROM reservation_claim WHERE reservation_id = ?`) and `App/app/db.py` `update_if` 2059-2084.
- Reuse, do not copy: `ubyport.RaiseAlert`, `ubyport.ResolveAlert`, `ubyport.Audit`, `ubyport.UTCNow` (`go/internal/ubyport/effects.go`, `store.go`), `ubyport.QueueCancelledWithGuestsMail` / `QueueCancelledWithGuestsPush` (`cancelled_notify.go`), `ubyport.SubmissionClaimTTL` (`claim.go`; see how `claim.go` compares `claimed_at`, it is epoch seconds), the `prague` location in `go/internal/ical/parse.go`, `validation.ParseISODate` (`go/internal/validation/validation.go` 169).
- Feed alert strings: `App/app/host_i18n.py` 654-657, language `en` (`DEFAULT_LANGUAGE`). `%(property)s` is the property name.
- **Traps:**
  - `_legacy_synthetic_uid` cuts `summary[:20]` in code points: use runes.
  - `_cancel_existing_stay` compares `date_from` to today's date in Europe/Prague, not UTC. It skips (and raises `cancelled_after_report`) when any guest is `sent`; otherwise status `cancelled`, then `expire_on_cancel` (claim row missing: nothing), then the warn step, then `stats.Cancelled++`.
  - The warn step counts guests with `archived_at IS NULL AND submit_state NOT IN ('sent','not_required')`; 0 means no alert, no mail, no push. Errors from the mail/push queue functions are logged and do not fail the cancel (Python swallows them).
  - `_fit_unsent_guest_windows` update is a compare-and-set: same WHERE as Python (expected `submit_state`, no live claim, no running/outcome_unknown submission), one statement per guest; audit only when 1 row changed. Bad ISO dates in the new window: return 0.
  - `_reopen_guest_access` only when `guest_access_locked_at` is set; returns whether it reopened.
  - `_record_feed_failure` writes `last_sync_at`, `last_checked_at`, `last_status='error'`, `last_error` and raises `feed_error` with params `{"feed": name, "error": msg}`. Name is `own_name or label or id` (empty string counts as missing, id printed as decimal).
  - `_report_import_limits` resolves the key when the list is empty, otherwise raises the alert (no params) and logs.
  - Alert param key order: match how `RaiseAlert` already serialises params; do not change `effects.go`.
## 3. Files
- New `go/internal/ical/reconcile.go`: `type Feed struct { ID, ApartmentID int64; OwnName, Label *string }`, `type SyncStats` (only the `Cancelled int` field for now), and unexported ports: `syntheticAliases`, `legacySyntheticUID`, `sendInFlight`, `fitUnsentGuestWindows`, `warnIfGuestsRegistered`, `cancelExistingStay`, `existingReservation` (return the reservation id and found flag, plus the columns 0644 needs: `id, status, date_from, date_to, uid`), `reopenGuestAccess`, `reportImportLimits`, `recordFeedFailure`. Each takes `ctx`, a `*pgxpool.Pool` and `getenv` where needed. Keep each next to a one-line comment naming its Python source line.
- New `go/internal/ical/reconcile_test.go`: DB tests in the style of `go/internal/ubyport/claim_test.go` (its pool helper, lines 18-60) (skip without `UBYHOST_TEST_DATABASE_URL`), plus pure tests for the alias and legacy UID functions (a multi-byte summary longer than 20 runes).
- Write `docs/tasks/0643-report.md`.
## 4. Steps
1. Pure functions and their tests.
2. DB helpers one by one, each with a test: send in flight (live claim, running submission, none); window fit (moves, keeps a sent guest, skips a guest with a live claim, audit row written); cancel (sent guest keeps stay active and raises `cancelled_after_report`; unsent guest gives cancelled + claim locked + queued mail rows for that reservation set to `failed` + `cancelled_with_guests` alert; past stay untouched); re-key of a legacy synthetic row; reopen only when locked; feed failure row + alert; import limits raise then resolve.
3. Commit: `0643: Go ports the iCal sync helpers (off, nothing calls them yet)`.
## 5. Do not touch
`App/` (all), `go/internal/ubyport/`, other `go/internal/` packages except `ical`, `go/cmd/`, `go.mod`/`go.sum`, compose, CI, templates/CSS/JS.
## 6. Commands
- Local Postgres: `pg_ctlcluster 16 main start; su postgres -c "psql -c \"ALTER USER postgres PASSWORD 'ubyhost'\""`, then `export UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/postgres`. Schema: see how `claim_test.go` sets it up and do the same.
- From `go/`: `test -z "$(gofmt -l .)" && go vet ./... && go test ./internal/ical/ -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL|PASS)' | tail -40`.
- From the repo root: `git diff --stat origin/main`, `python3 scripts/context_lint.py | tail -3`.
## 7. Acceptance
`git diff --stat origin/main` lists only section 3 files and this brief. gofmt, vet and tests pass with the DB URL set, 0 skipped in the new tests. Existing ical tests unchanged and green.
## 8. Stop and ask
Stop if a helper needs a change in `ubyport` or a new dependency, or Python behaviour cannot be matched.
## 9. Report
`docs/tasks/0643-report.md`: command tails, diff stat, any difference from Python.
