# 1136 report (Status: review)

Done: steps 1 to 6. The first run had no Postgres (connection refused). After the coordinator restarted it, all Go steps were re-run and pass (see Update below).

1. Files changed (`git diff --stat d2dbf393 HEAD -- App go`):
   - App/app/icalsync.py (+ per-guest locks, UPDATE on the cursor, stored-date guard)
   - App/tests/test_icalsync.py (+25, call-site test)
   - go/internal/ical/syncfeed.go (+ locks, stored-date guard, `sendInFlightFn` seam)
   - go/internal/ical/syncfeed_test.go (+85, new signature, call-site test, lock-wait test)
   - docs/tasks/1136-ical-date-move-claim-lock.md (Status: blocked)

2. Commands and results:
   - Step 1 check `db.ENCRYPTED_COLUMNS.get('reservation')`: prints `None`. Passed.
   - Step 1 `pytest tests/test_icalsync.py -k claim`: `3 passed, 48 deselected`.
   - Step 2 `pytest tests/test_icalsync.py tests/test_ical_skip_unchanged.py`: `61 passed`.
   - Step 2 revert bite (call site set to `db.update("reservation", ...) or True`), `-k precheck`: FAILED as expected (`('2099-02-10', '2099-02-12') == ('2099-01-10', '2099-01-12')`). Line restored exactly; rerun `61 passed`.
   - Step 3 `go build ./internal/ical/`: exit 0.
   - Step 4 first attempt, with the URL: all three FAIL with `connection refused` (Postgres was down).
   - Same tests WITHOUT the URL: all three SKIP, `ok`. Not a pass.
   - `go vet ./internal/ical/`: silent. `gofmt -l internal/ical/`: silent.

Update (Postgres back at localhost:5432):
   - `go test ./internal/ical/ -count=1 -run 'UpdateReservationUnlessClaimed|DefersDateMove' -v` with the URL: `--- PASS` for TestUpdateReservationUnlessClaimed, TestSyncFeedDefersDateMoveWhenClaimLandsAfterPrecheck, TestUpdateReservationUnlessClaimedWaitsForClaimLock. `ok`.
   - Full `go test ./internal/ical/ -count=1 -v` with the URL: `ok`; `--- SKIP` count 0.
   - `go vet ./internal/ical/`: silent.
   - Go revert-bite: call site set to `ok, err := true, updateRow(ctx, pool, "reservation", s.ID, changed)`; `-run DefersDateMove` FAILED (`date_from = "2027-05-02", want unchanged`; digest stored after a deferred move). Line restored exactly; rerun PASS; 0 SKIP.
   - `python3 scripts/context_lint.py`: `context lint: OK`.

3. Section 7 ticks:
   - [x] `lock_key` in icalsync.py (one hit, inside the helper)
   - [x] Go helper takes storedFrom/storedTo, locks in id order, SQL has `date_from = $` and `date_to = $`
   - [x] Python call-site test fails on revert, passes restored
   - [x] Go call-site test fails on revert, passes restored
   - [x] `TestUpdateReservationUnlessClaimedWaitsForClaimLock` PASS against Postgres
   - [x] Go tests and vet green against Postgres
   - [x] Python tests green; context lint OK
   - [x] Only §3 files changed

4. Deviations: none in code. Step 4 Go tests were first committed before Postgres was up; they now pass.

5. Questions: none.

6. Owner steps left: none for this brief. Merge of PR #933 and any follow-up brief per the brief's Owner steps.
