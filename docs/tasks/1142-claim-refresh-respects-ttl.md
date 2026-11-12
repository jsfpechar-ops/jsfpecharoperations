# 1142: the claim refresh must respect the TTL and cover every guest

Status: todo
Depends on: 1140b | Base commit: HEAD of branch claude/clever-fermi-tudhnt (PR #933) | Branch: task/1142-claim-refresh-respects-ttl
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

HIGH RISK filing path: the reviewer reads every diff line in the Risk list. Fixes a hole in 1140b found by an independent review. Python and Go change together.

## 1. Objective

Make the per-batch claim refresh (1140b) refuse a claim that already went stale, and treat a claim that lost any of its guest rows as lost, in Python and Go. Today a refresh keyed only by the token can revive a stale claim after the iCal guards moved the reservation, and batch 2 is then sent from in-memory pairs built on the old dates. Plus one nit: a silent `now` fallback in `syncfeed.go`.

## 2. Context

Rules: UBYPORT_CORE filing correctness beats everything. The live cutoff everywhere is `claimed_at >= time.time() - SUBMISSION_CLAIM_TTL_SECONDS` (Python `reporting.py` 2089, 2536) / `claimed_at >= epochSeconds() - SubmissionClaimTTL.Seconds()` (Go `liveClaimAfter`, `reconcile.go` 105). `claim_sendable` / `ClaimSendable` delete `claimed_at < cutoff` rows, so live means `>=` cutoff. Use exactly that.

The bug: if batch 1 stalls past 5 minutes the claim is stale but its rows remain (only `claim_sendable` deletes them). The iCal guard sees no live claim, moves the reservation and fits batch-2 guests' windows. Then the refresh matches the stale rows by token alone, revives them, and batch 2 is sent from pairs built on OLD dates (`submit_batch` does not re-read).

Fix: the refresh UPDATE adds `AND claimed_at >= cutoff`, and the sender requires the renewed row count to equal the number of guests in this claim (one `submission_claim` row per guest). Anything else is "claim lost": log, send no further batch (the `finally` / `defer` release stays).

Current Python (`App/app/reporting.py` 1711-1727):
```python
def refresh_sendable_claim(token: str) -> bool:
    """Renew the lease of a claim this worker still holds; False when it is gone.

    One UPDATE keyed by the claim token: a released or taken-over claim matches
    no row, so it is never resurrected. Called before each batch of a long send
    so the date-move and cancel guards and ``claim_sendable`` keep seeing it as
    live (the TTL is 5 minutes, one batch can take 60 s).
    """
    return (
        db.execute(
            "UPDATE submission_claim SET claimed_at = ? WHERE claim_token = ?",
            (time.time(), token),
        )
        > 0
    )
```
Current Go (`go/internal/ubyport/claim.go` 127-138) and `sendClaimedBatches` loop (`sweep.go` 364-374) are quoted in the steps. Test helpers: Python `fresh_db`, `_stay()` -> `(reservation_id, guest_id)`, `_pairs(guest_id, reservation_id)`; Go `claimTestPool(t)`, `seedGuest(t, pool) int64`, `builtOf(t, pool, id)`, `claimCount(t, pool, id)`, `claimedAt(t, pool, id)`, `nowSeconds()`.

The two existing tests that pretend a batch took ten minutes (`- 600`) would now correctly see a stale claim. Step 2 and step 4 change them to `- 240` (still live, under the 300 s TTL, so the refresh renews it).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/reporting.py | edit | `refresh_sendable_claim(token, expected)` with the TTL filter; `_send_claimed_batches` passes the guest count |
| App/tests/test_claim_recheck_stay.py | edit | adjust 3 existing spots, append 2 tests |
| go/internal/ubyport/claim.go | edit | TTL filter in `RefreshSendableClaim` |
| go/internal/ubyport/sweep.go | edit | `sendClaimedBatches` takes `want`; call site counts guests |
| go/internal/ubyport/claim_test.go | edit | adjust existing spots, append 2 tests |
| go/internal/ical/syncfeed.go | edit | nit only: error when `updated_at` is not a string |
| docs/tasks/1142-claim-refresh-respects-ttl.md | status | set `review` at the end |
| docs/tasks/1142-report.md | create | report |

No other file may change. Do NOT touch icalsync.py, reconcile.go, door_codes.py, billing*, migrations.

## 4. Steps

**Step 1. Python fix (`App/app/reporting.py`).** Anchors, each must print `1`:
`cd /home/user/jsfpecharoperations/App && grep -c "^def refresh_sendable_claim(token: str) -> bool:" app/reporting.py && grep -c "        if not refresh_sendable_claim(claim_token):" app/reporting.py && grep -c "    limit = config.UBYPORT_MAX_BATCH" app/reporting.py`
1a. Edit: old_string
```
def refresh_sendable_claim(token: str) -> bool:
    """Renew the lease of a claim this worker still holds; False when it is gone.

    One UPDATE keyed by the claim token: a released or taken-over claim matches
    no row, so it is never resurrected. Called before each batch of a long send
    so the date-move and cancel guards and ``claim_sendable`` keep seeing it as
    live (the TTL is 5 minutes, one batch can take 60 s).
    """
    return (
        db.execute(
            "UPDATE submission_claim SET claimed_at = ? WHERE claim_token = ?",
            (time.time(), token),
        )
        > 0
    )
```
new_string:
```
def refresh_sendable_claim(token: str, expected: int) -> bool:
    """Renew a claim this worker still holds; False when it is lost.

    One UPDATE keyed by the claim token AND the live cutoff the guards and
    ``claim_sendable`` use (``claimed_at >= now - TTL``): a stale claim is not
    revived, because by then the iCal guard may have moved the reservation and
    the in-memory pairs are out of date. It is renewed only when every one of
    its ``expected`` guest rows was renewed; a released, taken-over, stale or
    partly deleted claim is lost. Called before each batch of a long send.
    """
    now = time.time()
    renewed = db.execute(
        "UPDATE submission_claim SET claimed_at = ? "
        "WHERE claim_token = ? AND claimed_at >= ?",
        (now, token, now - SUBMISSION_CLAIM_TTL_SECONDS),
    )
    return renewed == expected
```
1b. Edit: old_string
```
    limit = config.UBYPORT_MAX_BATCH
    results: List[Dict[str, Any]] = []
    for start in range(0, len(pairs), limit):
        if not refresh_sendable_claim(claim_token):
```
new_string:
```
    limit = config.UBYPORT_MAX_BATCH
    results: List[Dict[str, Any]] = []
    guest_count = len({pair[0]["id"] for pair in pairs})
    for start in range(0, len(pairs), limit):
        if not refresh_sendable_claim(claim_token, guest_count):
```
Check: `cd /home/user/jsfpecharoperations/App && .venv/bin/python -c "import app.reporting" 2>&1 | tail -5` expect no output. (The tests of the next step will fail until step 2; that is expected.)

**Step 2. Python tests (`App/tests/test_claim_recheck_stay.py`).** Anchors, each must print `1`:
`cd /home/user/jsfpecharoperations/App && grep -c "claimed_at = claimed_at - 600 " tests/test_claim_recheck_stay.py && grep -c "assert reporting.refresh_sendable_claim(token) is False" tests/test_claim_recheck_stay.py && grep -c "assert reporting.refresh_sendable_claim(other_token) is True" tests/test_claim_recheck_stay.py && grep -c "# Pretend this batch took ten minutes." tests/test_claim_recheck_stay.py`
2a. Edit: old_string `        # Pretend this batch took ten minutes.` new_string `        # Pretend this batch took four minutes (still inside the 5 minute TTL).`
2b. Edit: old_string `            "UPDATE submission_claim SET claimed_at = claimed_at - 600 "` new_string `            "UPDATE submission_claim SET claimed_at = claimed_at - 240 "`
2c. Edit: old_string `    assert reporting.refresh_sendable_claim(token) is False` new_string `    assert reporting.refresh_sendable_claim(token, 1) is False`
2d. Edit: old_string `    assert reporting.refresh_sendable_claim(other_token) is True` new_string `    assert reporting.refresh_sendable_claim(other_token, 1) is True`
2e. Append at the end of the file:
```python


def test_an_expired_claim_is_not_refreshed_and_no_batch_is_sent(fresh_db, monkeypatch):
    """Rows of a stale claim are still there; refreshing must not revive them."""
    rid, gid = _stay()
    token, claimed = reporting.claim_sendable(_pairs(gid, rid))
    stale = time.time() - reporting.SUBMISSION_CLAIM_TTL_SECONDS - 5
    db.execute(
        "UPDATE submission_claim SET claimed_at = ? WHERE claim_token = ?",
        (stale, token),
    )
    calls = []
    monkeypatch.setattr(
        reporting, "submit_batch", lambda *args, **kwargs: calls.append(1) or {}
    )
    monkeypatch.setattr(config, "UBYPORT_MAX_BATCH", 1)

    assert reporting.refresh_sendable_claim(token, 1) is False
    assert reporting._send_claimed_batches(
        {"id": 1}, claimed * 2, token, mode="auto", env=None
    ) == []

    assert calls == []
    row = db.query_one(
        "SELECT claimed_at FROM submission_claim WHERE claim_token = ?", (token,)
    )
    assert row["claimed_at"] == stale
    reporting.release_sendable_claim(token)


def test_a_claim_missing_one_guest_row_is_treated_as_lost(fresh_db, monkeypatch):
    rid, gid = _stay()
    token, claimed = reporting.claim_sendable(_pairs(gid, rid))
    # Two guests in this claim, but only one row exists (the other was deleted).
    two_guests = claimed + [({"id": gid + 1000}, claimed[0][1])]
    calls = []
    monkeypatch.setattr(
        reporting, "submit_batch", lambda *args, **kwargs: calls.append(1) or {}
    )
    monkeypatch.setattr(config, "UBYPORT_MAX_BATCH", 1)

    assert reporting.refresh_sendable_claim(token, 2) is False
    assert reporting._send_claimed_batches(
        {"id": 1}, two_guests, token, mode="auto", env=None
    ) == []

    assert calls == []
    reporting.release_sendable_claim(token)
```
Command: `cd /home/user/jsfpecharoperations/App && .venv/bin/python -m pytest tests/test_claim_recheck_stay.py -q --tb=short 2>&1 | tail -30` expect `9 passed`.
Revert-bite (restore each after): (a) in `refresh_sendable_claim` replace the line `"WHERE claim_token = ? AND claimed_at >= ?",` with `"WHERE claim_token = ? AND (claimed_at >= ? OR 1 = 1)",` -> `test_an_expired_claim_is_not_refreshed_and_no_batch_is_sent` must FAIL; (b) change `return renewed == expected` to `return renewed > 0` -> `test_a_claim_missing_one_guest_row_is_treated_as_lost` must FAIL. Restore, re-run: `9 passed`. Record both outcomes for the report.

**Step 3. Go fix.** Anchors, each must print `1`:
`cd /home/user/jsfpecharoperations/go && grep -c 'UPDATE submission_claim SET claimed_at = \$1 WHERE claim_token = \$2`, nowSeconds(), token)' internal/ubyport/claim.go && grep -c "		if n == 0 {" internal/ubyport/sweep.go && grep -c "^func sendClaimedBatches(ctx context.Context, pool \*pgxpool.Pool, token string, batch \[\]BatchPair, maxBatch int" internal/ubyport/sweep.go && grep -c "	maxBatch := d.MaxBatch" internal/ubyport/sweep.go`
3a. `claim.go`: old_string
```
// RefreshSendableClaim renews the lease of the claim that carries token and
// returns how many rows it renewed. One UPDATE keyed by the token, so a
// released or taken-over claim matches nothing and is never resurrected.
// Python: refresh_sendable_claim.
func RefreshSendableClaim(ctx context.Context, pool *pgxpool.Pool, token string) (int64, error) {
	tag, err := pool.Exec(ctx,
		`UPDATE submission_claim SET claimed_at = $1 WHERE claim_token = $2`, nowSeconds(), token)
```
new_string:
```
// RefreshSendableClaim renews the lease of the claim that carries token and
// returns how many rows it renewed. One UPDATE keyed by the token and the live
// cutoff (claimed_at >= now - SubmissionClaimTTL, the one ClaimSendable and the
// iCal guards use), so a released, taken-over or stale claim matches nothing and
// is never revived. The caller compares the count with the guests it claimed.
// Python: refresh_sendable_claim.
func RefreshSendableClaim(ctx context.Context, pool *pgxpool.Pool, token string) (int64, error) {
	now := nowSeconds()
	tag, err := pool.Exec(ctx,
		`UPDATE submission_claim SET claimed_at = $1 WHERE claim_token = $2 AND claimed_at >= $3`,
		now, token, now-SubmissionClaimTTL.Seconds())
```
3b. `sweep.go`: old_string
```
func sendClaimedBatches(ctx context.Context, pool *pgxpool.Pool, token string, batch []BatchPair, maxBatch int, send func([]BatchPair) (BatchResult, error)) ([]BatchResult, error) {
```
new_string
```
func sendClaimedBatches(ctx context.Context, pool *pgxpool.Pool, token string, want int64, batch []BatchPair, maxBatch int, send func([]BatchPair) (BatchResult, error)) ([]BatchResult, error) {
```
and old_string `		if n == 0 {` new_string `		if n != want {` (in that function only; it is the only match). Also change the doc comment line `// renewing the claim before each chunk. A lost claim (released, or taken over` to `// renewing the claim before each chunk. A lost claim (released, stale, partly deleted, or taken over` .
3c. `sweep.go` call site: old_string
```
	maxBatch := d.MaxBatch
```
new_string
```
	guests := make(map[int64]struct{}, len(kept))
	for _, k := range kept {
		guests[k.GuestID] = struct{}{}
	}
	maxBatch := d.MaxBatch
```
and old_string `	return sendClaimedBatches(ctx, pool, token, batch, maxBatch, func(chunk []BatchPair) (BatchResult, error) {` new_string `	return sendClaimedBatches(ctx, pool, token, int64(len(guests)), batch, maxBatch, func(chunk []BatchPair) (BatchResult, error) {`.
Check: `cd /home/user/jsfpecharoperations/go && go build ./internal/ubyport/ 2>&1 | tail -10` expect no output (test file does not compile until step 4; do not run `go vet` yet).

**Step 4. Go tests (`go/internal/ubyport/claim_test.go`).** Anchors:
`cd /home/user/jsfpecharoperations/go && grep -c "claimed_at = claimed_at - 600 WHERE guest_id = \$1" internal/ubyport/claim_test.go && grep -c "sendClaimedBatches(ctx, pool, tok, " internal/ubyport/claim_test.go` expect `2` and `2`.
4a. Replace ALL occurrences (two) of `claimed_at = claimed_at - 600 WHERE guest_id = $1` with `claimed_at = claimed_at - 240 WHERE guest_id = $1`, and the comment `// Pretend this batch took ten minutes.` with `// Pretend this batch took four minutes (still inside the 5 minute TTL).` (use `sed -i`, then `grep -c "claimed_at - 240" internal/ubyport/claim_test.go` must print `2`).
4b. Edit: old_string `	results, err := sendClaimedBatches(ctx, pool, tok, make([]BatchPair, 3), 1, send)` new_string `	results, err := sendClaimedBatches(ctx, pool, tok, 1, make([]BatchPair, 3), 1, send)`.
4c. Edit: old_string `	results, err = sendClaimedBatches(ctx, pool, tok, make([]BatchPair, 2), 1,` new_string `	results, err = sendClaimedBatches(ctx, pool, tok, 1, make([]BatchPair, 2), 1,`.
4d. Append to the end of the file:
```go

func TestExpiredClaimIsNotRefreshedAndNoBatchIsSent(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	id := seedGuest(t, pool)
	pairs := []ClaimPair{{GuestID: id, SubmitState: "pending", Built: builtOf(t, pool, id)}}
	tok, _, err := ClaimSendable(ctx, pool, pairs)
	if err != nil {
		t.Fatal(err)
	}
	stale := nowSeconds() - SubmissionClaimTTL.Seconds() - 5
	if _, err := pool.Exec(ctx, `UPDATE submission_claim SET claimed_at = $1 WHERE guest_id = $2`, stale, id); err != nil {
		t.Fatal(err)
	}
	if n, err := RefreshSendableClaim(ctx, pool, tok); err != nil || n != 0 {
		t.Fatalf("refresh of an expired claim: %d, %v", n, err)
	}
	called := 0
	results, err := sendClaimedBatches(ctx, pool, tok, 1, make([]BatchPair, 2), 1,
		func([]BatchPair) (BatchResult, error) { called++; return BatchResult{}, nil })
	if err != nil || len(results) != 0 || called != 0 {
		t.Fatalf("expired claim: results %d, called %d, err %v", len(results), called, err)
	}
	if got := claimedAt(t, pool, id); got != stale {
		t.Fatalf("expired claim was revived: claimed_at %.0f, want %.0f", got, stale)
	}
}

func TestClaimMissingOneGuestRowIsTreatedAsLost(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	a := seedGuest(t, pool)
	b := seedGuest(t, pool)
	pairs := []ClaimPair{
		{GuestID: a, SubmitState: "pending", Built: builtOf(t, pool, a)},
		{GuestID: b, SubmitState: "pending", Built: builtOf(t, pool, b)},
	}
	tok, got, err := ClaimSendable(ctx, pool, pairs)
	if err != nil || len(got) != 2 {
		t.Fatalf("claim: %v, %d pairs", err, len(got))
	}
	if _, err := pool.Exec(ctx, `DELETE FROM submission_claim WHERE guest_id = $1`, b); err != nil {
		t.Fatal(err)
	}
	called := 0
	results, err := sendClaimedBatches(ctx, pool, tok, 2, make([]BatchPair, 2), 1,
		func([]BatchPair) (BatchResult, error) { called++; return BatchResult{}, nil })
	if err != nil || len(results) != 0 || called != 0 {
		t.Fatalf("partly missing claim: results %d, called %d, err %v", len(results), called, err)
	}
	if err := ReleaseSendableClaim(ctx, pool, tok); err != nil {
		t.Fatal(err)
	}
}
```
Command: `cd /home/user/jsfpecharoperations/go && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ubyport/ -run 'Refresh|SendClaimedBatches|Claim' -count=1 -v 2>&1 | tail -30` expect all `--- PASS`, `ok`.
Revert-bite (restore each after): (a) in `claim.go` replace ` AND claimed_at >= $3` with ` AND $3 >= 0` -> `TestExpiredClaimIsNotRefreshedAndNoBatchIsSent` must FAIL; (b) in `sweep.go` change `if n != want {` to `if n == 0 {` -> `TestClaimMissingOneGuestRowIsTreatedAsLost` must FAIL. Restore, re-run: PASS. Record both.

**Step 5. Nit (`go/internal/ical/syncfeed.go`).** Anchor must print `1`: `cd /home/user/jsfpecharoperations/go && grep -c '			now, _ := cols\["updated_at"\].(string)' internal/ical/syncfeed.go`
Edit (one line): old_string `			now, _ := cols["updated_at"].(string)`, new_string:
```
			now, ok := cols["updated_at"].(string)
			if !ok || now == "" {
				return false, fmt.Errorf("updateReservationUnlessClaimed: cols[updated_at] must be a non-empty string, got %T", cols["updated_at"])
			}
```
The error rolls the transaction back (deferred `tx.Rollback`). Check: `cd /home/user/jsfpecharoperations/go && go build ./internal/ical/ 2>&1 | tail -10` expect no output. If `ok` is already declared in that scope and the build says "no new variables", STOP (section 8). Existing callers with a `move` already pass `updated_at` (syncfeed_test.go 478, 518; the sync call site sets `changed["updated_at"] = now`), so no test change is needed.

**Step 6. Verify, report, lint.** Run each, all must pass:
1. `cd /home/user/jsfpecharoperations/App && .venv/bin/python -m pytest tests/test_claim_recheck_stay.py tests/test_icalsync.py tests/test_sm_*.py tests/test_ubyport_*.py tests/test_soap.py tests/test_worker.py tests/test_submission_*.py tests/test_stale_submission.py tests/test_filed_by_hand.py tests/test_filing_watchdog.py tests/test_police_*.py tests/test_deadline*.py tests/test_claim_*.py tests/test_endtoend.py -q --tb=short 2>&1 | tail -30` expect all passed.
2. `cd /home/user/jsfpecharoperations/go && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ical/ ./internal/ubyport/ -count=1 2>&1 | tail -30` expect two `ok` lines; also run the same with `-v 2>&1 | grep -c SKIP` expect `0`.
3. `cd /home/user/jsfpecharoperations/go && go vet ./internal/ical/ ./internal/ubyport/ 2>&1 | tail -10` expect no output; `gofmt -l internal 2>&1 | tail -10` expect no output.
4. Write `docs/tasks/1142-report.md` (section 9) and set `Status: review` in this brief.
5. `cd /home/user/jsfpecharoperations && python3 scripts/context_lint.py 2>&1 | tail -3` expect `context lint: OK` (a WARN about status.md is fine; do not edit status.md).

## 5. Do not touch

Paths outside section 3. Hard rules: UbyPort filing correctness first; SQL only through `db.py` helpers (Python) and Postgres-portable; no new dependency, no schema change, no new outbound request; never push to `main`; no push, merge or deploy (owner). Do not change `SUBMISSION_CLAIM_TTL_SECONDS` / `SubmissionClaimTTL`, `claim_sendable`, `ClaimSendable`, or the iCal guards.

## 6. Commands

Exactly those in steps 1-6. Python from `App/` (`.venv/bin/python -m pytest ... 2>&1 | tail -30`), Go from `go/` with `UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest`. Never the full suite.

## 7. Acceptance

- [ ] `grep -c "claimed_at >= ?" App/app/reporting.py` shows the refresh UPDATE carries the cutoff; `grep -n "claimed_at >= \$3" go/internal/ubyport/claim.go` shows 1 match
- [ ] Two new Python tests and two new Go tests pass, 0 SKIP
- [ ] All four revert-bite checks failed as stated and were restored
- [ ] An expired claim is neither refreshed nor sent; a claim missing a guest row stops the send (Python and Go)
- [ ] `go vet` and `gofmt -l` clean; `test_sm_*` and the claim rows of the test-map green; context lint OK
- [ ] `syncfeed.go` no longer discards the type assertion result

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt or anchor is not found, or a `grep -c` does not print the stated number;
- a test fails twice, or a revert-bite does NOT fail;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change (including `syncfeed_test.go` after step 5);
- section 5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1142-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. Section 7 ticked.
4. Revert-bite outcomes (four).
5. Deviations.
6. Questions.
7. Owner steps left.

## Risk list (for the reviewer)

- `App/app/reporting.py`: `refresh_sendable_claim` (cutoff and exact-count rule), `_send_claimed_batches` guest count.
- `go/internal/ubyport/claim.go`: `RefreshSendableClaim` cutoff arithmetic equals `ClaimSendable`'s.
- `go/internal/ubyport/sweep.go`: `want` (distinct claimed guests) and the `n != want` stop.
- `go/internal/ical/syncfeed.go`: the new error path rolls back the transaction.
- The `- 600` to `- 240` test edits (they must stay inside the TTL).

## Owner steps

1. Review the PR diff for the five files above.
2. Merge with `scripts/merge-pr-on-green.sh` once CI is green.
