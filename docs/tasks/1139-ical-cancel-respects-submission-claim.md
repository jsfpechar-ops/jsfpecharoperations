# 1139: iCal cancel and vanished-stay sweep: respect a live submission_claim

Status: todo
Depends on: 1136 | Base commit: 4fff483d (HEAD of branch claude/clever-fermi-tudhnt, PR #933) | Branch: task/1139-ical-cancel-claim
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

HIGH RISK filing path: the reviewer reads every diff line in §Risk list.

## 1. Objective

Stop the iCal sync from cancelling a stay while a guest of that stay holds a live `submission_claim` (a send to UbyPort is in flight). Take 1136's per-guest advisory locks in one transaction with the status UPDATE, guard it with `NOT EXISTS (live claim)`, and when a claim is live skip the cancel this pass and do not store the feed digest, so the next poll retries. Python and Go.

## 2. Context

Finding (verified at HEAD): the cancel path is harmful, not harmless.

What cancel writes (Python `icalsync._cancel_existing_stay` for an explicit `STATUS:CANCELLED` / `METHOD:CANCEL` event, and the vanished-stay sweep at the end of `sync_feed`; Go `cancelExistingStay` and the sweep in `SyncFeed`): `reservation.status = 'cancelled'`; then `claim.expire_on_cancel` / `expireOnCancel`: `reservation_claim.token_hash = NULL` plus guest access locked, and `email_outbox` rows `queued` -> `failed` for the reservation. Nothing is deleted. No guest is archived and no guest row changes. Neither path calls `_send_in_flight` / `sendInFlight` (only the date-move branch does).

What goes wrong for an in-flight send: the only guard is "a guest already `sent`" (`submit_state = SENT`), which an in-flight guest is not yet. So the stay is cancelled while the guest is being filed. The send then succeeds and the police register holds a guest for a stay we show as cancelled, with no `cancelled_after_report` alert (that alert fires only when a guest is already `sent` at cancel time), the guest's access token is wiped and their completion mail is failed mid-flow. The guest rows themselves stay intact, so the payload is not corrupted; the damage is a filed guest on a cancelled stay with nobody told.

Why deferring is right: once the claim resolves and the guest is `sent`, the next poll takes the existing "reported" branch and raises `cancelled_after_report`, which is the correct outcome.

1136 pattern (same locks, same predicate). Claim path locks `SELECT id FROM guest WHERE reservation_id = ? ORDER BY id` with `db.lock_key(cur, "guest", id)` (Go: `pg_advisory_xact_lock(hashtext('guest'), int32(id))`), then inserts into `submission_claim`. Under READ COMMITTED a plain `NOT EXISTS` could miss a claim committing just after the snapshot, so the locks are taken first. SQLite: `lock_key` is a no-op and `immediate()` serialises.

Scope decisions: only a live `submission_claim` blocks the cancel (the atomic guard). A `running` / `outcome_unknown` submission without a live claim is NOT covered (see Owner questions). `expire_on_cancel` / `expireOnCancel` are NOT changed, so `test_sm_queues.py` pins stay valid. No test_sm_* pin reads the changed status UPDATE (checked: `grep` of icalsync/reconcile/syncfeed in test_sm_reservation_claim_state.py, test_sm_go_parity.py, test_sm_guest_submit_state.py finds nothing); Step 7 runs them anyway.

A deferred event cancel must also count the UID as seen (`seen_uids`), otherwise the sweep below would try to cancel the same stay again, and a one-stay feed would hit the "suspect feed" early return, which stores the digest.

Current Python (`App/app/icalsync.py`, ~529):
```python
def _cancel_existing_stay(apartment_id: int, uid: str, date_from: str, now: str, stats: Dict[str, Any]) -> None:
    """Mark an active future stay as cancelled when the feed signals cancellation."""
    existing = db.query_one(
        "SELECT * FROM reservation WHERE apartment_id = ? AND uid = ?",
        (apartment_id, uid),
    )
    if not existing or existing["status"] != "active":
        return
    if existing["date_from"] < deadlines.local_now().date().isoformat():
        return
```
...
```python
    db.update("reservation", existing["id"], {"status": "cancelled", "updated_at": now})
    from . import claim as stay_claim

    stay_claim.expire_on_cancel(existing)
    _warn_if_guests_registered(existing, apartment_id, "cancelled")
    stats["cancelled"] += 1
```
Event call site (~770): `_cancel_existing_stay(feed["apartment_id"], event["uid"], event["date_from"], now, stats)` inside `if event.get("is_cancelled"):` followed by `continue`. Sweep (~992): `db.update("reservation", row["id"], {"status": "cancelled", "updated_at": now})` then `from . import claim as stay_claim`, `stay_claim.expire_on_cancel(row)`, `_warn_if_guests_registered(row, feed["apartment_id"], "disappeared")`. `deferred_in_flight` is initialised at ~742 (before the event loop) and read at ~1000 to drop the digest/etag.

Current Go (`go/internal/ical/reconcile.go` ~315, `cancelExistingStay(ctx, pool, getenv, apartmentID, uid, stats *SyncStats) error`): it does `pool.Exec(... UPDATE reservation SET status = 'cancelled', updated_at = $1 WHERE id = $2 ...)` then `expireOnCancel`. Call sites: `syncfeed.go` ~309 (event), ~548 (sweep, `updateRow(ctx, pool, "reservation", r.ID, map[string]any{"status": "cancelled", "updated_at": now})`), and 3 test calls in `reconcile_test.go` (lines ~255, ~275, ~289). `deferredInFlight` is declared at `syncfeed.go` ~286. `liveClaimAfter()` exists in reconcile.go; `pgx` is already imported there.

Test helpers. Python (`test_icalsync.py`): `_moved_stay(tmp_path, monkeypatch)` -> `(feed_id, reservation_id, guest_id)` (stay 2099-01-10..12, uid `moved-stay`, patches `fetch_feed` to `MOVED_STAY_FEED`); `_sync(feed_id)`; `_stored_stays(tmp_path, monkeypatch, name, *, stored, returned)` -> `(feed_id, apartment_id, uids)` and patches `fetch_feed` to the first `returned` uids (so with stored=10, returned=9 the last uid vanishes and is the only cancel candidate). Go: `testPool`, `seedApartment`, `newIcalFeed`, `seedStay(t, pool, aid, feed.ID, uid, from, to)`, `seedGuest(t, pool, stay, state, from, to)`, `runSync(t, pool, feed, text)`, `icsDoc`, `icsEvent(uid, from, to, summary, extra...)`, `scalarText`, `epochSeconds`, `must`. A feed returning 1 of 2 stored stays passes the completeness bar (0.5), as `TestSyncFeedVanishedStayCancelled` shows.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/icalsync.py | edit | guarded cancel helper, `_cancel_existing_stay` returns deferred flag, two call sites |
| App/tests/test_icalsync.py | edit | two tests (event cancel, vanished sweep) |
| go/internal/ical/reconcile.go | edit | `lockStayGuests`, `cancelReservationUnlessClaimed`, `cancelExistingStay` returns `(bool, error)` |
| go/internal/ical/syncfeed.go | edit | event and sweep call sites |
| go/internal/ical/reconcile_test.go | edit | 3 call sites of `cancelExistingStay` |
| go/internal/ical/syncfeed_test.go | edit | two tests (event cancel, vanished sweep) |
| docs/tasks/1139-ical-cancel-respects-submission-claim.md | status | set `review` at the end |
| docs/tasks/1139-report.md | create | report |

No other file may change.

## 4. Steps

**Step 1. Python helper and function.** In `App/app/icalsync.py`, replace the whole function `_cancel_existing_stay` (from the `def _cancel_existing_stay(` line through `    stats["cancelled"] += 1`, its last line; it is followed by two blank lines and `def _existing_reservation`) with:
```python
def _cancel_reservation_unless_claimed(reservation_id: int, now: str) -> bool:
    """Cancel a stay only if no live submission_claim covers it.

    One transaction, as for a date move: the claim path's per-guest advisory
    locks (all the stay's guests, ascending id), then one conditional UPDATE,
    so a claim that committed first is seen and a claim that comes later waits.
    False means skipped: the stay stays active and the next sync retries.
    """
    live_after = time.time() - reporting.SUBMISSION_CLAIM_TTL_SECONDS
    with db.immediate() as cur:
        cur.execute(
            "SELECT id FROM guest WHERE reservation_id = ? ORDER BY id", (reservation_id,)
        )
        for locked in cur.fetchall():
            db.lock_key(cur, "guest", locked["id"])
        cur.execute(
            "UPDATE reservation SET status = 'cancelled', updated_at = ? "
            "WHERE id = ? AND status = 'active' "
            "AND NOT EXISTS (SELECT 1 FROM submission_claim c "
            "JOIN guest g ON g.id = c.guest_id "
            "WHERE g.reservation_id = reservation.id "
            "AND g.archived_at IS NULL AND c.claimed_at >= ?)",
            (now, reservation_id, live_after),
        )
        return cur.rowcount == 1


def _cancel_existing_stay(apartment_id: int, uid: str, date_from: str, now: str, stats: Dict[str, Any]) -> bool:
    """Mark an active future stay as cancelled when the feed signals cancellation.

    Returns True when the cancel was deferred because a send is in flight.
    """
    existing = db.query_one(
        "SELECT * FROM reservation WHERE apartment_id = ? AND uid = ?",
        (apartment_id, uid),
    )
    if not existing or existing["status"] != "active":
        return False
    if existing["date_from"] < deadlines.local_now().date().isoformat():
        return False
    reported = db.query_one(
        "SELECT COUNT(*) AS n FROM guest WHERE reservation_id = ? AND submit_state = ?",
        (existing["id"], reporting.SENT),
    )
    if reported and reported["n"]:
        alerts.raise_alert(
            "warning",
            "cancelled_after_report",
            f"A stay from {existing['date_from']} was cancelled in the calendar after it had "
            "already been reported to the police.",
            "Check whether the booking was cancelled or merely moved.",
            dedupe_key=f"cancelled_after_report:{existing['id']}",
            apartment_id=apartment_id,
            reservation_id=existing["id"],
            params={"date": existing["date_from"], "variant": "cancelled"},
        )
        return False
    if not _cancel_reservation_unless_claimed(existing["id"], now):
        log.warning(
            "ical_cancel_deferred_in_flight apartment_id=%s reservation_id=%s",
            apartment_id,
            existing["id"],
        )
        return True
    from . import claim as stay_claim

    stay_claim.expire_on_cancel(existing)
    _warn_if_guests_registered(existing, apartment_id, "cancelled")
    stats["cancelled"] += 1
    return False
```
Before editing, check the old body matches what is in §2 and between the excerpts (`reported = db.query_one(... reporting.SENT)` and the `alerts.raise_alert(... "cancelled_after_report" ...)` block with `params={"date": existing["date_from"], "variant": "cancelled"}`); if not, STOP. Command: `cd App && .venv/bin/python -c "import app.icalsync" 2>&1 | tail -5`. Expected: no output.

**Step 2. Python call sites.** In `App/app/icalsync.py`:

(a) Replace
```python
        if event.get("is_cancelled"):
            _cancel_existing_stay(feed["apartment_id"], event["uid"], event["date_from"], now, stats)
            continue
```
with
```python
        if event.get("is_cancelled"):
            if _cancel_existing_stay(feed["apartment_id"], event["uid"], event["date_from"], now, stats):
                # Still alive until the send is resolved: the sweep below must
                # not cancel it, and the digest must not be stored.
                seen_uids.append(event["uid"])
                deferred_in_flight = True
            continue
```
(b) Replace
```python
        db.update("reservation", row["id"], {"status": "cancelled", "updated_at": now})
        from . import claim as stay_claim

        stay_claim.expire_on_cancel(row)
        _warn_if_guests_registered(row, feed["apartment_id"], "disappeared")
```
with
```python
        if not _cancel_reservation_unless_claimed(row["id"], now):
            deferred_in_flight = True
            log.warning(
                "ical_cancel_deferred_in_flight apartment_id=%s reservation_id=%s",
                feed["apartment_id"],
                row["id"],
            )
            continue
        from . import claim as stay_claim

        stay_claim.expire_on_cancel(row)
        _warn_if_guests_registered(row, feed["apartment_id"], "disappeared")
```
Command: `cd App && .venv/bin/python -m pytest tests/test_icalsync.py tests/test_ical_skip_unchanged.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass (61 passed at HEAD).

**Step 3. Python tests and revert bite.** Append to `App/tests/test_icalsync.py`:
```python
def test_a_cancel_event_is_deferred_while_a_claim_is_live(monkeypatch, tmp_path):
    """A send in flight blocks the cancel; it lands once the claim is gone."""
    feed_id, reservation_id, guest_id = _moved_stay(tmp_path, monkeypatch)
    monkeypatch.setattr(
        icalsync,
        "fetch_feed",
        lambda _url: MOVED_STAY_FEED.replace(
            "SUMMARY:Reserved", "SUMMARY:Reserved\nSTATUS:CANCELLED"
        ),
    )
    db.execute(
        "INSERT INTO submission_claim (guest_id, claim_token, claimed_at) "
        "VALUES (?, 'race', ?)",
        (guest_id, time.time()),
    )

    stats = _sync(feed_id)

    row = db.query_one("SELECT status FROM reservation WHERE id = ?", (reservation_id,))
    assert row["status"] == "active"
    assert stats["cancelled"] == 0
    feed = db.query_one("SELECT body_sha256, etag FROM ical_feed WHERE id = ?", (feed_id,))
    assert feed["body_sha256"] is None

    db.execute("DELETE FROM submission_claim WHERE guest_id = ?", (guest_id,))
    stats = _sync(feed_id)

    row = db.query_one("SELECT status FROM reservation WHERE id = ?", (reservation_id,))
    assert row["status"] == "cancelled"
    assert stats["cancelled"] == 1


def test_a_vanished_stay_is_not_cancelled_while_a_claim_is_live(monkeypatch, tmp_path):
    feed_id, apartment_id, uids = _stored_stays(
        tmp_path, monkeypatch, "sweep-claim.sqlite3", stored=10, returned=9
    )
    gone = db.query_one(
        "SELECT id FROM reservation WHERE apartment_id = ? AND uid = ?",
        (apartment_id, uids[9]),
    )["id"]
    now = db.utcnow()
    guest_id = db.insert(
        "guest",
        {
            "reservation_id": gone,
            "stay_from": "2099-03-01",
            "stay_to": "2099-03-05",
            "entered_by": "guest",
            "submit_state": "pending",
            "created_at": now,
            "updated_at": now,
        },
    )
    db.execute(
        "INSERT INTO submission_claim (guest_id, claim_token, claimed_at) "
        "VALUES (?, 'race', ?)",
        (guest_id, time.time()),
    )

    stats = _sync(feed_id)

    assert stats["cancelled"] == 0
    assert _active_count(apartment_id) == 10
    feed = db.query_one("SELECT body_sha256, etag FROM ical_feed WHERE id = ?", (feed_id,))
    assert feed["body_sha256"] is None

    db.execute("DELETE FROM submission_claim WHERE guest_id = ?", (guest_id,))
    stats = _sync(feed_id)

    assert stats["cancelled"] == 1
    assert _active_count(apartment_id) == 9
```
If the guest insert fails on a NOT NULL column, add the missing column the error names, copying the value from `_moved_stay`'s guest insert (the same file); do not change anything else. Command: `cd App && .venv/bin/python -m pytest tests/test_icalsync.py tests/test_ical_skip_unchanged.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass (63 passed).
Revert bite: `cp App/app/icalsync.py /tmp/icalsync.py.bak`. In `_cancel_reservation_unless_claimed` temporarily delete the six lines from `"AND NOT EXISTS (SELECT 1 FROM submission_claim c "` through `"AND g.archived_at IS NULL AND c.claimed_at >= ?)",` and change the parameters tuple to `(now, reservation_id)`. Run `cd App && .venv/bin/python -m pytest tests/test_icalsync.py -q --tb=short -k "claim_is_live" 2>&1 | tail -30`. Expected: both new tests FAIL (status `cancelled` instead of `active`). Restore with `cp /tmp/icalsync.py.bak App/app/icalsync.py`, rerun the same command, expected `2 passed`. If a test does not fail under the revert, STOP.

**Step 4. Go helper and function.** In `go/internal/ical/reconcile.go`, replace the whole function `cancelExistingStay` (the comment block above it, `// cancelExistingStay is _cancel_existing_stay ...`, through the closing `}` right before `// existingReservation is _existing_reservation`) with:
```go
// lockStayGuests takes the claim path's per-guest advisory locks (all the
// stay's guests, ascending id) in tx. Python's db.lock_key takes the id as a
// 32-bit integer; the key matches ubyport.ClaimSendable.
func lockStayGuests(ctx context.Context, tx pgx.Tx, reservationID int64) error {
	rows, err := tx.Query(ctx, `SELECT id FROM guest WHERE reservation_id = $1 ORDER BY id`, reservationID)
	if err != nil {
		return err
	}
	var guestIDs []int64
	for rows.Next() {
		var gid int64
		if err := rows.Scan(&gid); err != nil {
			rows.Close()
			return err
		}
		guestIDs = append(guestIDs, gid)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return err
	}
	for _, gid := range guestIDs {
		if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtext($1), $2)`, "guest", int32(gid)); err != nil {
			return err
		}
	}
	return nil
}

// cancelReservationUnlessClaimed sets status 'cancelled' only while the stay
// is active and no live submission_claim covers it. One transaction: the
// per-guest locks, then one UPDATE. False means skipped (the stay stays
// active and the next sync retries). Python: _cancel_reservation_unless_claimed.
func cancelReservationUnlessClaimed(ctx context.Context, pool *pgxpool.Pool, id int64, now string) (bool, error) {
	tx, err := pool.Begin(ctx)
	if err != nil {
		return false, err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if err := lockStayGuests(ctx, tx, id); err != nil {
		return false, err
	}
	tag, err := tx.Exec(ctx,
		`UPDATE reservation SET status = 'cancelled', updated_at = $1
		  WHERE id = $2 AND status = 'active'
		  AND NOT EXISTS (SELECT 1 FROM submission_claim c JOIN guest g ON g.id = c.guest_id
		    WHERE g.reservation_id = reservation.id AND g.archived_at IS NULL AND c.claimed_at >= $3)`,
		now, id, liveClaimAfter())
	if err != nil {
		return false, err
	}
	if err := tx.Commit(ctx); err != nil {
		return false, err
	}
	return tag.RowsAffected() == 1, nil
}

// cancelExistingStay is _cancel_existing_stay (icalsync.py). A stay that
// already has a sent guest is not cancelled; an alert is raised instead. The
// bool is true when the cancel was deferred because a send is in flight.
func cancelExistingStay(ctx context.Context, pool *pgxpool.Pool, getenv func(string) string,
	apartmentID int64, uid string, stats *SyncStats) (bool, error) {
	res, found, err := selectReservation(ctx, pool, apartmentID, uid)
	if err != nil || !found || res.Status != "active" {
		return false, err
	}
	today := time.Now().In(prague).Format(dateLayout)
	if res.DateFrom < today {
		return false, nil
	}
	reported, err := exists(ctx, pool,
		`SELECT 1 FROM guest WHERE reservation_id = $1 AND submit_state = $2 LIMIT 1`,
		res.ID, guestSent)
	if err != nil {
		return false, err
	}
	if reported {
		aid, rid := apartmentID, res.ID
		return false, ubyport.RaiseAlert(ctx, pool, "warning", "cancelled_after_report",
			fmt.Sprintf("A stay from %s was cancelled in the calendar after it had already been reported to the police.", res.DateFrom),
			"Check whether the booking was cancelled or merely moved.",
			fmt.Sprintf("cancelled_after_report:%d", res.ID), &aid, &rid, nil,
			ubyport.AlertParams{"date": res.DateFrom, "variant": "cancelled"})
	}
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
		return false, err
	}
	stats.Cancelled++
	return false, nil
}
```
Before editing, confirm the old function matches §2 (it contains `UPDATE reservation SET status = 'cancelled', updated_at = $1 WHERE id = $2` and `expireOnCancel(ctx, pool, res.ID)`); if not, STOP. The package will not build until Step 5 (call sites). Command: `cd go && gofmt -l internal/ical/ 2>&1 | tail -5`. Expected: no output.

**Step 5. Go call sites.** (a) `go/internal/ical/syncfeed.go`: replace
```go
		if ev.IsCancelled {
			if err := cancelExistingStay(ctx, pool, getenv, feed.ApartmentID, ev.UID, &stats); err != nil {
				return stats, err
			}
			continue
		}
```
with
```go
		if ev.IsCancelled {
			deferred, err := cancelExistingStay(ctx, pool, getenv, feed.ApartmentID, ev.UID, &stats)
			if err != nil {
				return stats, err
			}
			if deferred {
				// Still alive until the send is resolved: the sweep below must
				// not cancel it, and the digest must not be stored.
				seen[ev.UID] = true
				deferredInFlight = true
			}
			continue
		}
```
(b) same file, replace
```go
		if err := updateRow(ctx, pool, "reservation", r.ID, map[string]any{"status": "cancelled", "updated_at": now}); err != nil {
			return stats, err
		}
		if err := expireOnCancel(ctx, pool, r.ID); err != nil {
```
with
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
```
(c) `go/internal/ical/reconcile_test.go`: the three calls (`must(t, cancelExistingStay(ctx, pool, noEnv, apt, "u-cancel", stats))`, `... "u-sent", stats2))`, `... "u-past", stats3))`) become `_, err = cancelExistingStay(ctx, pool, noEnv, apt, "<uid>", <stats>)` followed by `must(t, err)`. In the first test `err` is already declared (`_, err := pool.Exec`), so `_, err = ` compiles; if a later call reports "undefined: err" or "no new variables" mismatch, use `if _, err := cancelExistingStay(...); err != nil { t.Fatal(err) }` for that call. Command: `cd go && go build ./internal/ical/ && go vet ./internal/ical/ 2>&1 | tail -30`. Expected: silent.

**Step 6. Go tests and revert bite.** Append to `go/internal/ical/syncfeed_test.go`:
```go
func TestSyncFeedCancelEventDeferredWhileClaimLive(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/cancel-claim.ics")
	stay := seedStay(t, pool, aid, feed.ID, "u-cc", "2999-03-01", "2999-03-05")
	g := seedGuest(t, pool, stay, "pending", "2999-03-01", "2999-03-05")
	_, err := pool.Exec(ctx, `INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES ($1, 'race', $2)`,
		g, epochSeconds())
	must(t, err)
	doc := icsDoc(icsEvent("u-cc", "29990301", "29990305", "Guest A", "STATUS:CANCELLED"))

	st := runSync(t, pool, feed, doc)

	if got := scalarText(t, pool, `SELECT status FROM reservation WHERE id = $1`, stay); got != "active" {
		t.Errorf("status = %q, want active while a claim is live", got)
	}
	if st.Cancelled != 0 {
		t.Errorf("Cancelled = %d, want 0", st.Cancelled)
	}
	if got := scalarText(t, pool, `SELECT COALESCE(body_sha256, '') FROM ical_feed WHERE id = $1`, feed.ID); got != "" {
		t.Errorf("digest stored after a deferred cancel: %q", got)
	}

	_, err = pool.Exec(ctx, `DELETE FROM submission_claim WHERE guest_id = $1`, g)
	must(t, err)
	st = runSync(t, pool, feed, doc)

	if got := scalarText(t, pool, `SELECT status FROM reservation WHERE id = $1`, stay); got != "cancelled" || st.Cancelled != 1 {
		t.Errorf("after the claim ended: status = %q, Cancelled = %d, want cancelled and 1", got, st.Cancelled)
	}
}

func TestSyncFeedVanishedStayDeferredWhileClaimLive(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/vanish-claim.ics")
	seedStay(t, pool, aid, feed.ID, "u1", "2999-03-01", "2999-03-05")
	gone := seedStay(t, pool, aid, feed.ID, "u2", "2999-04-01", "2999-04-05")
	g := seedGuest(t, pool, gone, "pending", "2999-04-01", "2999-04-05")
	_, err := pool.Exec(ctx, `INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES ($1, 'race', $2)`,
		g, epochSeconds())
	must(t, err)
	doc := icsDoc(icsEvent("u1", "29990301", "29990305", "Guest A"))

	st := runSync(t, pool, feed, doc)

	if got := scalarText(t, pool, `SELECT status FROM reservation WHERE id = $1`, gone); got != "active" {
		t.Errorf("status = %q, want active while a claim is live", got)
	}
	if st.Cancelled != 0 {
		t.Errorf("Cancelled = %d, want 0", st.Cancelled)
	}
	if got := scalarText(t, pool, `SELECT COALESCE(body_sha256, '') FROM ical_feed WHERE id = $1`, feed.ID); got != "" {
		t.Errorf("digest stored after a deferred cancel: %q", got)
	}

	_, err = pool.Exec(ctx, `DELETE FROM submission_claim WHERE guest_id = $1`, g)
	must(t, err)
	st = runSync(t, pool, feed, doc)

	if got := scalarText(t, pool, `SELECT status FROM reservation WHERE id = $1`, gone); got != "cancelled" || st.Cancelled != 1 {
		t.Errorf("after the claim ended: status = %q, Cancelled = %d, want cancelled and 1", got, st.Cancelled)
	}
}
```
Command: `cd go && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ical/ -count=1 -run 'DeferredWhileClaimLive|CancelExistingStay|CancelEvent|VanishedStayCancelled' -v 2>&1 | tail -30`. Expected: all `--- PASS`, none `SKIP`. (If the second run of a test still sees a stored digest and skips as unchanged, that is a real finding: STOP and report.)
Revert bite: `cp go/internal/ical/reconcile.go /tmp/reconcile.go.bak`. In `cancelReservationUnlessClaimed` temporarily delete the three lines from `AND NOT EXISTS (SELECT 1 FROM submission_claim c JOIN guest g ...` through `... c.claimed_at >= $3)\`,` keeping the closing backtick (the SQL then ends after `AND status = 'active'`) and change the args to `now, id)`. Run `cd go && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ical/ -count=1 -run 'DeferredWhileClaimLive' 2>&1 | tail -30`. Expected: both FAIL (`status = "cancelled", want active`). Restore with `cp /tmp/reconcile.go.bak go/internal/ical/reconcile.go`, rerun, expected PASS. If neither fails under the revert, STOP.

**Step 7. Area run, pins, lint, report.** Commands, each as written:
1. `cd App && .venv/bin/python -m pytest tests/test_icalsync.py tests/test_ical_skip_unchanged.py tests/test_sm_reservation_claim_state.py tests/test_sm_queues.py tests/test_sm_go_parity.py -q --tb=short 2>&1 | tail -30` expected all passed.
2. `cd go && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ical/ -count=1 2>&1 | tail -30` expected `ok`.
3. `cd go && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ical/ -count=1 -v 2>&1 | grep -c SKIP | tail -3` expected `0`.
4. `cd go && go vet ./internal/ical/ 2>&1 | tail -30` expected silent; `cd go && gofmt -l internal/ical/ 2>&1 | tail -5` expected silent.
5. `git diff --stat 4fff483d 2>&1 | tail -15` lists only §3 files.
6. `python3 scripts/context_lint.py 2>&1 | tail -3` expected `context lint: OK`.
Then write `docs/tasks/1139-report.md` per §9 and set `Status: review` at the top of this brief.

## 5. Do not touch

`App/app/reporting.py`, everything under `go/internal/ubyport/` (brief 1138 is editing them), `App/app/billing*`, `App/app/door_codes.py`, `App/app/claim.py` (`expire_on_cancel` unchanged), `App/app/db.py`, `App/app/migrations/`, the 1136 date-move helpers and their tests. No commit, no push. Hard rules: SQL only in the shapes shown; no new dependency; privacy rules unaffected (no personal-data field, no outbound request).

## 6. Commands

See Steps 1-7; every command ends `| tail -30` (or `tail -3` / `tail -5`). Tests are the test-map row "Calendar, iCal feeds" narrowed to `test_icalsync.py test_ical_skip_unchanged.py`, the three `test_sm_*` pins (they read changed neighbouring code), and the Go package `./internal/ical/`. Never the full suite.

## 7. Acceptance

- [ ] Both languages cancel only through the guarded helper: `grep -n "cancelled'" App/app/icalsync.py | tail -5` shows the one UPDATE inside `_cancel_reservation_unless_claimed`; `grep -n "status = 'cancelled'" go/internal/ical/*.go | grep -v _test | tail -5` shows one hit (reconcile.go).
- [ ] `lock_key` in `_cancel_reservation_unless_claimed` and `lockStayGuests` in Go (ascending id, key `hashtext('guest')` with `int32(id)`).
- [ ] A deferred cancel stores no digest and leaves the stay active; after the claim is deleted the next sync cancels (all four new tests assert both).
- [ ] The four new tests fail under the guard revert (shown in the report) and pass restored.
- [ ] Go ical tests PASS against Postgres, 0 SKIP; `go vet` silent; Python area and pin tests green.
- [ ] `git diff --stat` lists only the §3 files; `python3 scripts/context_lint.py 2>&1 | tail -3` says OK.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear (including: a Go Postgres test SKIPs, a second sync with the same body is skipped as unchanged, a test_sm_* pin fails);
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1139-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `App/app/icalsync.py`: `_cancel_reservation_unless_claimed` (lock order, `rowcount`, parameter order), `_cancel_existing_stay` return values (every early return is `False`), the two call sites (deferred stay counted as seen, `deferred_in_flight` drops the digest).
- `go/internal/ical/reconcile.go`: `lockStayGuests` (key must match `ubyport/claim.go`), `cancelReservationUnlessClaimed` (`$n` order), `cancelExistingStay` `(bool, error)` returns.
- `go/internal/ical/syncfeed.go`: `err` shadowing in the sweep loop; `seen[ev.UID]` set only when deferred.
- The two revert-bite proofs in the report.

## Owner steps

1. Review and merge PR #933 when green, using `scripts/merge-pr-on-green.sh`.
2. Decide the open question: should a `running` / `outcome_unknown` submission with no live claim also defer a cancel (as it defers a date move)? If yes, ask the orchestrator for a follow-up brief; it would need a rule for a stay stuck in `outcome_unknown`, which is never retried.
