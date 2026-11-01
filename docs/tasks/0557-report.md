# 0557 report

Status: blocked

## Files changed
- `go/internal/ubyport/recover.go` (new): `RecoverStaleSubmissions` (reporting.py 1851-1912). `RefreshRegistrationCompletedAt` is NOT written.
- `go/internal/ubyport/recover_test.go` (new): live claim left alone; old claim, empty guest list and no-claim batches become outcome_unknown; sent guest and newer-batch guest untouched; one critical alert with exact params; second run raises nothing.
- Not touched: `collect.go` (see Questions).

## Commands
- `gofmt -l .` empty; `go vet ./...` clean.
- `go test ./internal/ubyport/ -count=1 -v -run Recover`: PASS (TestRecoverLiveClaimLeftAlone, TestRecoverStaleBatches).
- `go test ./internal/ubyport/ -count=1`: `ok ... 23.694s`. Skip count: 0.
- `python3 scripts/context_lint.py`: not run (stopped before the lint step).

## Checklist (brief section 4)
- [x] Step 1, part: RecoverStaleSubmissions
- [ ] Step 1, part: RefreshRegistrationCompletedAt
- [x] Step 2, part: recover tests
- [ ] Step 2, part: refresh tests
- [ ] Step 3 commit message (commits made as "0557 step 1" and "0557 step 2: ...")

## Deviations
Done: steps 1 and 2 for stale recovery. Left: RefreshRegistrationCompletedAt and its tests; the `today` change in collect.go; the context lint.
Decisions beyond section 2: `guest_ids` parse ORDER BY id on the running scan (no effect on result); `live_after` is computed from the injected `now` (not wall clock).

## Questions
1. The 0556 guest loader does not exist as a function. The query and decryption are inline in `CollectSendable` (collect.go lines ~183-240, by apartment, ORDER BY r.date_from, g.id). The brief says to reuse it and only export it. The refresh needs guests of one reservation. Owner choice: (a) extract that query and decrypt loop into an exported function with a reservation or apartment filter, and have `CollectSendable` call it (touches 0556 code, needs 0556 tests to stay green); or (b) allow a reservation-scoped loader as a second copy (the brief forbids this).
2. Confirm the `today` change: `GuestIsComplete` gets the UTC date of `now()` instead of the Prague date now used in `CollectSendable`. This changes 0556 behaviour near midnight, so it should be decided with question 1.

## Owner steps left
None. Nothing pushed.
