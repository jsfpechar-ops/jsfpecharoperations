# 1138: the send claim re-checks the stay window and updated_at the payload was built from

Status: review
Depends on: none | Base commit: 116def7d | Branch: task/1138-claim-rechecks-stay-window
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

HIGH RISK: this is the UbyPort filing path ([UBYPORT_CORE](../UBYPORT_CORE.md), hard rule 1). Python and Go must behave the same.

## Open questions

The executor does nothing here. Owner decisions only.

Decided by the orchestrator (no action for the executor):

1. **No retry.** A host send that loses the race to a date move or edit files nothing; the next sweep sends fresh data. The host path already handles this: when `submit_for_apartment` returns `[]`, `App/app/routes/admin.py` (~4465) flashes the existing `flash.error.nothing_sendable` via `_back(...)`, and the bulk path (~3996) just `continue`s. Neither raises, so nothing reports an error beyond that existing flash. No copy change.
2. **Fail closed in Go.** `ClaimPair.Built == nil` is not claimed. Every caller passes `Built` (see Step 5).

Follow-up for a later brief (do not change here):

3. **`updated_at` is not bumped by every writer.** `db.update("guest", ...)` in `App/app/passport_photos.py:299` skips it (it writes only `passport_photo_at`, not a payload field; `routes/stay_fees.py:1164` does bump it, see 1145). So `updated_at` is the cheap guard, not a complete one; the stay window is compared directly because it is the field iCal moves. A per-field compare of name, document number, nationality and birth date (decrypting `*_enc` inside the claim) is a separate brief.

## 1. Objective

The claim re-reads the guest's and the reservation's stay window and `updated_at` inside its transaction, after the per-guest advisory lock, and drops any guest whose values differ from the ones the payload was built from. A date move or host edit that lands between "build the payload" and "take the claim" then files nothing; the next sweep rebuilds and sends the new dates.

## 2. Context

**Facts verified on this branch.** The payload is built from the `(guest, reservation)` rows `collect_sendable` returns (Go: `BatchPair` from `CollectSendable`, `go/internal/ubyport/collect.go` ~250). Dates in the payload come from `guest.stay_from/stay_to` and `reservation.date_from/date_to`. The claim today re-reads only `submit_state`, `archived_at`, `manual_filed_at` (Python and Go, confirmed). `submit_state` only changes when a writer sets it, so a date move does not change it. The iCal reservation UPDATE is guarded against a live claim (`go/internal/ical/syncfeed.go:108`), which covers "move after claim"; this brief covers "move before claim". Nothing in `test_sm_*` pins the claim SQL (`grep -n -i claim` in `test_sm_go_parity.py`, `test_sm_guest_submit_state.py`, `test_sm_submission_state.py` finds only table names and an `INSERT INTO submission_claim` writer check, none read the SELECT), so no pin test changes.

**Python anchor** (`App/app/reporting.py`, `claim_sendable`):

```python
        for guest, _reservation in pairs:
            cur.execute(
                "SELECT submit_state, archived_at, manual_filed_at FROM guest WHERE id = ?",
                (guest["id"],),
            )
            row = cur.fetchone()
```
and
```python
                or row["manual_filed_at"]
                or row["submit_state"] != guest["submit_state"]
            ):
                continue
```

**Go anchors** (`go/internal/ubyport/claim.go`):

```go
type ClaimPair struct {
	GuestID     int64
	SubmitState string
	Payload     any
}
```
```go
		var state string
		var archived, manual *string
		err := tx.QueryRow(ctx,
			`SELECT submit_state, archived_at, manual_filed_at FROM guest WHERE id = $1`, p.GuestID,
		).Scan(&state, &archived, &manual)
```
```go
		if truthy(archived) || truthy(manual) || state != p.SubmitState {
			continue
		}
```

Other Go anchors: `collect.go` `type collectStay struct {\n\tdateFrom, dateTo, completed, source string\n}`; `sweep.go` `claimIn = append(claimIn, ClaimPair{GuestID: p.Outcome.ID, SubmitState: state, Payload: p})`; `submit.go` `type BatchPair struct {` (fields `Guest`, `Reservation`, `Outcome`, `Source`).

Compare rule: both sides are normalised so NULL equals "" (Python `x or ""`; Go `COALESCE(x,'')`).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/reporting.py | edit | claim re-read adds stay window and `updated_at` of guest and reservation |
| App/tests/test_claim_recheck_stay.py | create | window moved / updated_at moved / unchanged |
| go/internal/ubyport/submit.go | edit | `BatchPair.Built ClaimBuilt` and the `ClaimBuilt` type |
| go/internal/ubyport/collect.go | edit | read `updated_at` of guest and reservation, fill `Built` |
| go/internal/ubyport/claim.go | edit | `ClaimPair.Built *ClaimBuilt`, recheck in the claim |
| go/internal/ubyport/sweep.go | edit | pass `Built` into `ClaimPair` |
| go/internal/ubyport/claim_test.go | edit | two tests: moved window dropped, unchanged claimed |

No other file may change.

## 4. Steps

**Step 1. Python claim re-read** (`App/app/reporting.py`). Replace the SELECT:

```diff
-                "SELECT submit_state, archived_at, manual_filed_at FROM guest WHERE id = ?",
+                "SELECT g.submit_state, g.archived_at, g.manual_filed_at, g.stay_from, g.stay_to, "
+                "g.updated_at AS g_updated_at, r.date_from, r.date_to, r.updated_at AS r_updated_at "
+                "FROM guest g JOIN reservation r ON r.id = g.reservation_id WHERE g.id = ?",
```
and replace the drop condition:

```diff
                 or row["manual_filed_at"]
                 or row["submit_state"] != guest["submit_state"]
+                # The payload was built from these. A moved stay window or an
+                # edit since then must not be filed under the old values: drop
+                # the pair, the next sweep rebuilds it.
+                or (row["stay_from"] or "") != (guest["stay_from"] or "")
+                or (row["stay_to"] or "") != (guest["stay_to"] or "")
+                or (row["g_updated_at"] or "") != (guest["updated_at"] or "")
+                or (row["date_from"] or "") != (reservation["date_from"] or "")
+                or (row["date_to"] or "") != (reservation["date_to"] or "")
+                or (row["r_updated_at"] or "") != (reservation["updated_at"] or "")
             ):
```
Also change the loop header `for guest, _reservation in pairs:` to `for guest, reservation in pairs:`. Command: `cd App && .venv/bin/python -m pytest tests/test_filed_by_hand.py tests/test_connection_reuse.py -q --tb=short -x 2>&1 | tail -30`. Expected: pass (their pairs come from `SELECT *`, so values are unchanged).

**Step 2. Python tests.** Create `App/tests/test_claim_recheck_stay.py`:

```python
"""1138: the claim drops a guest whose stay window moved after the list was built."""
from __future__ import annotations

from app import db, reporting


def _stay():
    now = db.utcnow()
    apartment_id = db.insert("apartment", {"internal_name": "1138 flat", "created_at": now})
    reservation_id = db.insert("reservation", {
        "apartment_id": apartment_id, "uid": "t1138", "date_from": "2026-12-01",
        "date_to": "2026-12-03", "created_at": now, "updated_at": now,
    })
    guest_id = db.insert("guest", {
        "reservation_id": reservation_id, "stay_from": "2026-12-01", "stay_to": "2026-12-03",
        "created_at": now, "updated_at": now,
    })
    return reservation_id, guest_id


def _pairs(guest_id, reservation_id):
    guest = db.query_one("SELECT * FROM guest WHERE id = ?", (guest_id,))
    reservation = db.query_one("SELECT * FROM reservation WHERE id = ?", (reservation_id,))
    return [(guest, reservation)]


def _claim(pairs):
    token, claimed = reporting.claim_sendable(pairs)
    reporting.release_sendable_claim(token)
    return claimed


def test_unchanged_pair_is_claimed(fresh_db):
    rid, gid = _stay()
    assert len(_claim(_pairs(gid, rid))) == 1


def test_reservation_dates_moved_after_the_list_drops_the_pair(fresh_db):
    rid, gid = _stay()
    pairs = _pairs(gid, rid)
    db.update("reservation", rid, {"date_to": "2026-12-05"})
    assert _claim(pairs) == []
    assert db.query_one("SELECT 1 AS n FROM submission_claim WHERE guest_id = ?", (gid,)) is None


def test_guest_window_moved_after_the_list_drops_the_pair(fresh_db):
    rid, gid = _stay()
    pairs = _pairs(gid, rid)
    db.update("guest", gid, {"stay_from": "2026-12-02"})
    assert _claim(pairs) == []


def test_guest_edit_bumping_updated_at_drops_the_pair(fresh_db):
    rid, gid = _stay()
    pairs = _pairs(gid, rid)
    db.update("guest", gid, {"updated_at": "2099-01-01T00:00:00+00:00"})
    assert _claim(pairs) == []
```
Command: `cd App && .venv/bin/python -m pytest tests/test_claim_recheck_stay.py -q --tb=short -x 2>&1 | tail -30`. Expected: 4 passed. If `fresh_db` is not found, STOP (§8).

**Step 3. Go: carry the built-from values.** In `go/internal/ubyport/submit.go` add after the `BatchPair` struct:

```go
// ClaimBuilt is what a payload was built from. ClaimSendable compares it with
// the rows it re-reads under the lock (NULL counts as empty).
type ClaimBuilt struct {
	StayFrom, StayTo, DateFrom, DateTo, GuestUpdated, ResUpdated string
}
```
and add the field `Built ClaimBuilt` to `BatchPair` after `Source string`. In `collect.go`: (a) `collectStay` becomes `dateFrom, dateTo, completed, source, updated string`; (b) in the reservation query change `COALESCE(source,'')\n\t\t   FROM reservation` to `COALESCE(source,''), COALESCE(updated_at,'')\n\t\t   FROM reservation` and add `, &s.updated` after `&s.source` in that Scan; (c) `collectGuest` gains `updated string` after `stayTo string`; (d) in `LoadGuests` change `g.submitted_at, g.receipt_submission_id\n\t\tFROM guest g` to `g.submitted_at, g.receipt_submission_id, COALESCE(g.updated_at,'')\n\t\tFROM guest g` and add `, &c.updated` after `&c.receiptID` in its Scan; (e) in the `BatchPair{` literal after `Source: st.source,` add:

```go
			Built: ClaimBuilt{StayFrom: c.stayFrom, StayTo: c.stayTo, DateFrom: st.dateFrom,
				DateTo: st.dateTo, GuestUpdated: c.updated, ResUpdated: st.updated},
```
Command: `cd go && go build ./internal/ubyport/ 2>&1 | tail -30`. Expected: no output.

**Step 4. Go: recheck in the claim.** `claim.go`: add `Built *ClaimBuilt` to `ClaimPair` (comment: nil is never claimed, fail closed). Replace the re-read:

```diff
-		var state string
-		var archived, manual *string
+		var state, stayFrom, stayTo, gUpd, dFrom, dTo, rUpd string
+		var archived, manual *string
 		err := tx.QueryRow(ctx,
-			`SELECT submit_state, archived_at, manual_filed_at FROM guest WHERE id = $1`, p.GuestID,
-		).Scan(&state, &archived, &manual)
+			`SELECT g.submit_state, g.archived_at, g.manual_filed_at,
+			        COALESCE(g.stay_from,''), COALESCE(g.stay_to,''), COALESCE(g.updated_at,''),
+			        COALESCE(r.date_from,''), COALESCE(r.date_to,''), COALESCE(r.updated_at,'')
+			   FROM guest g JOIN reservation r ON r.id = g.reservation_id WHERE g.id = $1`, p.GuestID,
+		).Scan(&state, &archived, &manual, &stayFrom, &stayTo, &gUpd, &dFrom, &dTo, &rUpd)
```
and after the existing `if truthy(archived) ... { continue }` block add:

```go
		// No built-from values means the caller cannot prove what it built:
		// fail closed, never claim.
		b := p.Built
		if b == nil || stayFrom != b.StayFrom || stayTo != b.StayTo ||
			gUpd != b.GuestUpdated || dFrom != b.DateFrom || dTo != b.DateTo || rUpd != b.ResUpdated {
			continue
		}
```
Update the doc comment of `ClaimSendable` to add "or whose stay window or updated_at differs from Built". In `sweep.go` change the append to `ClaimPair{GuestID: p.Outcome.ID, SubmitState: state, Payload: p, Built: &built}` with `built := p.Built` declared on the line before it. Command: `cd go && go vet ./internal/ubyport/ 2>&1 | tail -30`. Expected: no output.

**Step 5. Go callers and tests.** The only non-test caller of `ClaimSendable` is `sweep.go` (Step 4); `grep -rn 'ClaimSendable(\|ClaimPair{' go --include=*.go` shows no other. The tests in `claim_test.go` build `ClaimPair` without `Built` and would now claim nothing, so change them (the `builtOf` helper is added below, in the same file):

```diff
 // TestClaimOnlyOnce
-	pairs := []ClaimPair{{GuestID: id, SubmitState: "pending"}}
+	pairs := []ClaimPair{{GuestID: id, SubmitState: "pending", Built: builtOf(t, pool, id)}}

 // TestClaimReplacesStaleLease
-	_, got, err := ClaimSendable(ctx, pool, []ClaimPair{{GuestID: id, SubmitState: "pending"}})
+	_, got, err := ClaimSendable(ctx, pool, []ClaimPair{{GuestID: id, SubmitState: "pending", Built: builtOf(t, pool, id)}})

 // TestClaimSkipsRowsThatMovedOn
-		{GuestID: changed, SubmitState: "sent"}, // row is pending, the list said sent
-		{GuestID: archived, SubmitState: "pending"},
-		{GuestID: filed, SubmitState: "pending"},
+		{GuestID: changed, SubmitState: "sent", Built: builtOf(t, pool, changed)}, // row is pending, the list said sent
+		{GuestID: archived, SubmitState: "pending", Built: builtOf(t, pool, archived)},
+		{GuestID: filed, SubmitState: "pending", Built: builtOf(t, pool, filed)},

 // TestReleaseFreesGuest
-	pairs := []ClaimPair{{GuestID: id, SubmitState: "pending"}}
+	pairs := []ClaimPair{{GuestID: id, SubmitState: "pending", Built: builtOf(t, pool, id)}}
```
Leave the `{GuestID: 9999999, ...}` pair (row gone) as it is. Each `-` line is unique in the file except the `pairs := ...` line, which occurs in `TestClaimOnlyOnce` and `TestReleaseFreesGuest`: edit each by its test. Then append to `claim_test.go`:

```go
func builtOf(t *testing.T, pool *pgxpool.Pool, id int64) *ClaimBuilt {
	t.Helper()
	var b ClaimBuilt
	if err := pool.QueryRow(context.Background(),
		`SELECT COALESCE(g.stay_from,''), COALESCE(g.stay_to,''), COALESCE(g.updated_at,''),
		        COALESCE(r.date_from,''), COALESCE(r.date_to,''), COALESCE(r.updated_at,'')
		   FROM guest g JOIN reservation r ON r.id = g.reservation_id WHERE g.id = $1`, id,
	).Scan(&b.StayFrom, &b.StayTo, &b.GuestUpdated, &b.DateFrom, &b.DateTo, &b.ResUpdated); err != nil {
		t.Fatal(err)
	}
	return &b
}

func TestClaimDropsGuestWhoseWindowMovedAfterBuild(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	id := seedGuest(t, pool)
	pairs := []ClaimPair{{GuestID: id, SubmitState: "pending", Built: builtOf(t, pool, id)}}
	if _, err := pool.Exec(ctx,
		`UPDATE reservation SET date_to = '2026-12-09' WHERE id = (SELECT reservation_id FROM guest WHERE id = $1)`, id); err != nil {
		t.Fatal(err)
	}
	_, got, err := ClaimSendable(ctx, pool, pairs)
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 0 || claimCount(t, pool, id) != 0 {
		t.Fatalf("moved window: claimed %d pairs, %d claim rows", len(got), claimCount(t, pool, id))
	}
}

func TestClaimDropsPairWithoutBuiltValues(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	id := seedGuest(t, pool)
	_, got, err := ClaimSendable(ctx, pool, []ClaimPair{{GuestID: id, SubmitState: "pending"}})
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 0 || claimCount(t, pool, id) != 0 {
		t.Fatalf("nil Built: claimed %d pairs, %d claim rows", len(got), claimCount(t, pool, id))
	}
}

func TestClaimKeepsGuestWhoseBuiltValuesStillMatch(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	id := seedGuest(t, pool)
	tok, got, err := ClaimSendable(ctx, pool,
		[]ClaimPair{{GuestID: id, SubmitState: "pending", Built: builtOf(t, pool, id)}})
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 {
		t.Fatalf("unchanged guest: claimed %d pairs", len(got))
	}
	_ = ReleaseSendableClaim(ctx, pool, tok)
}
```
Command: `cd go && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ubyport/ -count=1 -run 'Claim' -v 2>&1 | tail -30`. Expected: the three new tests and the four edited ones print `--- PASS`, none `SKIP`. Then the whole package: `cd go && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ubyport/ -count=1 2>&1 | tail -30` expects `ok`. If a parity or JSON test fails on the new `Built` field, STOP (§8).

**Step 6. Gates.** Run, from `App/`: `.venv/bin/python -m pytest tests/test_ubyport_*.py tests/test_submission_*.py tests/test_stale_submission.py tests/test_filed_by_hand.py tests/test_claim_*.py tests/test_connection_reuse.py tests/test_zz_review.py tests/test_sm_go_parity.py tests/test_sm_guest_submit_state.py tests/test_sm_submission_state.py -q --tb=short -x 2>&1 | tail -30` (expected: all pass, 0 skipped except existing markers), then from the repo root `python3 scripts/context_lint.py 2>&1 | tail -3` (expected: OK). If the glob list is too slow, run the files in groups; at most two failures to fix, then §8.

## 5. Do not touch

`App/app/icalsync.py`, `go/internal/ical/`, `billing*`, `door_codes.py` (other briefs). No schema change, no migration, no new dependency, no new outbound request, no new personal-data field. Hard rules 1 (filing correctness), 3, 5 (SQL stays Postgres-portable: plain JOIN and COALESCE), 8 (never push to `main`).

## 6. Commands

As in each step. Python tests from `App/`, Go tests from `go/` with the Postgres URL (must PASS, not SKIP). Never the full suite.

## 7. Acceptance

- [ ] `grep -n "stay_from" App/app/reporting.py` shows the new compare inside `claim_sendable`.
- [ ] `test_claim_recheck_stay.py`: 4 passed.
- [ ] Go: the three new tests PASS (not SKIP; nil `Built` is not claimed), package `ok`.
- [ ] `grep -rn 'ClaimPair{' go --include=*.go` shows `Built:` on every pair except the gone-row and nil-Built test pairs.
- [ ] Step 6 test-map row, the three `test_sm_*` files green.
- [ ] `python3 scripts/context_lint.py 2>&1 | tail -3` = OK.
- [ ] `git diff --stat` lists only §3 files (plus this brief's report).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- the Go `Built` field breaks a parity or JSON test;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1138-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

`App/app/reporting.py` (`claim_sendable` diff), `go/internal/ubyport/claim.go`, `go/internal/ubyport/collect.go` (the extra columns and the `Built` fill), `go/internal/ubyport/sweep.go`.

## Owner steps

1. Review the PR diff of the four files above.
2. Merge with `scripts/merge-pr-on-green.sh` once CI is green; it deploys automatically.
