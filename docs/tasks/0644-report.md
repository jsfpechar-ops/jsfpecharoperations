# 0644 report: Go syncs one iCal feed (Status: review)

## Files changed
- go/internal/ical/reconcile.go: Feed gains URL, LastStatus, BodySHA256, ETag, LastModified; SyncStats gains Created, Updated, BlocksSkipped, Outcome, Error.
- go/internal/ical/syncfeed.go (new): BodyDigest, SyncFeed and helpers.
- go/internal/ical/syncfeed_test.go (new): digest test and 11 DB/304 tests.
- docs/tasks/0644-go-ical-sync-feed.md: Status set to review.
- docs/tasks/0644-report.md (this file).

## Commands
- `cd go && gofmt -l .` (empty) and `go vet ./internal/ical/`: clean.
- `UBYHOST_TEST_DATABASE_URL=postgres://postgres:ubyhost@127.0.0.1/postgres go test ./internal/ical/ -count=1 -v`:
  ```
  --- PASS: TestSendInFlight (0.39s) ... (all existing tests pass)
  --- PASS: TestBodyDigest (0.00s)
  --- PASS: TestSyncFeedCreatesAndUpdates (0.40s)
  --- PASS: TestSyncFeedUnchangedAndRevive (0.38s)
  --- PASS: TestSyncFeedBlockKeepsStay (0.39s)
  --- PASS: TestSyncFeedCancelEvent (0.41s)
  --- PASS: TestSyncFeedDuplicateUIDAlert (0.42s)
  --- PASS: TestSyncFeedMovedAfterReport (0.42s)
  --- PASS: TestSyncFeedDatesInFlightKeepsDigest (0.38s)
  --- PASS: TestSyncFeedIncompleteKeepsStays (0.39s)
  --- PASS: TestSyncFeedVanishedStayCancelled (0.39s)
  --- PASS: TestSyncFeedNotModified (0.37s)
  PASS
  ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ical 6.584s
  ```
  0 skipped.

## Deviations from Python
- The digest test value was printed by plain python3 with the same regex and sha256 (no App/.venv was created). Three inputs (DTSTAMP, lowercase DTSTAMP with TZID, LF only) give the same digest.
- `now` is one value for every write SyncFeed makes itself. The helpers it calls (cancelExistingStay, fitUnsentGuestWindows, expireOnCancel, reopenGuestAccess, recordFeedFailure) still call ubyport.UTCNow() themselves, so their timestamps can differ by microseconds.
- pyStr in reconcile.go renders a NULL as "None". syncfeed.go uses its own nz helper for NULL checks. Do not use pyStr for emptiness checks.
- Not covered by a new test: ignored-stay skip, live submission_claim in-flight case, guest access reopen on revive.

## Questions
None.

## Owner steps left
None. Nothing pushed. Nothing calls SyncFeed yet.
