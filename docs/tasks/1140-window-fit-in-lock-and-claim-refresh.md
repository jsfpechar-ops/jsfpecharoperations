# 1140: iCal date move: fit the guest windows inside the locked transaction, tidy the Go twin

Status: todo
Depends on: 1139 | Base commit: 8e512d47 (HEAD of branch claude/clever-fermi-tudhnt, PR #933) | Branch: task/1140-window-fit-in-lock
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

HIGH RISK filing path: the reviewer reads every diff line in the Risk list. This brief is half of a pair: 1140 (this file) fits the windows atomically and tidies the Go twin; 1140b renews the submission claim before each batch send. They touch different files; 1140b depends on this brief only to keep the order fixed.

## 1. Objective

Make the guest stay-window fit part of the same transaction as the guarded reservation date move (1136/1139 locks held), in Python and Go, so a sweep can never file an old window against the new reservation, and a move that is deferred changes nothing. Also: Go stored-dates check becomes NULL-safe, a move skipped because the host edited the dates is logged as `ical_dates_deferred_changed`, and `syncfeed.go` reuses `lockStayGuests`.

## 2. Context

Today `sync_feed` (`App/app/icalsync.py` ~865) calls `_update_reservation_unless_claimed(existing, changed)` (commits, locks released), and only later, at ~901, `_fit_unsent_guest_windows(...)`, which runs without the guest advisory locks and writes through `db.update_if` on other connections. Go does the same (`updateReservationUnlessClaimed` in `go/internal/ical/syncfeed.go`, then `fitUnsentGuestWindows` in `reconcile.go`). Two failures:

1. After the move commits and before the fit, a sweep's `collect_sendable` can read the guest's OLD window with the NEW reservation `updated_at`; `claim_sendable` then passes its re-check and the old window is filed.
2. If a claim wins the gap, or the process dies between the two writes, the windows are never fitted: the next poll sees no date change.

Fix: the fit runs inside `_update_reservation_unless_claimed` / `updateReservationUnlessClaimed`, on the same cursor/transaction, under the locks already held, only when the reservation UPDATE applied (rowcount 1). A deferred move writes nothing. Audit rows (`guest_stay_window_fitted`) are written after the commit (Python `db.audit`, Go `ubyport.Audit`), so a crash can lose an audit line but never splits the move from the fit.

The helper keeps its return type (bool; two 1136 tests assert `is False` / `is True`). A new optional argument `move` (Python dict, Go `*dateMove`) carries the fit input in and two results out: `moved` (windows fitted) and `reason` (`"claimed"` when a live claim exists, `"changed"` when the stored dates no longer matched). `reason` is decided by a cheap re-check inside the same transaction after a 0-row UPDATE. The caller logs `ical_dates_deferred_changed` for `"changed"`, else `ical_dates_deferred_in_flight` (same text in both languages). A deferred move still sets `deferred_in_flight` / `deferredInFlight` so the digest is not stored and the next poll retries.

Existing Python helper (`App/app/icalsync.py` ~408-437) already uses `db.immediate()`, `db.lock_key`, `db.null_safe_eq`. Existing Go helper (`syncfeed.go` ~91-170) duplicates `lockStayGuests` (`reconcile.go` ~316) and compares `date_from = $n` (not NULL-safe). Fit rules are unchanged: window = old window clipped to the new dates; if empty, the new dates; skip guests that are `sent`, archived, have a live claim, or point at a `running` / `outcome_unknown` submission. No pin in `test_sm_*` reads the fit or the reservation-move SQL (they pin `guest.submit_state`, `submission.state`, `reservation_claim.state`, queues and TRANSITIONS parity); the fit writes `stay_from`, `stay_to`, `updated_at` only. Step 8 runs them; if one fails, STOP.

Go test helpers: `testPool`, `seedApartment(t,pool) int64`, `newIcalFeed(t,pool,aid,url) Feed`, `seedStay(t,pool,aid,feedID,uid,from,to) int64`, `seedGuest(t,pool,stay,state,from,to) int64`, `scalarText`, `scalarInt`, `must`, `epochSeconds`. Python: `_moved_stay(tmp_path, monkeypatch)` returns `(feed_id, reservation_id, guest_id)` with the stay and the guest at 2099-01-10..12; `_sync(feed_id)`.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/icalsync.py | edit | helper takes `move`, fit moves into the transaction (`_fit_windows_in_tx`), call sites, log key |
| App/tests/test_icalsync.py | edit | append 4 tests |
| go/internal/ical/reconcile.go | edit | `fitUnsentGuestWindows` runs on a `pgx.Tx`; add `liveClaimInTx` |
| go/internal/ical/reconcile_test.go | edit | `TestFitUnsentGuestWindows` runs inside a tx |
| go/internal/ical/syncfeed.go | edit | `dateMove`, helper uses `lockStayGuests`, NULL-safe dates, fit inside, log key, call sites |
| go/internal/ical/syncfeed_test.go | edit | 3 existing calls get `nil`; append 2 tests |
| docs/tasks/1140-window-fit-in-lock-and-claim-refresh.md | status | set `review` at the end |
| docs/tasks/1140-report.md | create | report |

No other file may change. Do NOT touch door_codes.py, billing*, reporting.py, claim.go, sweep.go.

## 4. Steps

**Step 1. Python: replace the helper and the post-hoc fit.** Run these first; each must print `1`, else STOP (anchor missing):
`cd /home/user/jsfpecharoperations && grep -c "^def _update_reservation_unless_claimed(existing, values: dict) -> bool:" App/app/icalsync.py && grep -c "^def _fit_unsent_guest_windows(" App/app/icalsync.py && grep -c "^def _warn_if_guests_registered(reservation, apartment_id: int, variant: str) -> None:" App/app/icalsync.py`

Delete both old functions (everything from the helper's `def` up to, not including, `_warn_if_guests_registered`):
```
cd /home/user/jsfpecharoperations && python3 -I - <<'PY'
p = "App/app/icalsync.py"
s = open(p, encoding="utf-8").read()
start = "def _update_reservation_unless_claimed(existing, values: dict) -> bool:"
end = "def _warn_if_guests_registered(reservation, apartment_id: int, variant: str) -> None:"
assert s.count(start) == 1 and s.count(end) == 1
a, b = s.index(start), s.index(end)
assert a < b
open(p, "w", encoding="utf-8").write(s[:a] + s[b:])
PY
```
Then Edit `App/app/icalsync.py`: old_string `def _warn_if_guests_registered(reservation, apartment_id: int, variant: str) -> None:` new_string = the code below followed by that same line:
```python
def _update_reservation_unless_claimed(
    existing, values: dict, move: Optional[dict] = None
) -> bool:
    """Write a date move only if no live submission_claim covers the stay.

    In one transaction: take the claim path's per-guest advisory locks (all
    the stay's guests, ascending id, ``db.lock_key(cur, "guest", id)``), then
    run one conditional UPDATE. A claim that committed first is then visible to
    the NOT EXISTS; a claim that comes later waits for this commit. The stored
    dates must be unchanged too, so a host edit in between is deferred, not
    overwritten. False means skipped: the caller keeps the stored dates and the
    next sync retries.

    ``move`` (``apartment_id``, ``new_from``, ``new_to``) also fits the unsent
    guest windows in this same transaction, under the same locks, and only
    when the UPDATE applied; a skipped move changes nothing. The helper writes
    ``move["moved"]`` (windows fitted) and ``move["reason"]`` (``"claimed"``
    when a live claim exists, ``"changed"`` when the stored dates moved).
    ``values`` must then hold ``updated_at``.
    """
    live_after = time.time() - reporting.SUBMISSION_CLAIM_TTL_SECONDS
    sets = ", ".join(f"{k} = ?" for k in values)
    fitted: List[str] = []
    owner_user_id = None
    reason = ""
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
        applied = cur.rowcount == 1
        if move is not None and applied:
            cur.execute(
                "SELECT owner_user_id FROM apartment WHERE id = ?", (move["apartment_id"],)
            )
            row = cur.fetchone()
            owner_user_id = row["owner_user_id"] if row else None
            fitted = _fit_windows_in_tx(
                cur,
                existing["id"],
                move["new_from"],
                move["new_to"],
                values["updated_at"],
                live_after,
            )
        elif move is not None:
            cur.execute(
                "SELECT 1 AS n FROM submission_claim c JOIN guest g ON g.id = c.guest_id "
                "WHERE g.reservation_id = ? AND g.archived_at IS NULL "
                "AND c.claimed_at >= ? LIMIT 1",
                (existing["id"], live_after),
            )
            reason = "claimed" if cur.fetchone() else "changed"
    if move is not None:
        move["reason"] = reason
        move["moved"] = len(fitted)
        # After the commit: a crash can lose an audit line, never split the move.
        for detail in fitted:
            db.audit("guest_stay_window_fitted", detail, owner_user_id=owner_user_id)
    return applied


def _fit_windows_in_tx(
    cur, reservation_id: int, new_from: str, new_to: str, now: str, live_after: float
) -> List[str]:
    """Trim unsent guest stay windows to a booking that moved, on ``cur``.

    Runs inside ``_update_reservation_unless_claimed``'s transaction, with the
    stay's guest locks held. Returns one audit detail per guest changed.
    """
    from . import validation

    new_start = validation.parse_iso_date(new_from)
    new_end = validation.parse_iso_date(new_to)
    if not new_start or not new_end:
        return []
    cur.execute(
        "SELECT id, stay_from, stay_to, submit_state FROM guest "
        "WHERE reservation_id = ? AND archived_at IS NULL AND submit_state != ?",
        (reservation_id, reporting.SENT),
    )
    details: List[str] = []
    for guest in cur.fetchall():
        sf = validation.parse_iso_date(guest["stay_from"]) or new_start
        st = validation.parse_iso_date(guest["stay_to"]) or new_end
        fitted_from = max(sf, new_start)
        fitted_to = min(st, new_end)
        if fitted_from >= fitted_to:
            fitted_from, fitted_to = new_start, new_end
        new_sf, new_st = fitted_from.isoformat(), fitted_to.isoformat()
        if guest["stay_from"] == new_sf and guest["stay_to"] == new_st:
            continue
        # Compare-and-set: a guest the register already accepted, or whose last
        # send has no clear answer, must keep the window that went on the wire.
        cur.execute(
            "UPDATE guest SET stay_from = ?, stay_to = ?, updated_at = ? "
            f"WHERE id = ? AND {db.null_safe_eq('submit_state')} "
            "AND NOT EXISTS (SELECT 1 FROM submission_claim "
            "WHERE guest_id = ? AND claimed_at >= ?) "
            "AND (submission_id IS NULL OR NOT EXISTS ("
            "SELECT 1 FROM submission WHERE id = guest.submission_id "
            "AND state IN ('running', 'outcome_unknown')))",
            (
                new_sf,
                new_st,
                now,
                guest["id"],
                guest["submit_state"],
                guest["id"],
                live_after,
            ),
        )
        if cur.rowcount != 1:
            continue
        details.append(
            f"guest={guest['id']} reservation={reservation_id} "
            f"was={guest['stay_from']}..{guest['stay_to']} now={new_sf}..{new_st}"
        )
    return details


def _warn_if_guests_registered(reservation, apartment_id: int, variant: str) -> None:
```
Check no column of `guest` that the fit writes is encrypted: `cd /home/user/jsfpecharoperations/App && .venv/bin/python -c "from app import db; c=db.ENCRYPTED_COLUMNS.get('guest',{}); print([k for k in ('stay_from','stay_to','updated_at','submit_state') if k in c])" 2>&1 | tail -3` expected `[]` (else STOP). Syntax check: `cd /home/user/jsfpecharoperations/App && .venv/bin/python -c "import app.icalsync" 2>&1 | tail -3` expected: no output.

**Step 2. Python: call sites in `sync_feed`.** Do the four edits with the Edit tool, each old_string verbatim.

2a. old_string:
```
            if dates_changed and _send_in_flight(existing["id"]):
```
new_string:
```
            move = None
            if dates_changed and _send_in_flight(existing["id"]):
```
2b. old_string:
```
                applied = False
                if dates_changed:
                    applied = _update_reservation_unless_claimed(existing, changed)
```
new_string:
```
                applied = False
                if dates_changed:
                    move = {
                        "apartment_id": feed["apartment_id"],
                        "new_from": event["date_from"],
                        "new_to": event["date_to"],
                    }
                    applied = _update_reservation_unless_claimed(existing, changed, move)
```
2c. old_string (28-space indent; the first occurrence of this key at 16-space indent is NOT touched):
```
                        log.warning(
                            "ical_dates_deferred_in_flight apartment_id=%s reservation_id=%s "
                            "stored=%s..%s calendar=%s..%s",
                            feed["apartment_id"],
```
new_string:
```
                        log.warning(
                            "%s apartment_id=%s reservation_id=%s "
                            "stored=%s..%s calendar=%s..%s",
                            "ical_dates_deferred_changed"
                            if move.get("reason") == "changed"
                            else "ical_dates_deferred_in_flight",
                            feed["apartment_id"],
```
2d. old_string:
```
            if dates_changed:
                moved = _fit_unsent_guest_windows(
                    existing["id"],
                    feed["apartment_id"],
                    event["date_from"],
                    event["date_to"],
                    now,
                )
                if moved:
```
new_string:
```
            if dates_changed:
                moved = move["moved"] if move else 0
                if moved:
```
Command: `cd /home/user/jsfpecharoperations/App && grep -n "_fit_unsent_guest_windows" app/icalsync.py | tail -3; .venv/bin/python -m pytest tests/test_icalsync.py tests/test_ical_skip_unchanged.py -q --tb=short -x 2>&1 | tail -30`. Expected: grep prints nothing; existing tests pass (the window-fit tests at ~285-520 now go through the helper).

**Step 3. Python tests.** Append to `App/tests/test_icalsync.py`:
```python
_FIT_MOVED = {
    "date_from": "2099-02-10",
    "date_to": "2099-02-12",
    "updated_at": "2099-01-01T00:00:00+00:00",
}


def _fit_move(reservation_id):
    row = db.query_one("SELECT apartment_id FROM reservation WHERE id = ?", (reservation_id,))
    return {"apartment_id": row["apartment_id"], "new_from": "2099-02-10", "new_to": "2099-02-12"}


def _dates_and_window(reservation_id, guest_id):
    stay = db.query_one(
        "SELECT date_from, date_to FROM reservation WHERE id = ?", (reservation_id,)
    )
    guest = db.query_one("SELECT stay_from, stay_to FROM guest WHERE id = ?", (guest_id,))
    return (
        (stay["date_from"], stay["date_to"]),
        (guest["stay_from"], guest["stay_to"]),
    )


def test_date_move_fits_the_guest_windows_in_the_same_transaction(monkeypatch, tmp_path):
    _feed_id, reservation_id, guest_id = _moved_stay(tmp_path, monkeypatch)
    existing = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
    move = _fit_move(reservation_id)

    assert icalsync._update_reservation_unless_claimed(existing, dict(_FIT_MOVED), move) is True

    assert _dates_and_window(reservation_id, guest_id) == (
        ("2099-02-10", "2099-02-12"),
        ("2099-02-10", "2099-02-12"),
    )
    assert move["moved"] == 1
    audit = db.query_one(
        "SELECT COUNT(*) AS n FROM audit WHERE action = 'guest_stay_window_fitted'"
    )
    assert audit["n"] == 1

    # Atomic: when the fit fails, the reservation move rolls back with it.
    db.update("reservation", reservation_id, {"date_from": "2099-01-10", "date_to": "2099-01-12"})
    db.update("guest", guest_id, {"stay_from": "2099-01-10", "stay_to": "2099-01-12"})
    existing = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))

    def boom(*_args, **_kwargs):
        raise RuntimeError("fit failed")

    monkeypatch.setattr(icalsync, "_fit_windows_in_tx", boom)
    with pytest.raises(RuntimeError):
        icalsync._update_reservation_unless_claimed(
            existing, dict(_FIT_MOVED), _fit_move(reservation_id)
        )
    assert _dates_and_window(reservation_id, guest_id) == (
        ("2099-01-10", "2099-01-12"),
        ("2099-01-10", "2099-01-12"),
    )


def test_a_deferred_date_move_changes_neither_stay_nor_windows(monkeypatch, tmp_path):
    _feed_id, reservation_id, guest_id = _moved_stay(tmp_path, monkeypatch)
    existing = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
    unchanged = (("2099-01-10", "2099-01-12"), ("2099-01-10", "2099-01-12"))
    db.execute(
        "INSERT INTO submission_claim (guest_id, claim_token, claimed_at) "
        "VALUES (?, 'race', ?)",
        (guest_id, time.time()),
    )
    move = _fit_move(reservation_id)
    try:
        assert icalsync._update_reservation_unless_claimed(existing, dict(_FIT_MOVED), move) is False
        assert move["reason"] == "claimed"
        assert move["moved"] == 0
        assert _dates_and_window(reservation_id, guest_id) == unchanged
    finally:
        db.execute("DELETE FROM submission_claim WHERE guest_id = ?", (guest_id,))

    # A host edit after the read: the stored dates no longer match.
    db.update("reservation", reservation_id, {"date_from": "2099-01-11"})
    move = _fit_move(reservation_id)
    assert icalsync._update_reservation_unless_claimed(existing, dict(_FIT_MOVED), move) is False
    assert move["reason"] == "changed"
    assert move["moved"] == 0
    assert _dates_and_window(reservation_id, guest_id) == (
        ("2099-01-11", "2099-01-12"),
        ("2099-01-10", "2099-01-12"),
    )


def test_a_host_edit_during_the_sync_logs_deferred_changed(monkeypatch, tmp_path, caplog):
    feed_id, reservation_id, guest_id = _moved_stay(tmp_path, monkeypatch)

    def host_edits_the_dates(_reservation_id):
        db.update("reservation", reservation_id, {"date_from": "2099-01-11"})
        return False

    monkeypatch.setattr(icalsync, "_send_in_flight", host_edits_the_dates)
    with caplog.at_level("WARNING"):
        _sync(feed_id)
    assert "ical_dates_deferred_changed" in caplog.text
    assert "ical_dates_deferred_in_flight" not in caplog.text
    window = db.query_one("SELECT stay_from, stay_to FROM guest WHERE id = ?", (guest_id,))
    assert (window["stay_from"], window["stay_to"]) == ("2099-01-10", "2099-01-12")


def test_a_claim_landing_after_the_precheck_logs_deferred_in_flight(
    monkeypatch, tmp_path, caplog
):
    feed_id, _reservation_id, guest_id = _moved_stay(tmp_path, monkeypatch)
    monkeypatch.setattr(icalsync, "_send_in_flight", lambda _reservation_id: False)
    db.execute(
        "INSERT INTO submission_claim (guest_id, claim_token, claimed_at) "
        "VALUES (?, 'race', ?)",
        (guest_id, time.time()),
    )
    with caplog.at_level("WARNING"):
        _sync(feed_id)
    assert "ical_dates_deferred_in_flight" in caplog.text
    assert "ical_dates_deferred_changed" not in caplog.text
```
Check `pytest` is imported at the top of the file: `cd /home/user/jsfpecharoperations/App && grep -n "^import pytest" tests/test_icalsync.py | head -2`; if absent, add `import pytest` as its own line after the other top-level imports. Command: `cd /home/user/jsfpecharoperations/App && .venv/bin/python -m pytest tests/test_icalsync.py tests/test_ical_skip_unchanged.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass.

Revert-bite checks (restore each edit exactly afterwards, rerun green):
- (a) in `_update_reservation_unless_claimed` change `if move is not None and applied:` to `if False and move is not None and applied:`; run `-k "fits_the_guest_windows or window"`; expect FAIL (`test_date_move_fits_the_guest_windows_in_the_same_transaction` and the sync fit tests).
- (b) change `if move.get("reason") == "changed"` to `if move.get("reason") == "never"`; run `-k "logs_deferred"`; expect `test_a_host_edit_during_the_sync_logs_deferred_changed` FAIL.
- (c) in the helper replace `elif move is not None:` branch's `reason = "claimed" if cur.fetchone() else "changed"` with `reason = "claimed"`; run `-k "deferred_date_move"`; expect FAIL.
If any of (a)-(c) does not fail, STOP.

**Step 4. Go: fit runs on a transaction.** Anchors, each must print `1`:
`cd /home/user/jsfpecharoperations/go/internal/ical && grep -c "^// fitUnsentGuestWindows is _fit_unsent_guest_windows" reconcile.go && grep -c "^// warnIfGuestsRegistered is _warn_if_guests_registered (icalsync.py 469-493)." reconcile.go`
Delete the old function (from its comment to, not including, the `warnIfGuestsRegistered` comment):
```
cd /home/user/jsfpecharoperations/go/internal/ical && python3 -I - <<'PY'
p = "reconcile.go"
s = open(p, encoding="utf-8").read()
start = "// fitUnsentGuestWindows is _fit_unsent_guest_windows"
end = "// warnIfGuestsRegistered is _warn_if_guests_registered (icalsync.py 469-493).\n"
assert s.count(start) == 1 and s.count(end) == 1
a, b = s.index(start), s.index(end)
assert a < b
open(p, "w", encoding="utf-8").write(s[:a] + s[b:])
PY
```
Then Edit `reconcile.go`: old_string `// warnIfGuestsRegistered is _warn_if_guests_registered (icalsync.py 469-493).` new_string = the code below, a blank line, then that same comment line:
```go
// fitUnsentGuestWindows is _fit_windows_in_tx (icalsync.py). It runs on the
// caller's transaction, under the stay's guest locks, and writes guest rows
// only. It returns one audit detail per guest changed and the apartment
// owner; the caller writes the audit rows after the commit.
func fitUnsentGuestWindows(ctx context.Context, tx pgx.Tx, reservationID, apartmentID int64, newFrom, newTo, now string) ([]string, *int64, error) {
	newStart, okStart := validation.ParseISODate(newFrom)
	newEnd, okEnd := validation.ParseISODate(newTo)
	if !okStart || !okEnd {
		return nil, nil, nil
	}
	var owner *int64
	err := tx.QueryRow(ctx, `SELECT owner_user_id FROM apartment WHERE id = $1`, apartmentID).Scan(&owner)
	if err != nil && !errors.Is(err, pgx.ErrNoRows) {
		return nil, nil, err
	}
	type guestWindow struct {
		id          int64
		stayFrom    *string
		stayTo      *string
		submitState string
	}
	rows, err := tx.Query(ctx,
		`SELECT id, stay_from, stay_to, submit_state FROM guest
		  WHERE reservation_id = $1 AND archived_at IS NULL AND submit_state <> $2`,
		reservationID, guestSent)
	if err != nil {
		return nil, nil, err
	}
	var guests []guestWindow
	for rows.Next() {
		var g guestWindow
		if err := rows.Scan(&g.id, &g.stayFrom, &g.stayTo, &g.submitState); err != nil {
			rows.Close()
			return nil, nil, err
		}
		guests = append(guests, g)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, nil, err
	}
	parseOr := func(s *string, fallback time.Time) time.Time {
		if s != nil {
			if t, ok := validation.ParseISODate(*s); ok {
				return t
			}
		}
		return fallback
	}
	liveAfter := liveClaimAfter()
	var details []string
	for _, g := range guests {
		sf := parseOr(g.stayFrom, newStart)
		st := parseOr(g.stayTo, newEnd)
		fromT := maxDate(sf, newStart)
		toT := minDate(st, newEnd)
		if !fromT.Before(toT) {
			fromT, toT = newStart, newEnd
		}
		newSF, newST := fromT.Format(dateLayout), toT.Format(dateLayout)
		if g.stayFrom != nil && g.stayTo != nil && *g.stayFrom == newSF && *g.stayTo == newST {
			continue
		}
		oldWindow := pyStr(g.stayFrom) + ".." + pyStr(g.stayTo)
		tag, err := tx.Exec(ctx,
			`UPDATE guest SET stay_from = $1, stay_to = $2, updated_at = $3
			  WHERE id = $4 AND submit_state = $5
			    AND NOT EXISTS (SELECT 1 FROM submission_claim WHERE guest_id = $4 AND claimed_at >= $6)
			    AND (submission_id IS NULL OR NOT EXISTS (
			      SELECT 1 FROM submission WHERE id = guest.submission_id
			        AND state IN ('running', 'outcome_unknown')))`,
			newSF, newST, now, g.id, g.submitState, liveAfter)
		if err != nil {
			return nil, nil, err
		}
		if tag.RowsAffected() != 1 {
			continue
		}
		details = append(details, fmt.Sprintf("guest=%d reservation=%d was=%s now=%s..%s",
			g.id, reservationID, oldWindow, newSF, newST))
	}
	return details, owner, nil
}

// liveClaimInTx reports whether a live submission_claim covers the stay, read
// on the move's own transaction (decides the deferred reason).
func liveClaimInTx(ctx context.Context, tx pgx.Tx, reservationID int64) (bool, error) {
	var one int
	err := tx.QueryRow(ctx,
		`SELECT 1 FROM submission_claim c JOIN guest g ON g.id = c.guest_id
		  WHERE g.reservation_id = $1 AND g.archived_at IS NULL AND c.claimed_at >= $2 LIMIT 1`,
		reservationID, liveClaimAfter()).Scan(&one)
	if errors.Is(err, pgx.ErrNoRows) {
		return false, nil
	}
	return err == nil, err
}

```
Command: `cd /home/user/jsfpecharoperations/go && gofmt -l internal/ical/reconcile.go 2>&1 | tail -5`. Expected: no output. (Build fails until Step 5; that is expected here.)

**Step 5. Go: `syncfeed.go` helper and call sites.** Anchors, each must print `1`:
`cd /home/user/jsfpecharoperations/go/internal/ical && grep -c "^// sendInFlightFn is sendInFlight; tests replace it to simulate a claim that" syncfeed.go && grep -c "^func anyStr(p \*string) any {" syncfeed.go && grep -c "datesChanged := s.DateFrom != ev.DateFrom" syncfeed.go`
Delete the old helper block (it keeps `sendInFlightFn`, re-added below):
```
cd /home/user/jsfpecharoperations/go/internal/ical && python3 -I - <<'PY'
p = "syncfeed.go"
s = open(p, encoding="utf-8").read()
start = "// sendInFlightFn is sendInFlight; tests replace it to simulate a claim that"
end = "func anyStr(p *string) any {"
assert s.count(start) == 1 and s.count(end) == 1
a, b = s.index(start), s.index(end)
assert a < b
open(p, "w", encoding="utf-8").write(s[:a] + s[b:])
PY
```
Edit `syncfeed.go`: old_string `func anyStr(p *string) any {` new_string = the code below, a blank line, then `func anyStr(p *string) any {`:
```go
// sendInFlightFn is sendInFlight; tests replace it to simulate a claim that
// lands after the pre-check.
var sendInFlightFn = sendInFlight

// dateMove is the optional input and output of updateReservationUnlessClaimed.
// In: the apartment and the new dates to fit the unsent guest windows to.
// Out: Fitted (windows fitted) and Reason when the move was skipped:
// "claimed" (a live claim covers the stay) or "changed" (the stored dates moved).
type dateMove struct {
	ApartmentID    int64
	NewFrom, NewTo string
	Fitted         int
	Reason         string
}

// updateReservationUnlessClaimed writes a date move only while no live
// submission_claim covers the stay and the stored dates are still
// storedFrom..storedTo. One transaction: the claim path's per-guest advisory
// locks (lockStayGuests, ascending id, same key as ubyport.ClaimSendable),
// then one UPDATE. When move is set and the UPDATE applied, the unsent guest
// windows are fitted in the same transaction under the same locks; a skipped
// move changes nothing. False means skipped; the caller keeps the stored dates
// and the next sync retries. Python: _update_reservation_unless_claimed.
func updateReservationUnlessClaimed(ctx context.Context, pool *pgxpool.Pool, id int64, storedFrom, storedTo string, cols map[string]any, move *dateMove) (bool, error) {
	tx, err := pool.Begin(ctx)
	if err != nil {
		return false, err
	}
	defer func() { _ = tx.Rollback(ctx) }()
	if err := lockStayGuests(ctx, tx, id); err != nil {
		return false, err
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
		  AND date_from IS NOT DISTINCT FROM $%d AND date_to IS NOT DISTINCT FROM $%d
		  AND NOT EXISTS (SELECT 1 FROM submission_claim c JOIN guest g ON g.id = c.guest_id
		    WHERE g.reservation_id = reservation.id AND g.archived_at IS NULL AND c.claimed_at >= $%d)`,
			strings.Join(sets, ", "), n+1, n+2, n+3, n+4),
		args...)
	if err != nil {
		return false, err
	}
	applied := tag.RowsAffected() == 1
	var details []string
	var owner *int64
	if move != nil {
		if applied {
			now, _ := cols["updated_at"].(string)
			if details, owner, err = fitUnsentGuestWindows(ctx, tx, id, move.ApartmentID, move.NewFrom, move.NewTo, now); err != nil {
				return false, err
			}
		} else {
			live, err := liveClaimInTx(ctx, tx, id)
			if err != nil {
				return false, err
			}
			move.Reason = "changed"
			if live {
				move.Reason = "claimed"
			}
		}
	}
	if err := tx.Commit(ctx); err != nil {
		return false, err
	}
	if move != nil {
		move.Fitted = len(details)
		// After the commit: a crash can lose an audit line, never split the move.
		for _, d := range details {
			if err := ubyport.Audit(ctx, pool, "guest_stay_window_fitted", d, owner); err != nil {
				return applied, err
			}
		}
	}
	return applied, nil
}
```
Then four Edits in `syncfeed.go` (tabs, verbatim):

5a. old_string `		datesChanged := s.DateFrom != ev.DateFrom || s.DateTo != ev.DateTo` new_string:
```
		var move *dateMove
		datesChanged := s.DateFrom != ev.DateFrom || s.DateTo != ev.DateTo
```
5b. old_string `				ok, err := updateReservationUnlessClaimed(ctx, pool, s.ID, s.DateFrom, s.DateTo, changed)` new_string:
```
				move = &dateMove{ApartmentID: feed.ApartmentID, NewFrom: ev.DateFrom, NewTo: ev.DateTo}
				ok, err := updateReservationUnlessClaimed(ctx, pool, s.ID, s.DateFrom, s.DateTo, changed, move)
```
5c. old_string (five tabs on the `log.Printf`; the 4-tab pre-check log is NOT touched):
```
					deferredInFlight = true
					log.Printf("ical_dates_deferred_in_flight apartment_id=%d reservation_id=%d stored=%s..%s calendar=%s..%s",
						feed.ApartmentID, s.ID, s.DateFrom, s.DateTo, ev.DateFrom, ev.DateTo)
```
new_string:
```
					deferredInFlight = true
					event := "ical_dates_deferred_in_flight"
					if move.Reason == "changed" {
						event = "ical_dates_deferred_changed"
					}
					log.Printf("%s apartment_id=%d reservation_id=%d stored=%s..%s calendar=%s..%s",
						event, feed.ApartmentID, s.ID, s.DateFrom, s.DateTo, ev.DateFrom, ev.DateTo)
```
If a variable named `event` already exists in that scope the build fails: rename to `deferKey` in both lines.

5d. old_string:
```
			moved, err := fitUnsentGuestWindows(ctx, pool, s.ID, feed.ApartmentID, ev.DateFrom, ev.DateTo)
			if err != nil {
				return stats, err
			}
			if moved > 0 {
				log.Printf("ical_dates_moved_guests apartment_id=%d reservation_id=%d guests=%d",
					feed.ApartmentID, s.ID, moved)
			}
```
new_string:
```
			if move != nil && move.Fitted > 0 {
				log.Printf("ical_dates_moved_guests apartment_id=%d reservation_id=%d guests=%d",
					feed.ApartmentID, s.ID, move.Fitted)
			}
```
Fix the three 1136 tests' call sites: `cd /home/user/jsfpecharoperations/go/internal/ical && sed -i 's/\(updateReservationUnlessClaimed(ctx, pool, stay, "[0-9-]*", "[0-9-]*", cols\))/\1, nil)/' syncfeed_test.go && grep -c "cols, nil)" syncfeed_test.go` expected `3`.
Update `TestFitUnsentGuestWindows` in `reconcile_test.go`: replace the block from `	moved, err := fitUnsentGuestWindows(ctx, pool, res, apt, "2026-01-03", "2026-01-07")` through `		t.Fatalf("moved = %d, want 1", moved)\n	}` (the call and its `must` / length check) with:
```
	tx, err := pool.Begin(ctx)
	must(t, err)
	details, _, err := fitUnsentGuestWindows(ctx, tx, res, apt, "2026-01-03", "2026-01-07", "2026-01-05T00:00:00+00:00")
	must(t, err)
	must(t, tx.Commit(ctx))
	if len(details) != 1 {
		t.Fatalf("details = %v, want 1", details)
	}
```
and replace the audit assertion (`if n := scalarInt(t, pool, \`SELECT COUNT(*) FROM audit WHERE action = 'guest_stay_window_fitted'\`); n != 1 {` ... its block, 3 lines) with nothing (the audit is written by the caller now), and replace the last block (`if n, err := fitUnsentGuestWindows(ctx, pool, res, apt, "not-a-date", "2026-01-07"); err != nil || n != 0 {` ... `}`) with:
```
	tx2, err := pool.Begin(ctx)
	must(t, err)
	defer func() { _ = tx2.Rollback(ctx) }()
	if d, _, err := fitUnsentGuestWindows(ctx, tx2, res, apt, "not-a-date", "2026-01-07", "2026-01-05T00:00:00+00:00"); err != nil || len(d) != 0 {
		t.Fatalf("bad date: %v, %v", d, err)
	}
```
Command: `cd /home/user/jsfpecharoperations/go && gofmt -l internal/ical 2>&1 | tail -5; go vet ./internal/ical/ 2>&1 | tail -10`. Expected: no output from either.

**Step 6. Go tests.** Append to `go/internal/ical/syncfeed_test.go`:
```go
func TestDateMoveFitsGuestWindowsInTheSameTransaction(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/fit-tx.ics")
	stay := seedStay(t, pool, aid, feed.ID, "u-fit-tx", "2027-08-01", "2027-08-05")
	g := seedGuest(t, pool, stay, "pending", "2027-08-01", "2027-08-05")
	cols := map[string]any{"date_from": "2027-08-10", "date_to": "2027-08-14", "updated_at": ubyport.UTCNow()}
	move := &dateMove{ApartmentID: aid, NewFrom: "2027-08-10", NewTo: "2027-08-14"}
	ok, err := updateReservationUnlessClaimed(ctx, pool, stay, "2027-08-01", "2027-08-05", cols, move)
	must(t, err)
	if !ok {
		t.Fatal("date move skipped without a claim")
	}
	if got := scalarText(t, pool, `SELECT date_from || ' ' || date_to FROM reservation WHERE id = $1`, stay); got != "2027-08-10 2027-08-14" {
		t.Fatalf("stay = %q", got)
	}
	if got := scalarText(t, pool, `SELECT stay_from || ' ' || stay_to FROM guest WHERE id = $1`, g); got != "2027-08-10 2027-08-14" {
		t.Fatalf("guest window = %q, want fitted with the move", got)
	}
	if move.Fitted != 1 {
		t.Fatalf("Fitted = %d, want 1", move.Fitted)
	}
	if n := scalarInt(t, pool, `SELECT COUNT(*) FROM audit WHERE action = 'guest_stay_window_fitted'`); n != 1 {
		t.Fatalf("audit rows = %d, want 1", n)
	}
}

func TestDeferredDateMoveChangesNeitherStayNorWindows(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	aid := seedApartment(t, pool)
	feed := newIcalFeed(t, pool, aid, "https://feed.test/defer-tx.ics")
	stay := seedStay(t, pool, aid, feed.ID, "u-defer-tx", "2027-09-01", "2027-09-05")
	g := seedGuest(t, pool, stay, "pending", "2027-09-01", "2027-09-05")
	_, err := pool.Exec(ctx, `INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES ($1, 'race', $2)`,
		g, epochSeconds())
	must(t, err)
	cols := map[string]any{"date_from": "2027-09-10", "date_to": "2027-09-14", "updated_at": ubyport.UTCNow()}
	check := func(wantStay, wantWindow string) {
		t.Helper()
		if got := scalarText(t, pool, `SELECT date_from || ' ' || date_to FROM reservation WHERE id = $1`, stay); got != wantStay {
			t.Fatalf("stay = %q, want %q", got, wantStay)
		}
		if got := scalarText(t, pool, `SELECT stay_from || ' ' || stay_to FROM guest WHERE id = $1`, g); got != wantWindow {
			t.Fatalf("guest window = %q, want %q", got, wantWindow)
		}
	}
	move := &dateMove{ApartmentID: aid, NewFrom: "2027-09-10", NewTo: "2027-09-14"}
	ok, err := updateReservationUnlessClaimed(ctx, pool, stay, "2027-09-01", "2027-09-05", cols, move)
	must(t, err)
	if ok || move.Reason != "claimed" || move.Fitted != 0 {
		t.Fatalf("live claim: ok=%v reason=%q fitted=%d", ok, move.Reason, move.Fitted)
	}
	check("2027-09-01 2027-09-05", "2027-09-01 2027-09-05")

	_, err = pool.Exec(ctx, `DELETE FROM submission_claim WHERE guest_id = $1`, g)
	must(t, err)
	move = &dateMove{ApartmentID: aid, NewFrom: "2027-09-10", NewTo: "2027-09-14"}
	ok, err = updateReservationUnlessClaimed(ctx, pool, stay, "2027-09-02", "2027-09-05", cols, move)
	must(t, err)
	if ok || move.Reason != "changed" || move.Fitted != 0 {
		t.Fatalf("stored dates moved: ok=%v reason=%q fitted=%d", ok, move.Reason, move.Fitted)
	}
	check("2027-09-01 2027-09-05", "2027-09-01 2027-09-05")
}
```
Command: `cd /home/user/jsfpecharoperations/go && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ical/ -count=1 -run 'DateMove|UpdateReservationUnlessClaimed|FitUnsent|SyncFeed' -v 2>&1 | tail -30`. Expected: every listed test `--- PASS`, none `--- SKIP`.

Revert-bite checks (restore exactly, rerun green):
- (a) in `updateReservationUnlessClaimed` change `if applied {` (inside `if move != nil {`) to `if false && applied {`; run `-run 'FitsGuestWindows'`; expect FAIL.
- (b) change `move.Reason = "changed"` to `move.Reason = "claimed"`; run `-run 'DeferredDateMove'`; expect FAIL.
- (c) replace `date_from IS NOT DISTINCT FROM $%d AND date_to IS NOT DISTINCT FROM $%d` back with `date_from = $%d AND date_to = $%d` only to confirm the tests still pass (the NULL-safe form is not observable because both columns are NOT NULL); then restore. This is a read-through item, not a bite.
If (a) or (b) does not fail, STOP.

**Step 7. NULL-safe and duplicate-removal check.** Command: `cd /home/user/jsfpecharoperations/go/internal/ical && grep -c "IS NOT DISTINCT FROM" syncfeed.go; grep -c "pg_advisory_xact_lock" syncfeed.go reconcile.go`. Expected: `2`; then `syncfeed.go:0` and `reconcile.go:1`.

**Step 8. Final run and report.** Run, from `App/`: `.venv/bin/python -m pytest tests/test_icalsync.py tests/test_ical_skip_unchanged.py tests/test_claim_recheck_stay.py tests/test_claim_*.py tests/test_stale_submission.py tests/test_submission_*.py tests/test_sm_*.py -q --tb=short 2>&1 | tail -30` (expected all pass; a failing `test_sm_*` pin means STOP and name the pin in the report). From `go/`: `UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ical/ ./internal/ubyport/ -count=1 2>&1 | tail -30` (must print `ok` for both, not `SKIP`; add `-v | grep -c SKIP` expected 0), `go vet ./internal/ical/ ./internal/ubyport/ 2>&1 | tail -10` (no output), `gofmt -l internal 2>&1 | tail -5` (no output). From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -3` expected OK. Write the report (§9) and set `Status: review`.

## 5. Do not touch

- Any file outside §3. No `door_codes.py`, no `billing*`, no `reporting.py`, `claim.go`, `sweep.go` (1140b).
- AGENTS.md hard rules that apply: 1 (UbyPort filing correctness beats everything), 3 (public repo: no secrets, guest data, or operator identity in tests or logs), 5 (SQL stays Postgres-portable; no schema change), 8 (never push to `main`; merge only via `scripts/merge-pr-on-green.sh`; keep the PR draft). No new dependency, no template or CSS change, no new personal-data field.
- Do not change the pre-check log (`ical_dates_deferred_in_flight` at 16-space indent in Python, 4 tabs in Go) or `_send_in_flight` / `sendInFlight`.

## 6. Commands

Python from `App/` (each ending `2>&1 | tail -30`): the Step 3 and Step 8 pytest commands. Go from `go/`: the Step 6 and Step 8 commands with `UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest`. Expected output is stated per step. Never the full suite.

## 7. Acceptance

- [ ] `grep -c "_fit_unsent_guest_windows" App/app/icalsync.py` prints 0 and `grep -c "_fit_windows_in_tx" App/app/icalsync.py` prints 2 or more.
- [ ] The four new Python tests and the two new Go tests pass; Go output has no SKIP.
- [ ] Revert-bite checks (a)-(c) in Step 3 and (a)-(b) in Step 6 each failed as stated and were restored.
- [ ] `grep -c "IS NOT DISTINCT FROM" go/internal/ical/syncfeed.go` prints 2; `syncfeed.go` has no `pg_advisory_xact_lock`.
- [ ] A deferred move (claim live, or stored dates changed) leaves reservation and guest windows unchanged (tests `deferred_date_move` / `DeferredDateMove`).
- [ ] `test_sm_*`, `go vet`, `gofmt -l` clean; `python3 scripts/context_lint.py 2>&1 | tail -3` is OK.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt or anchor is not found, or a count in Step 1/4/5 is not `1`;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a revert-bite check does not fail;
- a `test_sm_*` pin fails;
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1140-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

The reviewer reads every line of:
- `App/app/icalsync.py`: `_update_reservation_unless_claimed`, `_fit_windows_in_tx`, the `sync_feed` call sites (edits 2a-2d). Check the guest UPDATE keeps all four guards (state CAS, no live claim, no running/outcome_unknown submission, not sent) and that no write happens when the reservation UPDATE did not apply.
- `go/internal/ical/syncfeed.go`: `updateReservationUnlessClaimed`, `dateMove`, call sites; `go/internal/ical/reconcile.go`: `fitUnsentGuestWindows`, `liveClaimInTx`. Check locks are taken before the UPDATE and held until `Commit`, and that audit rows are written after the commit.
- Known limitation to confirm: the NULL-safe Go comparison cannot be exercised by a test because `reservation.date_from` / `date_to` are NOT NULL; it matches Python's `db.null_safe_eq`.

## Owner steps

1. None for this brief. After review, Josef merges with `scripts/merge-pr-on-green.sh` once the draft may ship (green merges auto-deploy).
