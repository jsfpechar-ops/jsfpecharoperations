# 1150b: iCal date move over a crash-stuck `running` filing (K-F22), Go twin of 1150

Status: review
Depends on: 1150 | Base commit: a176c3ee (HEAD of branch claude/zealous-maxwell-a7ub54) | Branch: task/1150b-ical-move-running-go
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

HIGH RISK filing path: the reviewer reads every diff line in the Risk list.

## 1. Objective

Make the Go iCal sync (`go/internal/ical`) behave exactly as Python does after brief 1150: a date move is deferred (stored dates and guest windows kept, digest not stored) while a `running` submission of any age lists an unsent guest of the stay, even though no guest points at it. Today `sendInFlight` only sees a live claim or a guest pointed at the row, so a crash-stuck `running` batch lets the move land.

## 2. Context

Read `docs/tasks/1150-ical-move-unclaimed-running.md` §2 for the reasoning and the decision (no age limit for a move; no new alert, no copy, no cancel change). Go has no copy to add.

Where the guard is used: `go/internal/ical/syncfeed.go` ~393 calls `sendInFlightFn(ctx, pool, s.ID)` (a test seam for `sendInFlight`) for every changed-dates stay. `sendInFlight` lives in `go/internal/ical/reconcile.go` and ends in `pointedAtOpenSubmission`. `runningSubmissionCoversStay(ctx, pool, reservationID, newerThan string) (bool, error)` already exists there (from 1148b); an empty `newerThan` means no age limit. It is not changed.

Anchor, current code (`go/internal/ical/reconcile.go`, the whole of `sendInFlight` with its comment):
```go
// sendInFlight is _send_in_flight (icalsync.py 372-405): true while a live
// claim, or a running or outcome_unknown submission, still covers the stay.
func sendInFlight(ctx context.Context, pool *pgxpool.Pool, reservationID int64) (bool, error) {
	live, err := exists(ctx, pool,
		`SELECT 1 FROM submission_claim c JOIN guest g ON g.id = c.guest_id
		  WHERE g.reservation_id = $1 AND g.archived_at IS NULL AND c.claimed_at >= $2 LIMIT 1`,
		reservationID, liveClaimAfter())
	if err != nil || live {
		return live, err
	}
	return pointedAtOpenSubmission(ctx, pool, reservationID)
}
```

Existing tests that mask the bug (they point the guest at the `running` row, which a real crash never does): `TestSendInFlight` in reconcile_test.go (the `running` block) and `TestSyncFeedDatesInFlightKeepsDigest` in syncfeed_test.go. Leave them as they are; they stay valid. Test helpers, all in package `ical` tests: `testPool`, `seedApartment`, `newIcalFeed`, `seedStay(t, pool, aid, feedID, uid, from, to)`, `seedReservation(t, pool, aid, uid, from, to)`, `seedGuest(t, pool, reservationID, submitState, from, to) int64`, `seedSubmission(t, pool, aid, guestID, state, age time.Duration, point bool) int64` (syncfeed_test.go, from 1148b), `runSync(t, pool, feed, doc)`, `icsDoc`, `icsEvent`, `scalarText`, `openAlerts`, `must`. `reconcile_test.go` and `syncfeed_test.go` already import `time` and `fmt`.

## 3. Files

| Path | Action | What |
|---|---|---|
| go/internal/ical/reconcile.go | edit | `sendInFlight` comment and tail |
| go/internal/ical/reconcile_test.go | edit | 1 test appended |
| go/internal/ical/syncfeed_test.go | edit | 2 tests appended |
| docs/context/known-issues.md | edit | close K-F22 |
| docs/tasks/1150b-ical-move-unclaimed-running-go.md | status | `review` at the end |
| docs/tasks/1150b-report.md | create | report |

No other file may change.

## 4. Steps

Commit after each step: `git add -A && git commit -qm "1150b step N"`. Run Go commands from `go/` with `UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest`.

**Step 1. Tests first (they must fail before the fix).**
(a) Append to `go/internal/ical/reconcile_test.go`:
```go

func TestSendInFlightFindsACrashStuckRunningBatchByGuestIDs(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	apt := seedApartment(t, pool)

	stuck := seedReservation(t, pool, apt, "u-stuck", "2026-08-01", "2026-08-03")
	g := seedGuest(t, pool, stuck, "pending", "2026-08-01", "2026-08-03")
	sub := seedSubmission(t, pool, apt, g, "running", 0, false)
	if got, err := sendInFlight(ctx, pool, stuck); err != nil || !got {
		t.Fatalf("unpointed running batch: got %v, %v", got, err)
	}

	old := seedReservation(t, pool, apt, "u-old", "2026-09-01", "2026-09-03")
	gOld := seedGuest(t, pool, old, "pending", "2026-09-01", "2026-09-03")
	seedSubmission(t, pool, apt, gOld, "running", 3*time.Hour, false)
	if got, err := sendInFlight(ctx, pool, old); err != nil || !got {
		t.Fatalf("old running batch: got %v, %v", got, err)
	}

	other := seedReservation(t, pool, apt, "u-other", "2026-10-01", "2026-10-03")
	seedGuest(t, pool, other, "pending", "2026-10-01", "2026-10-03")
	if got, err := sendInFlight(ctx, pool, other); err != nil || got {
		t.Fatalf("running batch of another stay: got %v, %v", got, err)
	}

	sentRes := seedReservation(t, pool, apt, "u-sent", "2026-11-01", "2026-11-03")
	gSent := seedGuest(t, pool, sentRes, "sent", "2026-11-01", "2026-11-03")
	seedSubmission(t, pool, apt, gSent, "running", 0, false)
	if got, err := sendInFlight(ctx, pool, sentRes); err != nil || got {
		t.Fatalf("running batch listing only a sent guest: got %v, %v", got, err)
	}

	_, err := pool.Exec(ctx, `UPDATE submission SET state = 'ok' WHERE id = $1`, sub)
	must(t, err)
	if got, err := sendInFlight(ctx, pool, stuck); err != nil || got {
		t.Fatalf("settled batch: got %v, %v", got, err)
	}
}
```
(b) Append to `go/internal/ical/syncfeed_test.go`:
```go

func TestSyncFeedDateMoveWaitsForCrashStuckRunningBatchThenLands(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/move-running.ics")
	stay := seedStay(t, pool, aid, feed.ID, "u-mr", "2999-03-01", "2999-03-05")
	g := seedGuest(t, pool, stay, "pending", "2999-03-01", "2999-03-05")
	sub := seedSubmission(t, pool, aid, g, "running", 0, false)
	doc := icsDoc(icsEvent("u-mr", "29990302", "29990306", "Guest A"))

	runSync(t, pool, feed, doc)

	if got := scalarText(t, pool, `SELECT date_from FROM reservation WHERE id = $1`, stay); got != "2999-03-01" {
		t.Errorf("stay moved over a crash-stuck running batch: %q", got)
	}
	if got := scalarText(t, pool, `SELECT stay_from FROM guest WHERE id = $1`, g); got != "2999-03-01" {
		t.Errorf("guest window moved over a crash-stuck running batch: %q", got)
	}
	if got := scalarText(t, pool, `SELECT COALESCE(body_sha256, '') FROM ical_feed WHERE id = $1`, feed.ID); got != "" {
		t.Errorf("digest stored while deferred: %q", got)
	}

	_, err := pool.Exec(ctx, `UPDATE submission SET state = 'ok' WHERE id = $1`, sub)
	must(t, err)

	runSync(t, pool, feed, doc)

	if got := scalarText(t, pool, `SELECT date_from FROM reservation WHERE id = $1`, stay); got != "2999-03-02" {
		t.Errorf("after the batch settled: date_from = %q, want 2999-03-02", got)
	}
}

func TestSyncFeedOldRunningBatchStillDefersTheDateMove(t *testing.T) {
	pool := testPool(t)
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/move-old-running.ics")
	stay := seedStay(t, pool, aid, feed.ID, "u-mo", "2999-03-01", "2999-03-05")
	g := seedGuest(t, pool, stay, "pending", "2999-03-01", "2999-03-05")
	seedSubmission(t, pool, aid, g, "running", 3*time.Hour, false)

	runSync(t, pool, feed, icsDoc(icsEvent("u-mo", "29990302", "29990306", "Guest A")))

	if got := scalarText(t, pool, `SELECT date_from FROM reservation WHERE id = $1`, stay); got != "2999-03-01" {
		t.Errorf("stay moved over an old running batch: %q", got)
	}
	if n := openAlerts(t, pool, fmt.Sprintf("moved_after_report:%d", stay)); n != 0 {
		t.Errorf("moved_after_report alerts = %d, want 0", n)
	}
}
```
Command: `cd go && gofmt -l internal/ical/ && go vet ./internal/ical/ && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ical/ -run 'CrashStuckRunning|OldRunningBatchStillDefers' -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30`. Expected (fix not yet applied): three `--- FAIL`, then `FAIL`.

**Step 2. The fix in reconcile.go.** Replace the comment and the last line of `sendInFlight`.
Comment, old:
```go
// sendInFlight is _send_in_flight (icalsync.py 372-405): true while a live
// claim, or a running or outcome_unknown submission, still covers the stay.
```
Comment, new:
```go
// sendInFlight is _send_in_flight (icalsync.py 373-405): true while a live
// claim, an outcome_unknown submission the guest points at, or a running
// submission that lists an unsent guest of the stay (a crash leaves the guest
// unpointed, so guest_ids is the only link; no age limit) still covers the stay.
```
Last line, old: `	return pointedAtOpenSubmission(ctx, pool, reservationID)` followed by the closing `}` and then the blank line and `// runningCancelDefer is Python`. Use as the unique anchor the three lines
```go
	return pointedAtOpenSubmission(ctx, pool, reservationID)
}

// runningCancelDefer
```
new:
```go
	pointed, err := pointedAtOpenSubmission(ctx, pool, reservationID)
	if err != nil || pointed {
		return pointed, err
	}
	return runningSubmissionCoversStay(ctx, pool, reservationID, "")
}

// runningCancelDefer
```
(`live, err :=` is declared earlier in the function, so `pointed, err :=` is valid: `pointed` is new.)
Command: `cd go && gofmt -l internal/ical/ && go vet ./internal/ical/ && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ical/ -count=1 2>&1 | tail -30`. Expected: `ok`.

**Step 3. Revert bites.** Commit step 2 first. Run (R) = `cd go && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ical/ -run 'CrashStuckRunning|OldRunningBatchStillDefers' -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30`.
(a) Replace the final line `	return runningSubmissionCoversStay(ctx, pool, reservationID, "")` of `sendInFlight` with `	return false, nil`. Run (R). Expected: three `--- FAIL`. `git checkout go/internal/ical/reconcile.go`; (R): three `--- PASS`, `ok`.
(b) Replace the same line with ``	return exists(ctx, pool, `SELECT 1 FROM submission WHERE state = 'running' LIMIT 1`)``. Run (R). Expected: only `TestSendInFlightFindsACrashStuckRunningBatchByGuestIDs` FAILS (the sync tests have no over-deferral case; the unit test covers it). `git checkout go/internal/ical/reconcile.go`; (R): all PASS.

**Step 4. Area run, docs.**
`cd go && gofmt -l internal/ical/ && go vet ./internal/ical/ && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ical/ -count=1 -v 2>&1 | grep -c SKIP`: expected silent, silent, `0`. Then the same without `-v`/grep, `| tail -30`: `ok`.
In `docs/context/known-issues.md` replace the line starting `- K-F22 (937 review):` (the whole line) with `- K-F22 closed (1150, 1150b): an iCal date move now waits for a crash-stuck running filing (found through submission.guest_ids, any age), same as for outcome_unknown.` Command: `grep -c 'K-F22 closed' docs/context/known-issues.md`. Expected `1`. Then from the repo root `python3 scripts/context_lint.py | tail -3`: OK.

## 5. Do not touch

`go/internal/ubyport`, `claim.go`, `runningSubmissionCoversStay`, `runningDefersCancel`, `alertIfFilingInDoubt`, `pointedAtOpenSubmission`, `syncfeed.go`, Python files, copy files, migrations. Hard rules: 1, 4, 5 (SQL stays parameterised, Postgres only here).

## 6. Commands

Those in each step. Only `./internal/ical/`; no full Go suite.

## 7. Acceptance

- [ ] `sendInFlight` is true for an unpointed `running` row listing an unsent guest of the stay, of any age; false for another stay's guest, a `sent` guest only, or a settled row.
- [ ] 3 new tests pass against Postgres, 0 SKIP; bite (a) fails 3, bite (b) fails 1, each then passes.
- [ ] vet and gofmt silent; K-F22 closed; lint OK; only §3 files changed.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear.

## 9. Report

Write `docs/tasks/1150b-report.md` (600 tokens at most), set `Status: review`: files changed, each command with the last 5 lines, §7 ticked, bite results, deviations, questions, owner steps left (push, draft PR, merge 1150 and 1150b with `scripts/merge-pr-on-green.sh`).

## Risk list (for the reviewer)

The `sendInFlight` tail (no cutoff on purpose, same as Python), the reuse of `runningSubmissionCoversStay` with an empty `newerThan`, the existing masking tests left unchanged.

## Owner steps

1. Nothing before review.
