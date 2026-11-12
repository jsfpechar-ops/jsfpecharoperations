# 1133: iCal date move: close the claim race on the reservation row

Status: blocked
Depends on: none | Base commit: 7b8ff2ae | Branch: task/1133-ical-claim-race
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The calendar sync must never write new `date_from`/`date_to` on a reservation while a live `submission_claim` covers one of its guests. Today the check (`_send_in_flight` / `sendInFlight`) and the write are two separate statements, so a claim taken in between lets the date move land mid-send. Make the write itself conditional (one atomic UPDATE) and skip the move this pass; the next sync retries.

## 2. Context

Filing correctness beats every other feature (UBYPORT_CORE). Known issue K-F02 says "Date move ignores submission_claim". Reading the code at the base commit shows it is **partly stale**: a pre-check and a guarded guest-window UPDATE already exist. The remaining gap is a read-then-write race on the **reservation** row.

**Which copy runs.** status.md: the `ical` job runs in Go (`go/internal/ical/syncfeed.go`). The Python copy (`App/app/icalsync.py`) still runs when a host opens the app (`sync_owner_if_stale`) and in `sync_feed` callers. Fix both.

Already guarded (do NOT change): `_fit_unsent_guest_windows` (icalsync.py) and `fitUnsentGuestWindows` (reconcile.go) use `NOT EXISTS (SELECT 1 FROM submission_claim WHERE guest_id = ... AND claimed_at >= live)` in the UPDATE. Claims live for `SUBMISSION_CLAIM_TTL_SECONDS` (Go: `ubyport.SubmissionClaimTTL`, 5 min); live means `claimed_at >= time.time() - TTL`.

The race, Python, `App/app/icalsync.py` (sync_feed, existing-reservation branch):

```python
            if dates_changed and _send_in_flight(existing["id"]):
...
            if changed:
                changed["updated_at"] = now
                db.update("reservation", existing["id"], changed)
                stats["updated"] += 1
```

The race, Go, `go/internal/ical/syncfeed.go` (SyncFeed loop):

```go
		if len(changed) > 0 {
			changed["updated_at"] = now
			if err := updateRow(ctx, pool, "reservation", s.ID, changed); err != nil {
				return stats, err
			}
			stats.Updated++
		}
```

Tools that exist: `db.update_if(table, id, values, expected, extra_where, extra_params)` (db.py 2059, compare-and-set, True when rowcount is 1); Go `liveClaimAfter()` (reconcile.go), `updateRow` (syncfeed.go 72).

No `test_sm_*` pin test reads this SQL (checked: `test_sm_go_parity.py` has no ical entry), so no pin update is needed.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/icalsync.py | edit | add helper `_update_reservation_unless_claimed`; use it for date moves |
| App/tests/test_icalsync.py | edit | add regression test (append at end of file) |
| go/internal/ical/syncfeed.go | edit | add `updateReservationUnlessClaimed`; use it for date moves |
| go/internal/ical/syncfeed_test.go | edit | add regression test (append at end of file) |

No other file may change.

## 4. Steps

### Step 1. Python helper
In `App/app/icalsync.py`, insert directly **above** the line `def _fit_unsent_guest_windows(` this function:

```python
def _update_reservation_unless_claimed(existing, values: dict) -> bool:
    """Write a date move only if no live submission_claim covers the stay.

    One conditional UPDATE, so a claim taken after ``_send_in_flight`` cannot
    be raced. False means skipped: the caller keeps the stored dates and the
    next sync retries.
    """
    live_after = time.time() - reporting.SUBMISSION_CLAIM_TTL_SECONDS
    return db.update_if(
        "reservation",
        existing["id"],
        values,
        {"date_from": existing["date_from"], "date_to": existing["date_to"]},
        extra_where=(
            "NOT EXISTS (SELECT 1 FROM submission_claim c "
            "JOIN guest g ON g.id = c.guest_id "
            "WHERE g.reservation_id = reservation.id "
            "AND g.archived_at IS NULL AND c.claimed_at >= ?)"
        ),
        extra_params=(live_after,),
    )
```
Command: `grep -n "def _update_reservation_unless_claimed" App/app/icalsync.py | tail -3` -> one line.

### Step 2. Python call site
In `App/app/icalsync.py` replace exactly:

```python
            if changed:
                changed["updated_at"] = now
                db.update("reservation", existing["id"], changed)
                stats["updated"] += 1
```
with:

```python
            if changed:
                changed["updated_at"] = now
                applied = False
                if dates_changed:
                    applied = _update_reservation_unless_claimed(existing, changed)
                    if not applied:
                        # A claim landed after the pre-check: keep the stored
                        # dates and let the next poll retry the move.
                        for key in ("date_from", "date_to"):
                            changed.pop(key, None)
                        dates_changed = False
                        deferred_in_flight = True
                        log.warning(
                            "ical_dates_deferred_in_flight apartment_id=%s reservation_id=%s "
                            "stored=%s..%s calendar=%s..%s",
                            feed["apartment_id"],
                            existing["id"],
                            existing["date_from"],
                            existing["date_to"],
                            event["date_from"],
                            event["date_to"],
                        )
                if not applied and set(changed) - {"updated_at"}:
                    db.update("reservation", existing["id"], changed)
                    applied = True
                if applied:
                    stats["updated"] += 1
```
Command: `cd App && .venv/bin/python -c "import app.icalsync" 2>&1 | tail -5` -> no output.

### Step 3. Python regression test
Append to the end of `App/tests/test_icalsync.py` (uses `_moved_stay`, defined near line 205, same as the test at line 351):

```python
def test_reservation_date_write_is_skipped_while_a_claim_is_live(monkeypatch, tmp_path):
    """The date write is one conditional UPDATE: a claim taken after the pre-check wins."""
    feed_id, reservation_id, guest_id = _moved_stay(tmp_path, monkeypatch)
    existing = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
    moved = {"date_from": "2099-03-10", "date_to": "2099-03-12", "updated_at": "x"}
    db.execute(
        "INSERT INTO submission_claim (guest_id, claim_token, claimed_at) "
        "VALUES (?, 'race', ?)",
        (guest_id, time.time()),
    )
    try:
        assert icalsync._update_reservation_unless_claimed(existing, moved) is False
        row = db.query_one(
            "SELECT date_from, date_to FROM reservation WHERE id = ?", (reservation_id,)
        )
        assert (row["date_from"], row["date_to"]) == (existing["date_from"], existing["date_to"])
    finally:
        db.execute("DELETE FROM submission_claim WHERE guest_id = ?", (guest_id,))
    assert icalsync._update_reservation_unless_claimed(existing, moved) is True
    row = db.query_one(
        "SELECT date_from, date_to FROM reservation WHERE id = ?", (reservation_id,)
    )
    assert (row["date_from"], row["date_to"]) == ("2099-03-10", "2099-03-12")
```
If `time` or `icalsync` are not imported at top of the file, STOP (they are used by the test at line 351; verify with `grep -n "^import time\|icalsync" App/tests/test_icalsync.py | head -3`).

### Step 4. Go helper
In `go/internal/ical/syncfeed.go`, insert directly **after** the closing brace of `func updateRow` (the line `return err` then `}` before `func anyStr`):

```go
// updateReservationUnlessClaimed writes a date move only while no live
// submission_claim covers the stay (one UPDATE, so no check-then-write race).
// False means skipped; the caller keeps the stored dates and the next sync retries.
func updateReservationUnlessClaimed(ctx context.Context, pool *pgxpool.Pool, id int64, cols map[string]any) (bool, error) {
	keys := make([]string, 0, len(cols))
	for k := range cols {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	sets := make([]string, len(keys))
	args := make([]any, 0, len(keys)+2)
	for i, k := range keys {
		sets[i] = fmt.Sprintf("%s = $%d", k, i+1)
		args = append(args, cols[k])
	}
	args = append(args, id, liveClaimAfter())
	tag, err := pool.Exec(ctx,
		fmt.Sprintf(`UPDATE reservation SET %s WHERE id = $%d
		  AND NOT EXISTS (SELECT 1 FROM submission_claim c JOIN guest g ON g.id = c.guest_id
		    WHERE g.reservation_id = reservation.id AND g.archived_at IS NULL AND c.claimed_at >= $%d)`,
			strings.Join(sets, ", "), len(keys)+1, len(keys)+2),
		args...)
	if err != nil {
		return false, err
	}
	return tag.RowsAffected() == 1, nil
}
```
Command: `cd go && go build ./internal/ical/ 2>&1 | tail -10` -> no output.

### Step 5. Go call site
In `go/internal/ical/syncfeed.go` replace exactly:

```go
		if len(changed) > 0 {
			changed["updated_at"] = now
			if err := updateRow(ctx, pool, "reservation", s.ID, changed); err != nil {
				return stats, err
			}
			stats.Updated++
		}
```
with:

```go
		if len(changed) > 0 {
			changed["updated_at"] = now
			applied := false
			if datesChanged {
				ok, err := updateReservationUnlessClaimed(ctx, pool, s.ID, changed)
				if err != nil {
					return stats, err
				}
				applied = ok
				if !applied {
					// A claim landed after the pre-check: keep the stored dates; the next sync retries.
					delete(changed, "date_from")
					delete(changed, "date_to")
					datesChanged = false
					deferredInFlight = true
					log.Printf("ical_dates_deferred_in_flight apartment_id=%d reservation_id=%d stored=%s..%s calendar=%s..%s",
						feed.ApartmentID, s.ID, s.DateFrom, s.DateTo, ev.DateFrom, ev.DateTo)
				}
			}
			if !applied && len(changed) > 1 {
				if err := updateRow(ctx, pool, "reservation", s.ID, changed); err != nil {
					return stats, err
				}
				applied = true
			}
			if applied {
				stats.Updated++
			}
		}
```
Command: `cd go && go build ./internal/ical/ 2>&1 | tail -10` -> no output. If `err` shadowing or an unused variable breaks the build, fix only that, in this block.

### Step 6. Go regression test
Append to `go/internal/ical/syncfeed_test.go` (helpers `seedStay`, `seedGuest`, `newIcalFeed`, `scalarText`, `must` exist):

```go
func TestUpdateReservationUnlessClaimed(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/race.ics")
	stay := seedStay(t, pool, aid, feed.ID, "u-race", "2027-04-01", "2027-04-05")
	g := seedGuest(t, pool, stay, "pending", "2027-04-01", "2027-04-05")
	_, err := pool.Exec(ctx, `INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES ($1, 'race', $2)`,
		g, epochSeconds())
	must(t, err)
	cols := map[string]any{"date_from": "2027-04-02", "date_to": "2027-04-06", "updated_at": ubyport.UTCNow()}
	ok, err := updateReservationUnlessClaimed(ctx, pool, stay, cols)
	must(t, err)
	if ok {
		t.Fatal("date move applied while a live claim was held")
	}
	if got := scalarText(t, pool, `SELECT date_from FROM reservation WHERE id = $1`, stay); got != "2027-04-01" {
		t.Fatalf("date_from = %q, want unchanged", got)
	}
	_, err = pool.Exec(ctx, `DELETE FROM submission_claim WHERE guest_id = $1`, g)
	must(t, err)
	ok, err = updateReservationUnlessClaimed(ctx, pool, stay, cols)
	must(t, err)
	if !ok {
		t.Fatal("date move skipped after the claim was released")
	}
	if got := scalarText(t, pool, `SELECT date_from FROM reservation WHERE id = $1`, stay); got != "2027-04-02" {
		t.Fatalf("date_from = %q, want 2027-04-02", got)
	}
}
```
Command: `cd go && go build ./internal/ical/ && go vet ./internal/ical/ 2>&1 | tail -10` -> no output.

## 5. Do not touch

`_fit_unsent_guest_windows` / `fitUnsentGuestWindows`, `_send_in_flight` / `sendInFlight`, anything under `App/app/ubyport/`, `reporting.py`, `claim.go`, migrations, docs. Hard rules: no new dependency, SQL only through db helpers, no push to main, no merge.

## 6. Commands

1. `cd App && .venv/bin/python -m pytest tests/test_icalsync.py tests/test_ical_skip_unchanged.py -q --tb=short -x 2>&1 | tail -30` -> all pass, 0 skipped (test-map row "Calendar, iCal feeds"; the other files in that row only if the first two pass and calls remain).
2. `cd go && go test ./internal/ical/ -count=1 2>&1 | tail -30` -> `ok`; the new Go test must run, not skip. If `testPool` skips for lack of Postgres, report `blocked` for the Go test and hand the exact command to the owner. (test-map.md has no Go row; this is the package's own tests.)
3. From repo root: `python3 scripts/context_lint.py 2>&1 | tail -30` -> clean.

## 7. Acceptance

- [ ] New Python test passes; `test_a_live_send_claim_defers_fitting_the_guest_window` still passes.
- [ ] New Go test passes (not skipped); `TestSyncFeedDatesInFlightKeepsDigest` still passes.
- [ ] `git diff --stat` lists only the four §3 files.
- [ ] Both date writes carry the claim condition in the same UPDATE statement.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (report as `blocked`);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand to owner with the exact command).

## 9. Report

Write `docs/tasks/1133-report.md` (600 tokens at most) and set `Status: review`: files changed (`git diff --stat`), each command with the last 5 lines, §7 ticked, deviations, questions, owner steps left.

## Open questions (owner decision, not for Haiku)

1. K-F02 is partly stale: the pre-check and guest-window guard already exist and are tested. After merge the orchestrator should reword K-F02 to "reservation write was racy, fixed by 1133" or close it. Confirm.
2. The cancel path (`db.update(... "status": "cancelled")` in Python, `expireOnCancel`/`cancelExistingStay` in Go) also ignores a live claim. Out of scope here; it changes status, not dates. Separate brief?
3. Race on `submission.state` running/outcome_unknown is not covered by the atomic write (only live claims). A live claim is held for the whole send, so this should be enough; confirm with UBYPORT_CORE owner.

## Risk list (for the reviewer)

All four §3 files: the two call-site blocks (Step 2, Step 5) and the two helper SQL strings (Step 1, Step 4).

## Owner steps

1. After the PR is green, read the PR description and click "Ready for review" only if the Go test is listed as run, not skipped.
2. Merge with `scripts/merge-pr-on-green.sh <PR number>`.
