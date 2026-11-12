# 1148b: iCal cancel with a `running` or `outcome_unknown` filing (K-F20), Go twin of 1148

Status: review
Depends on: 1148 | Base commit: 21c87fc6 (HEAD of branch claude/zealous-maxwell-a7ub54) | Branch: task/1148b-ical-cancel-running-go
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

HIGH RISK filing path: the reviewer reads every diff line in the Risk list.

## 1. Objective

Make the Go iCal sync (`go/internal/ical`) behave exactly as Python does after brief 1148: a `running` submission younger than 30 minutes (no live claim) defers a cancel; otherwise the cancel proceeds and, when a guest of the stay is in a `running` or `outcome_unknown` filing, raises the warning alert `cancelled_filing_unconfirmed`. The copy keys already exist (1148 step 4); Go only writes the alert row with params.

## 2. Context

Read the simulation table and the reasoning in `docs/tasks/1148-ical-cancel-unclaimed-running.md` §2 (T1 to T9); it is not repeated here. Python names to match: `RUNNING_CANCEL_DEFER_SECONDS`, `_pointed_at_open_submission`, `_running_submission_covers_stay`, `_running_defers_cancel`, `_alert_if_filing_in_doubt`.

Facts for Go: `submission.guest_ids` and `submission.created_at` are `text` columns (checked in Postgres). `created_at` is written as `2006-01-02T15:04:05+00:00` (`ubyport.UTCNow`, store.go:76), so a text compare against a cutoff in the same format is correct. A guest is not pointed at a `running` row (only `outcome_unknown`), so `running` is found through `guest_ids` (JSON array of ints). `exists(ctx, pool, sql, args...)` and `guestSent` already exist in `go/internal/ical/reconcile.go`. `ubyport.RaiseAlert(ctx, pool, level, kind, message, detail, dedupeKey, &aid, &rid, nil, ubyport.AlertParams{...})` is the alert writer; the card is rendered by Python from the params.

Anchors, current code (`go/internal/ical/reconcile.go`):

Imports start:
```go
import (
	"context"
	"errors"
	"fmt"
```
`sendInFlight` ends (~line 138 to 148):
```go
	return exists(ctx, pool,
		`SELECT 1 FROM guest g JOIN submission s ON s.id = g.submission_id
		  WHERE g.reservation_id = $1 AND g.archived_at IS NULL
		    AND g.submit_state <> $2 AND s.state IN ('running', 'outcome_unknown') LIMIT 1`,
		reservationID, guestSent)
}
```
`cancelExistingStay` (~line 370 to 392):
```go
	cancelled, err := cancelReservationUnlessClaimed(ctx, pool, res.ID, ubyport.UTCNow())
	if err != nil {
		return false, err
	}
	if !cancelled {
		log.Printf("ical_cancel_deferred_in_flight apartment_id=%d reservation_id=%d", apartmentID, res.ID)
		return true, nil
	}
	if err := expireOnCancel(ctx, pool, res.ID); err != nil {
		return false, err
	}
	if err := warnIfGuestsRegistered(ctx, pool, getenv, res, apartmentID, "cancelled"); err != nil {
```
`go/internal/ical/syncfeed.go` sweep (~575 to 592):
```go
		cancelled, err := cancelReservationUnlessClaimed(ctx, pool, r.ID, now)
		if err != nil {
			return stats, err
		}
		if !cancelled {
			deferredInFlight = true
			log.Printf("ical_cancel_deferred_in_flight apartment_id=%d reservation_id=%d", feed.ApartmentID, r.ID)
			continue
		}
		if err := expireOnCancel(ctx, pool, r.ID); err != nil {
			return stats, err
		}
		if err := warnIfGuestsRegistered(ctx, pool, getenv,
			reservationRow{ID: r.ID, DateFrom: r.DateFrom}, feed.ApartmentID, "disappeared"); err != nil {
```
Test helpers: `testPool`, `seedApartment`, `newIcalFeed`, `seedStay(t, pool, aid, feedID, uid, from, to)`, `seedGuest(t, pool, stay, state, from, to) int64`, `runSync(t, pool, feed, doc)`, `icsDoc`, `icsEvent(uid, from, to, summary, extra...)`, `scalarText`, `scalarInt`, `openAlerts(t, pool, key)`, `epochSeconds`, `must` (see `TestSyncFeedCancelEventDeferredWhileClaimLive` and `TestSyncFeedVanishedStayDeferredWhileClaimLive` in syncfeed_test.go for the exact shape; the new tests copy them).

## 3. Files

| Path | Action | What |
|---|---|---|
| go/internal/ical/reconcile.go | edit | import, 5 helpers, `sendInFlight` tail, `cancelExistingStay` |
| go/internal/ical/syncfeed.go | edit | sweep call site |
| go/internal/ical/syncfeed_test.go | edit | imports if needed, helpers, 6 tests |
| docs/context/known-issues.md | edit | close K-F20 |
| docs/tasks/1148b-ical-cancel-unclaimed-running-go.md | status | `review` at the end |
| docs/tasks/1148b-report.md | create | report |

No other file may change.

## 4. Steps

Commit after each step: `git add -A && git commit -qm "1148b step N"`. Go tests need `UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest` and run from `go/`.

**Step 1. Helpers in reconcile.go.**
(a) In the import block replace `	"context"\n	"errors"\n` with `	"context"\n	"encoding/json"\n	"errors"\n`.
(b) Replace the tail of `sendInFlight` quoted in §2 (from `	return exists(ctx, pool,` with the `submission s` query, to its closing `}`) with:
```go
	return pointedAtOpenSubmission(ctx, pool, reservationID)
}

// runningCancelDefer is Python RUNNING_CANCEL_DEFER_SECONDS: a cancel waits for
// a running batch whose claim is gone only this long.
const runningCancelDefer = 30 * time.Minute

// pointedAtOpenSubmission is Python _pointed_at_open_submission: an unsent
// guest of the stay points at a running or outcome_unknown batch.
func pointedAtOpenSubmission(ctx context.Context, pool *pgxpool.Pool, reservationID int64) (bool, error) {
	return exists(ctx, pool,
		`SELECT 1 FROM guest g JOIN submission s ON s.id = g.submission_id
		  WHERE g.reservation_id = $1 AND g.archived_at IS NULL
		    AND g.submit_state <> $2 AND s.state IN ('running', 'outcome_unknown') LIMIT 1`,
		reservationID, guestSent)
}

// runningSubmissionCoversStay is Python _running_submission_covers_stay: a
// running batch of this apartment lists an unsent guest of the stay. A guest is
// not pointed at a running batch, so submission.guest_ids (JSON) is the link.
// newerThan, when not empty, limits the rows by created_at (same text format).
func runningSubmissionCoversStay(ctx context.Context, pool *pgxpool.Pool, reservationID int64, newerThan string) (bool, error) {
	rows, err := pool.Query(ctx,
		`SELECT id FROM guest WHERE reservation_id = $1 AND archived_at IS NULL AND submit_state <> $2`,
		reservationID, guestSent)
	if err != nil {
		return false, err
	}
	guests := map[int64]bool{}
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			rows.Close()
			return false, err
		}
		guests[id] = true
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return false, err
	}
	if len(guests) == 0 {
		return false, nil
	}
	sql := `SELECT s.guest_ids FROM submission s JOIN reservation r ON r.apartment_id = s.apartment_id
	         WHERE r.id = $1 AND s.state = 'running'`
	args := []any{reservationID}
	if newerThan != "" {
		sql += ` AND s.created_at >= $2`
		args = append(args, newerThan)
	}
	subs, err := pool.Query(ctx, sql, args...)
	if err != nil {
		return false, err
	}
	defer subs.Close()
	for subs.Next() {
		var raw *string
		if err := subs.Scan(&raw); err != nil {
			return false, err
		}
		if raw == nil || *raw == "" {
			continue
		}
		var listed []int64
		if json.Unmarshal([]byte(*raw), &listed) != nil {
			continue
		}
		for _, id := range listed {
			if guests[id] {
				return true, nil
			}
		}
	}
	return false, subs.Err()
}

// runningDefersCancel is Python _running_defers_cancel.
func runningDefersCancel(ctx context.Context, pool *pgxpool.Pool, reservationID int64) (bool, error) {
	cutoff := time.Now().UTC().Add(-runningCancelDefer).Format("2006-01-02T15:04:05") + "+00:00"
	return runningSubmissionCoversStay(ctx, pool, reservationID, cutoff)
}

// alertIfFilingInDoubt is Python _alert_if_filing_in_doubt: after a cancel, tell
// the host the register may hold this stay's guests.
func alertIfFilingInDoubt(ctx context.Context, pool *pgxpool.Pool, res reservationRow, apartmentID int64) error {
	doubt, err := pointedAtOpenSubmission(ctx, pool, res.ID)
	if err != nil {
		return err
	}
	if !doubt {
		if doubt, err = runningSubmissionCoversStay(ctx, pool, res.ID, ""); err != nil {
			return err
		}
	}
	if !doubt {
		return nil
	}
	aid, rid := apartmentID, res.ID
	return ubyport.RaiseAlert(ctx, pool, "warning", "cancelled_filing_unconfirmed",
		fmt.Sprintf("A stay from %s was cancelled in the calendar while the report of its guests to the police was unconfirmed.", res.DateFrom),
		"Check in UbyPort whether the guests are listed.",
		fmt.Sprintf("cancelled_filing_unconfirmed:%d", res.ID), &aid, &rid, nil,
		ubyport.AlertParams{"date": res.DateFrom})
}
```
Command: `cd go && go build ./internal/ical/ && gofmt -l internal/ical/ 2>&1 | tail -30`. Expected: silent.

**Step 2. Event call site.** In `cancelExistingStay` replace the quoted block (from `	cancelled, err := cancelReservationUnlessClaimed(ctx, pool, res.ID, ubyport.UTCNow())` to the `warnIfGuestsRegistered` `if` block's first line) with:
```go
	deferRunning, err := runningDefersCancel(ctx, pool, res.ID)
	if err != nil {
		return false, err
	}
	cancelled := false
	if !deferRunning {
		if cancelled, err = cancelReservationUnlessClaimed(ctx, pool, res.ID, ubyport.UTCNow()); err != nil {
			return false, err
		}
	}
	if !cancelled {
		log.Printf("ical_cancel_deferred_in_flight apartment_id=%d reservation_id=%d", apartmentID, res.ID)
		return true, nil
	}
	if err := expireOnCancel(ctx, pool, res.ID); err != nil {
		return false, err
	}
	if err := alertIfFilingInDoubt(ctx, pool, res, apartmentID); err != nil {
		return false, err
	}
	if err := warnIfGuestsRegistered(ctx, pool, getenv, res, apartmentID, "cancelled"); err != nil {
```
Command: `cd go && go build ./internal/ical/ 2>&1 | tail -30`. Expected: silent.

**Step 3. Sweep call site.** In syncfeed.go replace the sweep block quoted in §2 with:
```go
		deferRunning, err := runningDefersCancel(ctx, pool, r.ID)
		if err != nil {
			return stats, err
		}
		cancelled := false
		if !deferRunning {
			if cancelled, err = cancelReservationUnlessClaimed(ctx, pool, r.ID, now); err != nil {
				return stats, err
			}
		}
		if !cancelled {
			deferredInFlight = true
			log.Printf("ical_cancel_deferred_in_flight apartment_id=%d reservation_id=%d", feed.ApartmentID, r.ID)
			continue
		}
		if err := expireOnCancel(ctx, pool, r.ID); err != nil {
			return stats, err
		}
		if err := alertIfFilingInDoubt(ctx, pool,
			reservationRow{ID: r.ID, DateFrom: r.DateFrom}, feed.ApartmentID); err != nil {
			return stats, err
		}
		if err := warnIfGuestsRegistered(ctx, pool, getenv,
			reservationRow{ID: r.ID, DateFrom: r.DateFrom}, feed.ApartmentID, "disappeared"); err != nil {
```
Command: `cd go && go build ./internal/ical/ && go vet ./internal/ical/ && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ical/ -count=1 2>&1 | tail -30`. Expected: `ok`.

**Step 4. Tests.** Append to `go/internal/ical/syncfeed_test.go` (add `"encoding/json"` only if the compiler asks; the code below does not need it):
```go
func seedSubmission(t *testing.T, pool *pgxpool.Pool, aid, guestID int64, state string, age time.Duration, point bool) int64 {
	t.Helper()
	created := time.Now().UTC().Add(-age).Format("2006-01-02T15:04:05") + "+00:00"
	var id int64
	must(t, pool.QueryRow(context.Background(),
		`INSERT INTO submission (apartment_id, created_at, mode, state, guest_ids)
		 VALUES ($1, $2, 'auto', $3, $4) RETURNING id`,
		aid, created, state, fmt.Sprintf("[%d]", guestID)).Scan(&id))
	if point {
		_, err := pool.Exec(context.Background(), `UPDATE guest SET submission_id = $1 WHERE id = $2`, id, guestID)
		must(t, err)
	}
	return id
}

func TestSyncFeedCancelEventWithUnconfirmedFilingCancelsAndAlerts(t *testing.T) {
	pool := testPool(t)
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/cancel-unknown.ics")
	stay := seedStay(t, pool, aid, feed.ID, "u-cu", "2999-03-01", "2999-03-05")
	g := seedGuest(t, pool, stay, "pending", "2999-03-01", "2999-03-05")
	seedSubmission(t, pool, aid, g, "outcome_unknown", 0, true)
	doc := icsDoc(icsEvent("u-cu", "29990301", "29990305", "Guest A", "STATUS:CANCELLED"))

	st := runSync(t, pool, feed, doc)

	if got := scalarText(t, pool, `SELECT status FROM reservation WHERE id = $1`, stay); got != "cancelled" || st.Cancelled != 1 {
		t.Errorf("status = %q, Cancelled = %d, want cancelled and 1", got, st.Cancelled)
	}
	if n := openAlerts(t, pool, fmt.Sprintf("cancelled_filing_unconfirmed:%d", stay)); n != 1 {
		t.Errorf("cancelled_filing_unconfirmed alerts = %d, want 1", n)
	}
}

func TestSyncFeedCancelEventWithSettledFilingRaisesNoUnconfirmedAlert(t *testing.T) {
	pool := testPool(t)
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/cancel-ok.ics")
	stay := seedStay(t, pool, aid, feed.ID, "u-co", "2999-03-01", "2999-03-05")
	g := seedGuest(t, pool, stay, "pending", "2999-03-01", "2999-03-05")
	seedSubmission(t, pool, aid, g, "ok", 0, true)
	doc := icsDoc(icsEvent("u-co", "29990301", "29990305", "Guest A", "STATUS:CANCELLED"))

	runSync(t, pool, feed, doc)

	if got := scalarText(t, pool, `SELECT status FROM reservation WHERE id = $1`, stay); got != "cancelled" {
		t.Errorf("status = %q, want cancelled", got)
	}
	if n := openAlerts(t, pool, fmt.Sprintf("cancelled_filing_unconfirmed:%d", stay)); n != 0 {
		t.Errorf("alerts = %d, want 0", n)
	}
}

func TestSyncFeedFreshRunningFilingDefersTheCancel(t *testing.T) {
	pool := testPool(t)
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/cancel-running.ics")
	stay := seedStay(t, pool, aid, feed.ID, "u-cr", "2999-03-01", "2999-03-05")
	g := seedGuest(t, pool, stay, "pending", "2999-03-01", "2999-03-05")
	sub := seedSubmission(t, pool, aid, g, "running", 0, false)
	_, err := pool.Exec(context.Background(),
		`INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES ($1, 'old', $2)`, g, epochSeconds()-3600)
	must(t, err)
	doc := icsDoc(icsEvent("u-cr", "29990301", "29990305", "Guest A", "STATUS:CANCELLED"))

	st := runSync(t, pool, feed, doc)

	if got := scalarText(t, pool, `SELECT status FROM reservation WHERE id = $1`, stay); got != "active" || st.Cancelled != 0 {
		t.Errorf("status = %q, Cancelled = %d, want active and 0", got, st.Cancelled)
	}
	if got := scalarText(t, pool, `SELECT COALESCE(body_sha256, '') FROM ical_feed WHERE id = $1`, feed.ID); got != "" {
		t.Errorf("digest stored after a deferred cancel: %q", got)
	}
	if n := openAlerts(t, pool, fmt.Sprintf("cancelled_filing_unconfirmed:%d", stay)); n != 0 {
		t.Errorf("alerts = %d, want 0 while deferred", n)
	}

	_, err = pool.Exec(context.Background(), `UPDATE submission SET state = 'outcome_unknown' WHERE id = $1`, sub)
	must(t, err)
	_, err = pool.Exec(context.Background(), `UPDATE guest SET submission_id = $1 WHERE id = $2`, sub, g)
	must(t, err)

	st = runSync(t, pool, feed, doc)

	if got := scalarText(t, pool, `SELECT status FROM reservation WHERE id = $1`, stay); got != "cancelled" || st.Cancelled != 1 {
		t.Errorf("after recovery: status = %q, Cancelled = %d, want cancelled and 1", got, st.Cancelled)
	}
	if n := openAlerts(t, pool, fmt.Sprintf("cancelled_filing_unconfirmed:%d", stay)); n != 1 {
		t.Errorf("alerts = %d, want 1", n)
	}
}

func TestSyncFeedOldRunningFilingDoesNotHoldTheCancel(t *testing.T) {
	pool := testPool(t)
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/cancel-old-running.ics")
	stay := seedStay(t, pool, aid, feed.ID, "u-cold", "2999-03-01", "2999-03-05")
	g := seedGuest(t, pool, stay, "pending", "2999-03-01", "2999-03-05")
	seedSubmission(t, pool, aid, g, "running", 2*time.Hour, false)
	doc := icsDoc(icsEvent("u-cold", "29990301", "29990305", "Guest A", "STATUS:CANCELLED"))

	st := runSync(t, pool, feed, doc)

	if got := scalarText(t, pool, `SELECT status FROM reservation WHERE id = $1`, stay); got != "cancelled" || st.Cancelled != 1 {
		t.Errorf("status = %q, Cancelled = %d, want cancelled and 1", got, st.Cancelled)
	}
	if n := openAlerts(t, pool, fmt.Sprintf("cancelled_filing_unconfirmed:%d", stay)); n != 1 {
		t.Errorf("alerts = %d, want 1", n)
	}
}

func TestSyncFeedVanishedStayWithUnconfirmedFilingCancelsAndAlerts(t *testing.T) {
	pool := testPool(t)
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/vanish-unknown.ics")
	seedStay(t, pool, aid, feed.ID, "u1", "2999-03-01", "2999-03-05")
	gone := seedStay(t, pool, aid, feed.ID, "u2", "2999-04-01", "2999-04-05")
	g := seedGuest(t, pool, gone, "pending", "2999-04-01", "2999-04-05")
	seedSubmission(t, pool, aid, g, "outcome_unknown", 0, true)
	doc := icsDoc(icsEvent("u1", "29990301", "29990305", "Guest A"))

	st := runSync(t, pool, feed, doc)

	if got := scalarText(t, pool, `SELECT status FROM reservation WHERE id = $1`, gone); got != "cancelled" || st.Cancelled != 1 {
		t.Errorf("status = %q, Cancelled = %d, want cancelled and 1", got, st.Cancelled)
	}
	if n := openAlerts(t, pool, fmt.Sprintf("cancelled_filing_unconfirmed:%d", gone)); n != 1 {
		t.Errorf("alerts = %d, want 1", n)
	}
}

func TestSyncFeedVanishedStayWithFreshRunningFilingIsDeferred(t *testing.T) {
	pool := testPool(t)
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/vanish-running.ics")
	seedStay(t, pool, aid, feed.ID, "u1", "2999-03-01", "2999-03-05")
	gone := seedStay(t, pool, aid, feed.ID, "u2", "2999-04-01", "2999-04-05")
	g := seedGuest(t, pool, gone, "pending", "2999-04-01", "2999-04-05")
	seedSubmission(t, pool, aid, g, "running", 0, false)
	doc := icsDoc(icsEvent("u1", "29990301", "29990305", "Guest A"))

	st := runSync(t, pool, feed, doc)

	if got := scalarText(t, pool, `SELECT status FROM reservation WHERE id = $1`, gone); got != "active" || st.Cancelled != 0 {
		t.Errorf("status = %q, Cancelled = %d, want active and 0", got, st.Cancelled)
	}
	if got := scalarText(t, pool, `SELECT COALESCE(body_sha256, '') FROM ical_feed WHERE id = $1`, feed.ID); got != "" {
		t.Errorf("digest stored after a deferred cancel: %q", got)
	}
}
```
Command: `cd go && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ical/ -run 'UnconfirmedFiling|SettledFiling|FreshRunning|OldRunning' -count=1 -v 2>&1 | grep -E '^(--- |ok|FAIL)' | tail -30`. Expected: 6 `--- PASS`, then `ok`.

**Step 5. Revert bite.**
(a) In `reconcile.go` insert `	return nil` as the first statement of `alertIfFilingInDoubt` (by hand, with Edit). Run the Step 4 command: expected FAIL for `UnconfirmedFiling` (both), `OldRunning` and `FreshRunning` (its second half). Restore: `git checkout go/internal/ical/reconcile.go`; rerun: PASS.
(b) In `runningDefersCancel` insert `	return false, nil` as the first statement. Run the Step 4 command: expected FAIL for `FreshRunning` tests (both). Restore with `git checkout go/internal/ical/reconcile.go`; rerun: PASS.

**Step 6. Area run, docs.**
`cd go && gofmt -l internal/ical/ && go vet ./internal/ical/ && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ical/ -count=1 -v 2>&1 | grep -c SKIP` : expected silent, silent, `0`. Then the full package: same without `-v`/grep, `| tail -30`: `ok`.
In `docs/context/known-issues.md` replace the line starting `- K-F20 (1139):` with `- K-F20 closed (1148, 1148b): a fresh running filing defers an iCal cancel; a cancel over a running or outcome_unknown filing raises cancelled_filing_unconfirmed.` Command: `grep -c 'K-F20 closed' docs/context/known-issues.md`. Expected `1`. Then from the repo root `python3 scripts/context_lint.py | tail -3`: OK.

## 5. Do not touch

`go/internal/ubyport`, `claim.go`, Python files, copy files, migrations. Hard rules: 1, 4, 5 (SQL stays parameterised, Postgres only here).

## 6. Commands

Those in each step. No full Go suite beyond `./internal/ical/`.

## 7. Acceptance

- [ ] Event and sweep both go through `runningDefersCancel` and `alertIfFilingInDoubt`; `sendInFlight` behaviour unchanged.
- [ ] 6 new tests pass against Postgres, 0 SKIP; both bites fail then pass.
- [ ] vet and gofmt silent; K-F20 closed; lint OK; only §3 files changed.

## 8. Stop and ask

Stop, and write the report, if: an excerpt is not found; a test fails twice; you reach 25 tool calls or about 50k tokens (report as `blocked`); a new dependency seems needed; a file outside §3 needs a change; §5 would be touched; a step is unclear.

## 9. Report

Write `docs/tasks/1148b-report.md` (600 tokens at most), set `Status: review`: files changed, each command with the last 5 lines, §7 ticked, bite results, deviations, questions, owner steps left (push, draft PR, merge both 1148 and 1148b with `scripts/merge-pr-on-green.sh`).

## Risk list (for the reviewer)

`runningSubmissionCoversStay` (JSON overlap, text cutoff), the two call sites (a deferred sweep keeps `deferredInFlight`), `alertIfFilingInDoubt` (dedupe key equals Python's).

## Owner steps

1. Nothing before review.
