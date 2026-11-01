# 0557 report

Status: review

## Files changed
- `go/internal/ubyport/recover.go` (new): `RecoverStaleSubmissions` (reporting.py 1851-1912) and `RefreshRegistrationCompletedAt` (923-972).
- `go/internal/ubyport/recover_test.go` (new): stale recovery cases; `TestReportingTodayIsUTCDate` (23:30 UTC); `TestRefreshRegistrationCompletedAt` (declared reached, quiet 12 h, not yet quiet, incomplete clears, complete keeps stamp; hand-filed guests count as complete).
- `go/internal/ubyport/collect.go`: guest query and decrypt loop extracted into exported `LoadGuests(ctx, pool, GuestScope, decrypt)`; `CollectSendable` calls it with the same SQL, order and errors. `today` is now `reportingToday(now)`, the UTC date of now (was Prague date).
- `docs/tasks/0557-report.md`.

## Commands
- `gofmt -l .` empty; `go vet ./internal/ubyport/` clean.
- `go test ./internal/ubyport/ -count=1 -v -run 'Refresh|Recover|Reporting'`: all PASS.
- `go test ./internal/ubyport/ -count=1`: `ok github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport 30.988s`. Skip count: 0 (`grep -c -- '--- SKIP'` = 0).

## Deviations
- Refresh needs guest `updated_at`/`created_at`, which the loader does not select. A separate small query reads them (`COALESCE(NULLIF(updated_at,''), NULLIF(created_at,''))`), so `LoadGuests` and its SQL stay as they were.
- `LoadGuests` returns the unexported `collectGuest` type, as the existing code does.
- The stay scope of `LoadGuests` has no status filter (Python's reservation_progress has none).
- The `today` change is in CollectSendable, so 0556 behaviour changes near midnight. Tests stay green.

## Owner steps left
None. Nothing pushed.
