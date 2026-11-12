# 1136 report (Status: blocked)

Done: steps 1 to 4. Left: step 4 Go Postgres run, the Go revert-bite proof, and step 5 Go run and vet against Postgres. Step 6 (this report) done.

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
   - Step 4 `go test ... -run 'UpdateReservationUnlessClaimed|DefersDateMove' -v` WITH `UBYHOST_TEST_DATABASE_URL`: all three FAIL with `failed to connect ... 127.0.0.1:5432: connection refused`. `pg_isready -h localhost -p 5432`: no response. Postgres is not running in this session, so the brief's "local Postgres is running" premise is false here.
   - Same tests WITHOUT the URL: all three SKIP, `ok`. Not a pass.
   - `go vet ./internal/ical/`: silent. `gofmt -l internal/ical/`: silent.
   - Go revert-bite proof: NOT RUN (needs Postgres).
   - `python3 scripts/context_lint.py`: `context lint: OK`.

3. Section 7 ticks:
   - [x] `lock_key` in icalsync.py (one hit, inside the helper)
   - [x] Go helper takes storedFrom/storedTo, locks in id order, SQL has `date_from = $` and `date_to = $`
   - [x] Python call-site test fails on revert, passes restored
   - [ ] Go call-site test fails on revert (not run, no Postgres)
   - [ ] `TestUpdateReservationUnlessClaimedWaitsForClaimLock` PASS against Postgres (not run)
   - [ ] Go tests and vet green against Postgres (vet green; Go tests not run against Postgres)
   - [x] Python tests green; context lint OK
   - [x] Only §3 files changed

4. Deviations: none in code. Step 4 test code was committed unverified against Postgres.

5. Questions: none.

6. Owner steps left:
   - Start the local Postgres at localhost:5432 (database `ubytest`, user `uby`), then from `go/` run:
     `UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ical/ -count=1 -v 2>&1 | grep -E 'SKIP|FAIL|ok' | tail -30`
   - Then run the Go revert-bite proof from brief Step 4 and set the brief to `review`.
