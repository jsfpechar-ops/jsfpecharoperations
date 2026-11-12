# 1136: iCal date move: take the claim path's per-guest locks, add call-site tests, align Go with Python

Status: review
Depends on: 1133 | Base commit: HEAD of branch claude/clever-fermi-tudhnt (PR #933) | Branch: task/1136-ical-claim-lock
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Make the guarded iCal date-move UPDATE (brief 1133) truly atomic on Postgres by taking the same per-guest advisory locks the claim path takes, in one transaction with the UPDATE, in Python and Go. Also add one call-site test per language (reverting the sync call site must fail a test) and make the Go UPDATE require the stored dates unchanged, as Python already does.

## 2. Context

Brief 1133 added `_update_reservation_unless_claimed` (Python) and `updateReservationUnlessClaimed` (Go): one UPDATE with `NOT EXISTS (live submission_claim on the stay's guests)`. Review found three gaps.

1. Not atomic on Postgres. Under READ COMMITTED the `NOT EXISTS` sees the statement snapshot. The claim path takes `pg_advisory_xact_lock(hashtext('guest'), id)` per guest (Python `db.lock_key(cur, "guest", id)`, ids ascending; Go `ubyport/claim.go` line 62 with `int32(id)`) and then INSERTs into `submission_claim`; nothing conflicts with the reservation row. A claim committing just after the UPDATE's snapshot lets the move land. Fix: in one transaction take the same locks for every guest of the reservation in ascending id order (the claim path at `reporting.py` ~2497 locks `SELECT id FROM guest WHERE reservation_id = ? ORDER BY id`), then run the guarded UPDATE. The lock is held to commit, so a claim that committed first is visible to the UPDATE, and a claim that comes later waits for us. SQLite: `lock_key` is a no-op and `BEGIN IMMEDIATE` already serialises.
2. Tests only call the helper. Reverting the `sync_feed` / `SyncFeed` call site to a plain update keeps all tests green.
3. Divergence. Python's `update_if` also requires stored `date_from` / `date_to` unchanged; Go does not.

Python: `db.update_if` runs on its own connection inside an `immediate()` block (`_helper_conn`), so it cannot join the locked transaction. The UPDATE must be written on the cursor. `reservation` has no encrypted columns (Step 1 checks this). Cursor `rowcount` is used the same way in `reporting.py` (`cur.rowcount == 1`).

Current Python (`App/app/icalsync.py`, ~408):
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
Current Go (`go/internal/ical/syncfeed.go`, ~91-117) is `updateReservationUnlessClaimed(ctx, pool, id, cols)`, called at ~355 as `ok, err := updateReservationUnlessClaimed(ctx, pool, s.ID, changed)`; the pre-check at ~320 is `inFlight, err := sendInFlight(ctx, pool, s.ID)`. `s.DateFrom` / `s.DateTo` are `string`.

Test helpers that exist: Python `_moved_stay(tmp_path, monkeypatch)` returns `(feed_id, reservation_id, guest_id)`, patches `fetch_feed` to a feed moving the stay 2099-01-10..12 to 2099-02-10..12 with `SUMMARY:Reserved`; `_sync(feed_id)` returns the stats dict. Go: `testPool`, `seedApartment`, `newIcalFeed`, `seedStay`, `seedGuest(t, pool, stay, state, from, to)`, `runSync(t, pool, feed, text)`, `icsDoc`, `icsEvent`, `scalarText`, `epochSeconds`, `must`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/icalsync.py | edit | helper takes per-guest locks, UPDATE on the cursor |
| App/tests/test_icalsync.py | edit | add call-site test |
| go/internal/ical/syncfeed.go | edit | locks + stored-date guard + `sendInFlightFn` seam |
| go/internal/ical/syncfeed_test.go | edit | new signature, call-site test, lock-wait test |
| docs/tasks/1136-ical-date-move-claim-lock.md | status | set `review` at the end |
| docs/tasks/1136-report.md | create | report |

No other file may change.

## 4. Steps

**Step 1. Python helper.** First run `cd App && .venv/bin/python -c "from app import db; print(db.ENCRYPTED_COLUMNS.get('reservation'))" 2>&1 | tail -3`; expected `None` (else STOP). In `App/app/icalsync.py` replace the whole body of `_update_reservation_unless_claimed` (from the `"""Write a date move` docstring through `extra_params=(live_after,),\n    )`) with:
```python
    """Write a date move only if no live submission_claim covers the stay.

    In one transaction: take the claim path's per-guest advisory locks (all
    the stay's guests, ascending id, ``db.lock_key(cur, "guest", id)``), then
    run one conditional UPDATE. A claim that committed first is then visible
    to the NOT EXISTS; a claim that comes later waits for this commit. The
    stored dates must be unchanged too, so a host edit in between is deferred,
    not overwritten. False means skipped: the caller keeps the stored dates
    and the next sync retries.
    """
    live_after = time.time() - reporting.SUBMISSION_CLAIM_TTL_SECONDS
    sets = ", ".join(f"{k} = ?" for k in values)
    with db.immediate() as cur:
        cur.execute(
            "SELECT id FROM guest WHERE reservation_id = ? ORDER BY id", (existing["id"],)
        )
        for locked in cur.fetchall():
            db.lock_key(cur, "guest", locked["id"])
        cur.execute(
            f"UPDATE reservation SET {sets} WHERE id = ? "
            f"AND {db.null_safe_eq('date_from')} AND {db.null_safe_eq('date_to')} "
            "AND NOT EXISTS (SELECT 1 FROM submission_claim c "
            "JOIN guest g ON g.id = c.guest_id "
            "WHERE g.reservation_id = reservation.id "
            "AND g.archived_at IS NULL AND c.claimed_at >= ?)",
            list(values.values())
            + [existing["id"], existing["date_from"], existing["date_to"], live_after],
        )
        return cur.rowcount == 1
```
If `values` can be empty the caller never passes it (it only runs with `changed`). Command: `cd App && .venv/bin/python -m pytest tests/test_icalsync.py -q --tb=short -x -k "claim" 2>&1 | tail -30`. Expected: existing `test_reservation_date_write_is_skipped_while_a_claim_is_live` passes.

**Step 2. Python call-site test.** Append to `App/tests/test_icalsync.py`:
```python
def test_sync_feed_defers_a_date_move_when_a_claim_lands_after_the_precheck(
    monkeypatch, tmp_path
):
    """sync_feed must go through the guarded write, not a plain update."""
    feed_id, reservation_id, guest_id = _moved_stay(tmp_path, monkeypatch)
    db.update("reservation", reservation_id, {"summary": "Old"})
    monkeypatch.setattr(icalsync, "_send_in_flight", lambda _reservation_id: False)
    db.execute(
        "INSERT INTO submission_claim (guest_id, claim_token, claimed_at) "
        "VALUES (?, 'race', ?)",
        (guest_id, time.time()),
    )

    stats = _sync(feed_id)

    row = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
    assert (row["date_from"], row["date_to"]) == ("2099-01-10", "2099-01-12")
    assert row["summary"] == "Reserved"
    assert stats["updated"] == 1
    feed = db.query_one("SELECT body_sha256, etag FROM ical_feed WHERE id = ?", (feed_id,))
    assert feed["body_sha256"] is None
    guest = db.query_one("SELECT stay_from, stay_to FROM guest WHERE id = ?", (guest_id,))
    assert (guest["stay_from"], guest["stay_to"]) == ("2099-01-10", "2099-01-12")
```
Command: `cd App && .venv/bin/python -m pytest tests/test_icalsync.py tests/test_ical_skip_unchanged.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass. Then prove the test bites: temporarily change the call `applied = _update_reservation_unless_claimed(existing, changed)` to `applied = db.update("reservation", existing["id"], changed) or True`, rerun only the new test (`-k precheck`), expect FAIL, then restore the line exactly and rerun (expect pass). If the new test does not fail with the revert, STOP.

**Step 3. Go helper.** In `go/internal/ical/syncfeed.go` replace the whole function `updateReservationUnlessClaimed` (the comment block above it included) with:
```go
// sendInFlightFn is sendInFlight; tests replace it to simulate a claim that
// lands after the pre-check.
var sendInFlightFn = sendInFlight

// updateReservationUnlessClaimed writes a date move only while no live
// submission_claim covers the stay and the stored dates are still
// storedFrom..storedTo. One transaction: the claim path's per-guest advisory
// locks (ascending id, same key as ubyport.ClaimSendable), then one UPDATE.
// False means skipped; the caller keeps the stored dates and the next sync retries.
func updateReservationUnlessClaimed(ctx context.Context, pool *pgxpool.Pool, id int64, storedFrom, storedTo string, cols map[string]any) (bool, error) {
	tx, err := pool.Begin(ctx)
	if err != nil {
		return false, err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	rows, err := tx.Query(ctx, `SELECT id FROM guest WHERE reservation_id = $1 ORDER BY id`, id)
	if err != nil {
		return false, err
	}
	var guestIDs []int64
	for rows.Next() {
		var gid int64
		if err := rows.Scan(&gid); err != nil {
			rows.Close()
			return false, err
		}
		guestIDs = append(guestIDs, gid)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return false, err
	}
	for _, gid := range guestIDs {
		// Python's db.lock_key takes the id as a 32-bit integer.
		if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1), $2)`, "guest", int32(gid)); err != nil {
			return false, err
		}
	}
	keys := make([]string, 0, len(cols))
	for k := range cols {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	sets := make([]string, len(keys))
	args := make([]any, 0, len(keys)+4)
	for i, k := range keys {
		sets[i] = fmt.Sprintf("%s = $%d", k, i+1)
		args = append(args, cols[k])
	}
	args = append(args, id, storedFrom, storedTo, liveClaimAfter())
	n := len(keys)
	tag, err := tx.Exec(ctx,
		fmt.Sprintf(`UPDATE reservation SET %s WHERE id = $%d
		  AND date_from = $%d AND date_to = $%d
		  AND NOT EXISTS (SELECT 1 FROM submission_claim c JOIN guest g ON g.id = c.guest_id
		    WHERE g.reservation_id = reservation.id AND g.archived_at IS NULL AND c.claimed_at >= $%d)`,
			strings.Join(sets, ", "), n+1, n+2, n+3, n+4),
		args...)
	if err != nil {
		return false, err
	}
	if err := tx.Commit(ctx); err != nil {
		return false, err
	}
	return tag.RowsAffected() == 1, nil
}
```
Then replace the pre-check line `inFlight, err := sendInFlight(ctx, pool, s.ID)` with `inFlight, err := sendInFlightFn(ctx, pool, s.ID)` and `ok, err := updateReservationUnlessClaimed(ctx, pool, s.ID, changed)` with `ok, err := updateReservationUnlessClaimed(ctx, pool, s.ID, s.DateFrom, s.DateTo, changed)`. Command: `cd go && go build ./internal/ical/ 2>&1 | tail -30`. Expected: only test-file errors are not reported by build; build is silent. (If `date_from` is a DATE column rather than text, STOP: the existing test reads it with `scalarText`, so it is text.)

**Step 4. Go tests.** In `go/internal/ical/syncfeed_test.go`: add `"time"` to the import block (after `"testing"`). In `TestUpdateReservationUnlessClaimed` change both calls `updateReservationUnlessClaimed(ctx, pool, stay, cols)` to `updateReservationUnlessClaimed(ctx, pool, stay, "2027-04-01", "2027-04-05", cols)`. Append:
```go
func TestSyncFeedDefersDateMoveWhenClaimLandsAfterPrecheck(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/late-claim.ics")
	stay := seedStay(t, pool, aid, feed.ID, "u-late", "2027-05-01", "2027-05-05")
	g := seedGuest(t, pool, stay, "pending", "2027-05-01", "2027-05-05")
	_, err := pool.Exec(ctx, `UPDATE reservation SET summary = 'Old' WHERE id = $1`, stay)
	must(t, err)
	_, err = pool.Exec(ctx, `INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES ($1, 'race', $2)`,
		g, epochSeconds())
	must(t, err)
	orig := sendInFlightFn
	sendInFlightFn = func(context.Context, *pgxpool.Pool, int64) (bool, error) { return false, nil }
	t.Cleanup(func() { sendInFlightFn = orig })

	st := runSync(t, pool, feed, icsDoc(icsEvent("u-late", "20270502", "20270506", "Guest B")))

	if got := scalarText(t, pool, `SELECT date_from FROM reservation WHERE id = $1`, stay); got != "2027-05-01" {
		t.Errorf("date_from = %q, want unchanged", got)
	}
	if got := scalarText(t, pool, `SELECT summary FROM reservation WHERE id = $1`, stay); got != "Guest B" {
		t.Errorf("summary = %q, want the non-date change written", got)
	}
	if st.Updated != 1 {
		t.Errorf("Updated = %d, want 1", st.Updated)
	}
	if got := scalarText(t, pool, `SELECT COALESCE(body_sha256, '') FROM ical_feed WHERE id = $1`, feed.ID); got != "" {
		t.Errorf("digest stored after a deferred move: %q", got)
	}
	if got := scalarText(t, pool, `SELECT stay_from FROM guest WHERE id = $1`, g); got != "2027-05-01" {
		t.Errorf("guest stay_from = %q, want not refitted", got)
	}
}

func TestUpdateReservationUnlessClaimedWaitsForClaimLock(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/lock.ics")
	stay := seedStay(t, pool, aid, feed.ID, "u-lock", "2027-06-01", "2027-06-05")
	g := seedGuest(t, pool, stay, "pending", "2027-06-01", "2027-06-05")
	tx, err := pool.Begin(ctx)
	must(t, err)
	defer func() { _ = tx.Rollback(ctx) }()
	_, err = tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1), $2)`, "guest", int32(g))
	must(t, err)
	_, err = tx.Exec(ctx, `INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES ($1, 'late', $2)`,
		g, epochSeconds())
	must(t, err)
	type result struct {
		ok  bool
		err error
	}
	done := make(chan result, 1)
	go func() {
		cols := map[string]any{"date_from": "2027-06-02", "date_to": "2027-06-06", "updated_at": ubyport.UTCNow()}
		ok, err := updateReservationUnlessClaimed(ctx, pool, stay, "2027-06-01", "2027-06-05", cols)
		done <- result{ok, err}
	}()
	select {
	case r := <-done:
		t.Fatalf("returned before the claim committed: %+v", r)
	case <-time.After(300 * time.Millisecond):
	}
	must(t, tx.Commit(ctx))
	select {
	case r := <-done:
		must(t, r.err)
		if r.ok {
			t.Fatal("date move applied although a claim committed first")
		}
	case <-time.After(5 * time.Second):
		t.Fatal("helper still blocked after the claim committed")
	}
	if got := scalarText(t, pool, `SELECT date_from FROM reservation WHERE id = $1`, stay); got != "2027-06-01" {
		t.Fatalf("date_from = %q, want unchanged", got)
	}
}
```
Command: `cd go && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ical/ -count=1 -run 'UpdateReservationUnlessClaimed|DefersDateMove' -v 2>&1 | tail -30`. Expected: three tests show `--- PASS`, none `SKIP`. Then prove the call-site test bites: temporarily replace `ok, err := updateReservationUnlessClaimed(ctx, pool, s.ID, s.DateFrom, s.DateTo, changed)` with `ok, err := true, updateRow(ctx, pool, "reservation", s.ID, changed)`, rerun `-run DefersDateMove`, expect FAIL, restore the line exactly, rerun, expect PASS. If the verbatim `Updated` or summary value differs from the assertion on first run, fix the assertion to match the code's real stat definition only if the other assertions pass; otherwise STOP.

**Step 5. Full area run and lint.** Commands: `cd App && .venv/bin/python -m pytest tests/test_icalsync.py tests/test_ical_skip_unchanged.py -q --tb=short -x 2>&1 | tail -30`; `cd go && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ical/ -count=1 2>&1 | tail -30`; `cd go && go vet ./internal/ical/ 2>&1 | tail -30`; `python3 scripts/context_lint.py 2>&1 | tail -3`. Expected: Python all passed; Go `ok` (and the Postgres tests must PASS, not SKIP: re-run with `-v 2>&1 | grep -c SKIP | tail -3` expecting `0`); vet silent; lint says OK.

**Step 6. Report.** Write `docs/tasks/1136-report.md` per §9 and set `Status: review` at the top of this brief.

## 5. Do not touch

`App/app/reporting.py`, `go/internal/ubyport/` (claim path unchanged; a follow-up brief owns it), `App/app/db.py`, all of `App/app/migrations/`. No commit, no push. Hard rules: SQL only in the helpers shown; no new dependency; privacy rules unaffected (no personal-data field, no outbound request).

## 6. Commands

See Steps 1-5; every command ends `| tail -30` (or `tail -3`). Tests are the test-map row "Calendar, iCal feeds" narrowed to `test_icalsync.py test_ical_skip_unchanged.py` plus the Go package `./internal/ical/`. Never the full suite.

## 7. Acceptance

- [ ] `_update_reservation_unless_claimed` locks all the stay's guests (ascending id) and UPDATEs in one `db.immediate()` block: `grep -n "lock_key" App/app/icalsync.py | tail -3` shows one hit.
- [ ] Go helper takes `storedFrom, storedTo`, locks guests in id order, and the SQL contains `date_from = $` and `date_to = $`: `grep -n "date_from = \$%d" go/internal/ical/syncfeed.go | tail -3`.
- [ ] Both call-site tests fail when the call site is reverted (shown in the report) and pass restored.
- [ ] `TestUpdateReservationUnlessClaimedWaitsForClaimLock` passes against Postgres (PASS, not SKIP).
- [ ] Python tests, Go tests, `go vet`: green. `python3 scripts/context_lint.py` says OK.
- [ ] `git diff --stat` lists only the §3 files.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear (including: `reservation` has encrypted columns, `date_from` is not text in Postgres, or a Go Postgres test SKIPs);
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1136-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/icalsync.py`: `_update_reservation_unless_claimed` (lock order, `rowcount`, placeholder order).
- `go/internal/ical/syncfeed.go`: `updateReservationUnlessClaimed` (lock key `hashtext('guest')` with `int32(id)` must match `ubyport/claim.go`; `$n` numbering; Rollback after Commit is harmless).
- The two revert-bite proofs in the report.

## Owner steps

1. Review and merge PR #933 when green, using `scripts/merge-pr-on-green.sh`.
2. Ask the orchestrator for the follow-up brief that adds a reservation-row lock to the claim path (`reporting.py`, `ubyport/claim.go`), if wanted.
