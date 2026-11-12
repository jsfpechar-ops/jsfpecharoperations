# 1147: claim-refresh TTL boundary test and a real missing-row test

Status: todo
Depends on: 1144 | Base commit: HEAD of the branch after 1144 is merged (1144 makes Go `nowSeconds` a var; do not start before that) | Branch: task/1147-claim-ttl-nits
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

Test-only. No app code changes (the revert-bite edits are temporary and restored). HIGH RISK area (filing path), but the diff is three tests in two files.

## 1. Objective

Two review nits on 1142: (1) pin the exact TTL boundary of `refresh_sendable_claim` (Python, `App/tests/test_claim_recheck_stay.py`) and of `RefreshSendableClaim` (Go, `go/internal/ubyport/claim_test.go`) with a frozen clock; (2) in the Python file, make the "missing guest row" test delete a real claim row of a real second guest instead of faking a guest id (`gid + 1000`).

## 2. Context

Boundary evidence. The refresh keeps a claim live when `claimed_at >= now - TTL` (inclusive), the same cutoff as `claim_sendable`, which deletes only `claimed_at < cutoff`:
- `App/app/reporting.py:1726-1727`: `"WHERE claim_token = ? AND claimed_at >= ?",` / `(now, token, now - SUBMISSION_CLAIM_TTL_SECONDS),` with `now = time.time()` at line 1723.
- `App/app/reporting.py:1666-1667`: `"DELETE FROM submission_claim WHERE claimed_at < ?",` / `(time.time() - SUBMISSION_CLAIM_TTL_SECONDS,),`.
- `SUBMISSION_CLAIM_TTL_SECONDS = 5 * 60` (line 97).

Expected: a claim with `claimed_at == now - TTL` exactly is still live (refresh returns True, `claimed_at` becomes `now`); one with `claimed_at == now - TTL - 0.001` is stale (refresh returns False, row unchanged).

Clock: the 1142 tests do not freeze time; they shift `claimed_at` with SQL. A boundary needs an exact `now`, so this brief patches `time.time` with `monkeypatch.setattr(reporting.time, "time", lambda: NOW)` AFTER the claim is taken (the claim itself uses the real clock). `NOW = 1_900_000_000.0` and the TTL (300) are exactly representable doubles, so `NOW - 300` is exact in Python and SQLite REAL.

Go: after 1144, `go/internal/ubyport/claim.go` reads
```go
var nowSeconds = func() float64 {
	return float64(time.Now().UnixNano()) / 1e9
}
```
and `RefreshSendableClaim` (about claim.go:133-137) has `now := nowSeconds()` and `` `UPDATE submission_claim SET claimed_at = $1 WHERE claim_token = $2 AND claimed_at >= $3`, now, token, now-SubmissionClaimTTL.Seconds()) ``. The test swaps `nowSeconds` the way 1144's test does (`real := nowSeconds` ... `t.Cleanup(func() { nowSeconds = real })`). If `var nowSeconds` is not there, STOP (1144 has not landed). Helpers in claim_test.go: `claimTestPool(t)`, `seedGuest(t, pool)`, `builtOf(t, pool, id)`, `claimedAt(t, pool, id)`. Go tests need `UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest`; a skipped test does NOT count as passing.

Current test to change (`App/tests/test_claim_recheck_stay.py`, end of file):
```python
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
What the case means: a claim covers N guests (one `submission_claim` row each); if one row is gone (released or stolen), the refresh renews fewer rows than `expected` and the send stops. The fake guest never had a row, so the test never showed a real claim losing a row.

## 3. Files

| Path | Action | What |
|---|---|---|
| App/tests/test_claim_recheck_stay.py | edit | replace one test, append one test |
| go/internal/ubyport/claim_test.go | edit | append one boundary test |
| docs/tasks/1147-claim-ttl-test-nits.md | status | set `review` at the end |
| docs/tasks/1147-report.md | create | report |

No other file may change.

## 4. Steps

**Step 1. Anchors.** Each must print `1`:
`cd /home/user/jsfpecharoperations/App && grep -c "^def test_a_claim_missing_one_guest_row_is_treated_as_lost(fresh_db, monkeypatch):" tests/test_claim_recheck_stay.py && grep -c "two_guests = claimed + \[({\"id\": gid + 1000}, claimed\[0\]\[1\])\]" tests/test_claim_recheck_stay.py && grep -c '"WHERE claim_token = ? AND claimed_at >= ?",' app/reporting.py 2>&1 | tail -30`
If any is not `1`, STOP.

**Step 2. Replace the missing-row test.** Edit `App/tests/test_claim_recheck_stay.py`: old_string
```
    rid, gid = _stay()
    token, claimed = reporting.claim_sendable(_pairs(gid, rid))
    # Two guests in this claim, but only one row exists (the other was deleted).
    two_guests = claimed + [({"id": gid + 1000}, claimed[0][1])]
    calls = []
```
new_string
```
    rid, gid = _stay()
    now = db.utcnow()
    gid2 = db.insert("guest", {
        "reservation_id": rid, "stay_from": "2026-12-01", "stay_to": "2026-12-03",
        "created_at": now, "updated_at": now,
    })
    two_guests = _pairs(gid, rid) + _pairs(gid2, rid)
    token, claimed = reporting.claim_sendable(two_guests)
    assert len(claimed) == 2
    # Lose one real claim row (as if another worker released or took it over).
    db.execute("DELETE FROM submission_claim WHERE guest_id = ?", (gid2,))
    calls = []
```
Then edit: old_string `        {"id": 1}, two_guests, token, mode="auto", env=None` new_string `        {"id": 1}, claimed, token, mode="auto", env=None`.
Command: `cd /home/user/jsfpecharoperations/App && .venv/bin/python -m pytest tests/test_claim_recheck_stay.py -q --tb=short -x 2>&1 | tail -30` expect `9 passed`.

**Step 3. Append the boundary test** at the end of `App/tests/test_claim_recheck_stay.py` (two blank lines before it):
```python
def test_refresh_boundary_is_inclusive_at_exactly_the_ttl(fresh_db, monkeypatch):
    """claimed_at == now - TTL is still live; one millisecond older is stale."""
    rid, gid = _stay()
    token, _claimed = reporting.claim_sendable(_pairs(gid, rid))
    now = 1_900_000_000.0
    monkeypatch.setattr(reporting.time, "time", lambda: now)
    cutoff = now - reporting.SUBMISSION_CLAIM_TTL_SECONDS

    db.execute("UPDATE submission_claim SET claimed_at = ? WHERE claim_token = ?", (cutoff, token))
    assert reporting.refresh_sendable_claim(token, 1) is True
    row = db.query_one("SELECT claimed_at FROM submission_claim WHERE claim_token = ?", (token,))
    assert row["claimed_at"] == now

    stale = cutoff - 0.001
    db.execute("UPDATE submission_claim SET claimed_at = ? WHERE claim_token = ?", (stale, token))
    assert reporting.refresh_sendable_claim(token, 1) is False
    row = db.query_one("SELECT claimed_at FROM submission_claim WHERE claim_token = ?", (token,))
    assert row["claimed_at"] == stale
    reporting.release_sendable_claim(token)
```
Command: `cd /home/user/jsfpecharoperations/App && .venv/bin/python -m pytest tests/test_claim_recheck_stay.py -q --tb=short -x 2>&1 | tail -30` expect `10 passed`. If the boundary test fails on a patched-clock side effect, STOP (do not change app code).

**Step 4. Revert-bite (boundary).** Temporarily edit `App/app/reporting.py`: old_string `"WHERE claim_token = ? AND claimed_at >= ?",` new_string `"WHERE claim_token = ? AND claimed_at > ?",`. Run:
`cd /home/user/jsfpecharoperations/App && .venv/bin/python -m pytest tests/test_claim_recheck_stay.py -q --tb=short 2>&1 | tail -30` expect exactly `test_refresh_boundary_is_inclusive_at_exactly_the_ttl` FAILED (`assert False is True`), the rest passed. Restore the line to `>=` (undo with the reverse edit), then `cd /home/user/jsfpecharoperations && git diff --stat -- App/app 2>&1 | tail -30` must print nothing.

**Step 5. Revert-bite (missing row).** Temporarily edit `App/app/reporting.py`: old_string `    return renewed == expected` new_string `    return renewed > 0`. Run the same pytest command; expect `test_a_claim_missing_one_guest_row_is_treated_as_lost` FAILED, the rest passed. Restore, then `git diff --stat -- App/app 2>&1 | tail -30` prints nothing.

**Step 6. Go boundary test.** Anchors, each must print `1` (`cd /home/user/jsfpecharoperations/go`): `grep -c "^var nowSeconds = func() float64 {" internal/ubyport/claim.go` and `` grep -c 'WHERE claim_token = \$2 AND claimed_at >= \$3' internal/ubyport/claim.go ``. Append to `go/internal/ubyport/claim_test.go`:
```go

func TestRefreshBoundaryIsInclusiveAtExactlyTheTTL(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	id := seedGuest(t, pool)
	pairs := []ClaimPair{{GuestID: id, SubmitState: "pending", Built: builtOf(t, pool, id)}}
	tok, _, err := ClaimSendable(ctx, pool, pairs)
	if err != nil {
		t.Fatal(err)
	}
	const now = 1_900_000_000.0
	real := nowSeconds
	nowSeconds = func() float64 { return now }
	t.Cleanup(func() { nowSeconds = real })
	cutoff := now - SubmissionClaimTTL.Seconds()

	if _, err := pool.Exec(ctx, `UPDATE submission_claim SET claimed_at = $1 WHERE guest_id = $2`, cutoff, id); err != nil {
		t.Fatal(err)
	}
	if n, err := RefreshSendableClaim(ctx, pool, tok); err != nil || n != 1 {
		t.Fatalf("refresh at exactly the cutoff: %d, %v (want 1)", n, err)
	}
	if got := claimedAt(t, pool, id); got != now {
		t.Fatalf("claimed_at %.3f, want %.3f", got, now)
	}

	stale := cutoff - 0.001
	if _, err := pool.Exec(ctx, `UPDATE submission_claim SET claimed_at = $1 WHERE guest_id = $2`, stale, id); err != nil {
		t.Fatal(err)
	}
	if n, err := RefreshSendableClaim(ctx, pool, tok); err != nil || n != 0 {
		t.Fatalf("refresh 1 ms past the cutoff: %d, %v (want 0)", n, err)
	}
	if got := claimedAt(t, pool, id); got != stale {
		t.Fatalf("stale claim was revived: %.3f, want %.3f", got, stale)
	}
	nowSeconds = real
	if err := ReleaseSendableClaim(ctx, pool, tok); err != nil {
		t.Fatal(err)
	}
}
```
Command: `cd /home/user/jsfpecharoperations/go && gofmt -l internal 2>&1 | tail -30` expect no output; then `cd /home/user/jsfpecharoperations/go && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ubyport/ -run 'TestRefreshBoundary' -count=1 -v 2>&1 | tail -30` expect `--- PASS` and `ok`, no SKIP. (If the column is `REAL` rather than double and the 0.001 step misbehaves, STOP.)

**Step 7. Revert-bite (Go boundary).** Temporarily edit `go/internal/ubyport/claim.go`: old_string `WHERE claim_token = $2 AND claimed_at >= $3` new_string `WHERE claim_token = $2 AND claimed_at > $3`. Run the same `go test -run 'TestRefreshBoundary'` command: expect FAIL with `refresh at exactly the cutoff: 0, <nil> (want 1)`. Restore, then `cd /home/user/jsfpecharoperations && git diff --stat -- go/internal/ubyport/claim.go 2>&1 | tail -30` must print nothing (1144 is already committed), and re-run: PASS.

**Step 8. Final run and lint.**
1. `cd /home/user/jsfpecharoperations/App && .venv/bin/python -m pytest tests/test_claim_recheck_stay.py -q --tb=short -x 2>&1 | tail -30` expect `10 passed`.
2. Postgres: `cd /home/user/jsfpecharoperations/App && UBYHOST_DATABASE_URL=postgresql://uby:uby@localhost:5432/ubytest .venv/bin/python -m pytest tests/test_claim_recheck_stay.py -q --tb=short -x 2>&1 | tail -30` expect `10 passed` (if Postgres is not running, say so in the report; do not start services).
3. `cd /home/user/jsfpecharoperations/go && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ubyport/ -count=1 2>&1 | tail -30` expect `ok`; `go vet ./internal/ubyport/ 2>&1 | tail -10` no output.
4. `cd /home/user/jsfpecharoperations && python3 scripts/context_lint.py 2>&1 | tail -3` expect `context lint: OK` (a status WARN is fine).
5. Write `docs/tasks/1147-report.md`; set `Status: review` in this brief.

## 5. Do not touch

Everything outside section 3, in particular `App/app/` and `go/internal/ubyport/claim.go` (except the temporary, restored edits of steps 4, 5 and 7), `status.md`, `known-issues.md`. Hard rules: no new dependency, no schema change, never push to `main`, no push/merge/deploy.

## 6. Commands

Exactly those in steps 1-8; Python from `App/` with `.venv/bin/python -m pytest ... -q --tb=short -x 2>&1 | tail -30`, Go from `go/`. Test-map: claim tests only. Never the full suite.

## 7. Acceptance

- [ ] `grep -c "gid + 1000" App/tests/test_claim_recheck_stay.py` prints `0`
- [ ] `grep -c "^def test_refresh_boundary_is_inclusive_at_exactly_the_ttl" App/tests/test_claim_recheck_stay.py` prints `1`
- [ ] File: `10 passed`, 0 skipped, on SQLite
- [ ] Go `TestRefreshBoundaryIsInclusiveAtExactlyTheTTL` passes, 0 SKIP
- [ ] All three revert-bite checks failed the named test and were restored; `git diff --stat -- App/app go/internal/ubyport/claim.go` is empty
- [ ] `git diff --stat` lists only the two test files (plus this brief and the report)

## 8. Stop and ask

Stop, and write the report, if:

- an anchor is not found or a `grep -c` does not print `1`;
- a test fails twice, or a revert-bite does NOT fail the named test;
- you reach 25 tool calls or about 50k tokens (report as `blocked`);
- a file outside section 3 needs a change (including any app-code or Go change to get a clock seam);
- you need push, merge, secrets, SSH or deploy (hand to the owner with the exact command).

## 9. Report

Write `docs/tasks/1147-report.md` (600 tokens at most) and set `Status: review`. It has: files changed (`git diff --stat`); each command with its last 5 output lines; section 7 ticked; the three revert-bite outcomes; deviations; questions; owner steps left.

## Risk list (for the reviewer)

- `App/tests/test_claim_recheck_stay.py`: the global `time.time` patch is undone by `monkeypatch`; the second guest is a real row; the boundary is `>=` (inclusive).
- `go/internal/ubyport/claim_test.go`: the fake clock is restored by `t.Cleanup`.
- Confirm `App/app/` and `claim.go` have no diff.

## Owner steps

1. Review the test diff.
2. Merge with `scripts/merge-pr-on-green.sh` once CI is green.
