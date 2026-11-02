# 0643 report: Go ports of the iCal sync helpers

Status: review. Nothing calls the helpers yet; production is unchanged.

## Files changed
- New `go/internal/ical/reconcile.go`: `Feed`, `SyncStats` (Cancelled only), and unexported ports of `syntheticAliases`, `legacySyntheticUID`, `sendInFlight`, `fitUnsentGuestWindows`, `warnIfGuestsRegistered`, `cancelExistingStay`, `existingReservation`, `reopenGuestAccess`, `reportImportLimits`, `recordFeedFailure`. Each has a one-line comment naming its Python source lines.
- New `go/internal/ical/reconcile_test.go`: pure tests (alias and legacy UID, runes, 25-rune summary) and DB tests for each helper. The DB tests skip without `UBYHOST_TEST_DATABASE_URL`.
- `docs/tasks/0643-go-ical-sync-helpers.md`: Status set to `review`.
- This report.

No change to `ubyport`, `go.mod`, `go.sum`, compose, CI, `App/` or templates.

## Commands
- `cd go && test -z "$(gofmt -l .)" && go vet ./...`: clean, no output.
- `UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/postgres go test ./internal/ical/ -count=1 -v`:
  ```
  --- PASS: TestSyntheticKeysPure (0.00s)
  --- PASS: TestSendInFlight (0.50s)
  --- PASS: TestFitUnsentGuestWindows (0.49s)
  --- PASS: TestCancelExistingStay (0.49s)
  --- PASS: TestRekeyLegacySynthetic (0.51s)
  --- PASS: TestReopenGuestAccess (0.48s)
  --- PASS: TestRecordFeedFailure (0.51s)
  --- PASS: TestReportImportLimits (0.43s)
  PASS
  ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ical	3.414s
  ```
  Skipped tests: 0. Existing ical tests (fetch, parse, golden, feed URL) pass unchanged.
- `python3 scripts/context_lint.py | tail -3`: see the commit step.

## Deviations from Python
- Helpers read the time through `ubyport.UTCNow()` instead of taking a `now` argument. The Python `now` only feeds `updated_at`-style columns.
- `cancelExistingStay` drops the unused Python `date_from` and `now` parameters. The Python body compares the stored `date_from`, not the parameter.
- `expire_on_cancel` (claim.py 705-720) and `reopen_guest_access` (claim.py 695-702) are not exported by `ubyport`, so their SQL is inlined in `ical` as `expireOnCancel` and in `reopenGuestAccess`. This is a copy; a later slice could move both into `ubyport`.
- The "%(property)s" alert copy is taken from host_i18n.py 654-657 as in the brief. The `feed_error` text is a hard-coded English f-string in Python (icalsync.py 650-661), and it is ported as such.
- `claimed_at` is compared against Unix seconds from `time.Now()`, the same float as Python `time.time()`, with `ubyport.SubmissionClaimTTL` as the window.
- `_fit` uses `submit_state = $5` instead of a null-safe compare. The column is NOT NULL, so the results are the same.
- The DB test helper is a copy of `claimTestPool` because the ubyport one is unexported. It applies `App/migrations_pg/*.sql` the same way.
- Commits: one commit, not one per step. Each step was run and checked before the next.

## Questions
None.

## Owner steps left
None for this slice. Branch `task/0643-go-ical-sync-helpers` is committed and not pushed.
