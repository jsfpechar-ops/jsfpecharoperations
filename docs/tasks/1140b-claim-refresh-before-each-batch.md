# 1140b: renew the submission claim before each batch send

Status: review
Depends on: 1140 | Base commit: 8e512d47 (HEAD of branch claude/clever-fermi-tudhnt, PR #933) | Branch: task/1140b-claim-refresh
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

HIGH RISK filing path: the reviewer reads every diff line in the Risk list. Second half of the pair started by 1140; no file overlap, it only runs after 1140 to keep the order fixed.

## 1. Objective

Keep a submission claim live for the whole multi-batch send: refresh `claimed_at` for the worker's own claim before each batch, in Python and Go, so the iCal date-move and cancel guards (1143/1136/1139) and the claim-steal in `claim_sendable` never see a still-running send as stale. If the claim is gone (released, or taken over), stop sending further batches.

## 2. Context

`SUBMISSION_CLAIM_TTL_SECONDS = 5 * 60` (`App/app/reporting.py` ~97) and Go `SubmissionClaimTTL = 5 * time.Minute` (`go/internal/ubyport/claim.go` ~16). Nothing renews a claim, but `submit_for_apartment` (`reporting.py` ~2285) and Go `SubmitForApartment` (`go/internal/ubyport/sweep.go` ~275) loop over batches under ONE claim, each batch a UbyPort call with `UBYPORT_TIMEOUT` 60 s (`config.py` 313). Past 5 minutes the claim is stale: the date-move and cancel guards (`claimed_at >= now - TTL`) pass mid-send, and another worker's `claim_sendable` deletes the stale rows and claims the same guests.

Fix: before each batch, one UPDATE of `claimed_at` filtered by the claim token: `UPDATE submission_claim SET claimed_at = ? WHERE claim_token = ?`. A UPDATE cannot resurrect a deleted row, so a released or taken-over claim (another worker holds a different token for that guest, or the row is gone) matches 0 rows. A 0-row refresh means the claim is lost: log it and send no further batch (return the results so far; the `finally` / `defer` release stays). The refresh runs also before the first batch (harmless, and it covers a long collect-to-send gap).

To make the loop testable without a UbyPort stub, the batch loop moves into a small helper in both languages: Python `_send_claimed_batches(apartment, pairs, claim_token, *, mode, env)` (calls the module-level `submit_batch`, which tests can monkeypatch); Go `sendClaimedBatches(ctx, pool, token, batch, maxBatch, send)` where `send` is a closure over `SubmitBatch`.

Current Python (`App/app/reporting.py` ~2339-2357):
```python
    claim_token, pairs = claim_sendable(pairs)
    if not pairs:
        return []
    try:
        limit = config.UBYPORT_MAX_BATCH
        results = []
        for start in range(0, len(pairs), limit):
            results.append(
                submit_batch(
                    apartment,
                    pairs[start:start + limit],
                    mode=mode,
                    env=env,
                )
            )
        return results
    finally:
        release_sendable_claim(claim_token)
```
Current Go (`sweep.go` ~351-365):
```go
	sender := d.NewSender(apt)
	var results []BatchResult
	for start := 0; start < len(batch); start += maxBatch {
		end := min(start+maxBatch, len(batch))
		res, err := SubmitBatch(ctx, d.Batch, sender, apt.Apartment, apt.Ref, batch[start:end], mode)
		if err != nil {
			return results, err
		}
		results = append(results, res)
	}
	return results, nil
}
```
`claim_sendable` (Python) / `ClaimSendable` (Go) first delete claims older than the TTL, then claim; `recover_stale_submissions` and the guards read `claimed_at >= now - TTL`. `submission_claim.claimed_at` is `double precision` (Postgres) / a real number (SQLite) holding epoch seconds. No `test_sm_*` pin reads `submission_claim` writes (they pin `guest.submit_state`, `submission.state`, `reservation_claim.state`, queues and TRANSITIONS parity); the final step runs them anyway.

Python test helpers in `App/tests/test_claim_recheck_stay.py`: fixture `fresh_db`, `_stay()` returns `(reservation_id, guest_id)`, `_pairs(guest_id, reservation_id)`. Go test helpers in `go/internal/ubyport/claim_test.go`: `claimTestPool(t)`, `seedGuest(t, pool) int64`, `builtOf(t, pool, id) *ClaimBuilt`, `claimCount(t, pool, id) int`, `nowSeconds()` (in `claim.go`).

## 3. Files

| Path | Action | What |
|---|---|---|
| App/app/reporting.py | edit | `refresh_sendable_claim`, `_send_claimed_batches`, `submit_for_apartment` uses it |
| App/tests/test_claim_recheck_stay.py | edit | append 3 tests |
| go/internal/ubyport/claim.go | edit | `RefreshSendableClaim` |
| go/internal/ubyport/sweep.go | edit | `sendClaimedBatches`, `SubmitForApartment` uses it |
| go/internal/ubyport/claim_test.go | edit | append 2 tests |
| docs/tasks/1140b-claim-refresh-before-each-batch.md | status | set `review` at the end |
| docs/tasks/1140b-report.md | create | report |

No other file may change. Do NOT touch door_codes.py, billing*, icalsync.py, syncfeed.go, reconcile.go.

## 4. Steps

**Step 1. Python.** Anchors, each must print `1`:
`cd /home/user/jsfpecharoperations/App && grep -c "^def release_sendable_claim(token: str) -> None:" app/reporting.py && grep -c "        limit = config.UBYPORT_MAX_BATCH" app/reporting.py && grep -c "^    claim_token, pairs = claim_sendable(pairs)" app/reporting.py`
1a. Edit `App/app/reporting.py`: old_string
```
def release_sendable_claim(token: str) -> None:
    db.execute("DELETE FROM submission_claim WHERE claim_token = ?", (token,))
```
new_string:
```
def release_sendable_claim(token: str) -> None:
    db.execute("DELETE FROM submission_claim WHERE claim_token = ?", (token,))


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


def _send_claimed_batches(
    apartment, pairs: List[Tuple[Any, Any]], claim_token: str, *, mode: str, env: Optional[str]
) -> List[Dict[str, Any]]:
    """Send ``pairs`` in batches under one claim, renewing it before each batch.

    A lost claim (released, or taken over after a stale TTL) stops the send:
    the remaining guests are left for the next sweep.
    """
    limit = config.UBYPORT_MAX_BATCH
    results: List[Dict[str, Any]] = []
    for start in range(0, len(pairs), limit):
        if not refresh_sendable_claim(claim_token):
            log.warning(
                "submission_claim_lost apartment_id=%s sent_batches=%s remaining=%s",
                apartment["id"],
                len(results),
                len(pairs) - start,
            )
            break
        results.append(
            submit_batch(apartment, pairs[start:start + limit], mode=mode, env=env)
        )
    return results
```
1b. Edit: old_string
```
    try:
        limit = config.UBYPORT_MAX_BATCH
        results = []
        for start in range(0, len(pairs), limit):
            results.append(
                submit_batch(
                    apartment,
                    pairs[start:start + limit],
                    mode=mode,
                    env=env,
                )
            )
        return results
    finally:
        release_sendable_claim(claim_token)
```
new_string:
```
    try:
        return _send_claimed_batches(
            apartment, pairs, claim_token, mode=mode, env=env
        )
    finally:
        release_sendable_claim(claim_token)
```
`List`, `Tuple`, `Dict`, `Any`, `Optional` are already imported in `reporting.py` (it already uses them in `claim_sendable`'s signature); confirm with `cd /home/user/jsfpecharoperations/App && grep -n "^from typing import" app/reporting.py | head -2`. Command: `cd /home/user/jsfpecharoperations/App && .venv/bin/python -c "import app.reporting" 2>&1 | tail -3`. Expected: no output.

**Step 2. Python tests.** Append to `App/tests/test_claim_recheck_stay.py` (add `import time` on its own line under `import pytest` if the file has no `import time`):
```python
def test_a_multi_batch_send_keeps_the_claim_live(fresh_db, monkeypatch):
    """Each batch runs under a claim whose claimed_at was just renewed."""
    rid, gid = _stay()
    token, claimed = reporting.claim_sendable(_pairs(gid, rid))
    seen = []

    def fake_batch(apartment, pairs, mode="auto", env=None):
        row = db.query_one(
            "SELECT claimed_at FROM submission_claim WHERE claim_token = ?", (token,)
        )
        seen.append(row["claimed_at"])
        # Pretend this batch took ten minutes.
        db.execute(
            "UPDATE submission_claim SET claimed_at = claimed_at - 600 "
            "WHERE claim_token = ?",
            (token,),
        )
        return {"submitted": 1}

    monkeypatch.setattr(reporting, "submit_batch", fake_batch)
    monkeypatch.setattr(config, "UBYPORT_MAX_BATCH", 1)

    results = reporting._send_claimed_batches(
        {"id": 1}, claimed * 3, token, mode="auto", env=None
    )

    assert len(results) == 3
    floor = time.time() - 60
    assert len(seen) == 3 and all(value >= floor for value in seen)
    reporting.release_sendable_claim(token)


def test_a_lost_claim_stops_the_send_and_is_not_resurrected(fresh_db, monkeypatch):
    rid, gid = _stay()
    token, claimed = reporting.claim_sendable(_pairs(gid, rid))
    calls = []
    monkeypatch.setattr(
        reporting, "submit_batch", lambda *args, **kwargs: calls.append(1) or {}
    )
    monkeypatch.setattr(config, "UBYPORT_MAX_BATCH", 1)
    reporting.release_sendable_claim(token)

    assert reporting._send_claimed_batches(
        {"id": 1}, claimed * 2, token, mode="auto", env=None
    ) == []

    assert calls == []
    assert db.query_one(
        "SELECT 1 AS n FROM submission_claim WHERE guest_id = ?", (gid,)
    ) is None


def test_refresh_does_not_touch_another_workers_claim_and_stale_ones_are_stolen(
    fresh_db,
):
    rid, gid = _stay()
    token, claimed = reporting.claim_sendable(_pairs(gid, rid))
    assert len(claimed) == 1
    # Our claim ages past the TTL; another worker steals the guest.
    db.execute(
        "UPDATE submission_claim SET claimed_at = ? WHERE claim_token = ?",
        (time.time() - reporting.SUBMISSION_CLAIM_TTL_SECONDS - 5, token),
    )
    other_token, stolen = reporting.claim_sendable(_pairs(gid, rid))
    assert len(stolen) == 1
    before = db.query_one(
        "SELECT claimed_at FROM submission_claim WHERE guest_id = ?", (gid,)
    )["claimed_at"]

    assert reporting.refresh_sendable_claim(token) is False

    row = db.query_one(
        "SELECT claim_token, claimed_at FROM submission_claim WHERE guest_id = ?", (gid,)
    )
    assert (row["claim_token"], row["claimed_at"]) == (other_token, before)
    assert reporting.refresh_sendable_claim(other_token) is True
    reporting.release_sendable_claim(other_token)
```
Command: `cd /home/user/jsfpecharoperations/App && .venv/bin/python -m pytest tests/test_claim_recheck_stay.py -q --tb=short -x 2>&1 | tail -30`. Expected: all pass.
Revert-bite checks (restore exactly, rerun green):
- (a) in `_send_claimed_batches` replace `if not refresh_sendable_claim(claim_token):` with `if False and not refresh_sendable_claim(claim_token):`; run `-k "multi_batch"`; expect FAIL (the second and third batch see an aged claim).
- (b) replace `if not refresh_sendable_claim(claim_token):` with `if not (refresh_sendable_claim(claim_token) or True):`; run `-k "lost_claim"`; expect FAIL (batches are still sent).
If (a) or (b) does not fail, STOP.

**Step 3. Go: `RefreshSendableClaim`.** Anchor: `cd /home/user/jsfpecharoperations/go/internal/ubyport && grep -c "^func ReleaseSendableClaim(ctx context.Context, pool \*pgxpool.Pool, token string) error {" claim.go` must print `1`. Edit `claim.go`: old_string
```
func truthy(s *string) bool {
```
new_string:
```
// RefreshSendableClaim renews the lease of the claim that carries token and
// returns how many rows it renewed. One UPDATE keyed by the token, so a
// released or taken-over claim matches nothing and is never resurrected.
// Python: refresh_sendable_claim.
func RefreshSendableClaim(ctx context.Context, pool *pgxpool.Pool, token string) (int64, error) {
	tag, err := pool.Exec(ctx,
		`UPDATE submission_claim SET claimed_at = $1 WHERE claim_token = $2`, nowSeconds(), token)
	if err != nil {
		return 0, err
	}
	return tag.RowsAffected(), nil
}

func truthy(s *string) bool {
```

**Step 4. Go: `sendClaimedBatches`.** Anchor: `cd /home/user/jsfpecharoperations/go/internal/ubyport && grep -c "	sender := d.NewSender(apt)" sweep.go` must print `1`. Edit `sweep.go`: old_string
```
	sender := d.NewSender(apt)
	var results []BatchResult
	for start := 0; start < len(batch); start += maxBatch {
		end := min(start+maxBatch, len(batch))
		res, err := SubmitBatch(ctx, d.Batch, sender, apt.Apartment, apt.Ref, batch[start:end], mode)
		if err != nil {
			return results, err
		}
		results = append(results, res)
	}
	return results, nil
}
```
new_string:
```
	sender := d.NewSender(apt)
	return sendClaimedBatches(ctx, pool, token, batch, maxBatch, func(chunk []BatchPair) (BatchResult, error) {
		return SubmitBatch(ctx, d.Batch, sender, apt.Apartment, apt.Ref, chunk, mode)
	})
}

// sendClaimedBatches sends batch in chunks of maxBatch under one claim,
// renewing the claim before each chunk. A lost claim (released, or taken over
// after a stale TTL) stops the send and returns the results so far; the
// remaining guests are left for the next sweep. Python: _send_claimed_batches.
func sendClaimedBatches(ctx context.Context, pool *pgxpool.Pool, token string, batch []BatchPair, maxBatch int, send func([]BatchPair) (BatchResult, error)) ([]BatchResult, error) {
	var results []BatchResult
	for start := 0; start < len(batch); start += maxBatch {
		n, err := RefreshSendableClaim(ctx, pool, token)
		if err != nil {
			return results, err
		}
		if n == 0 {
			log.Printf("submission_claim_lost sent_batches=%d remaining=%d", len(results), len(batch)-start)
			break
		}
		end := min(start+maxBatch, len(batch))
		res, err := send(batch[start:end])
		if err != nil {
			return results, err
		}
		results = append(results, res)
	}
	return results, nil
}
```
Command: `cd /home/user/jsfpecharoperations/go && gofmt -l internal/ubyport 2>&1 | tail -5; go vet ./internal/ubyport/ 2>&1 | tail -10`. Expected: no output.

**Step 5. Go tests.** Append to `go/internal/ubyport/claim_test.go`:
```go
func claimedAt(t *testing.T, pool *pgxpool.Pool, id int64) float64 {
	t.Helper()
	var v float64
	if err := pool.QueryRow(context.Background(),
		`SELECT claimed_at FROM submission_claim WHERE guest_id = $1`, id).Scan(&v); err != nil {
		t.Fatal(err)
	}
	return v
}

func TestRefreshRenewsOwnClaimAndNeverResurrects(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	id := seedGuest(t, pool)
	pairs := []ClaimPair{{GuestID: id, SubmitState: "pending", Built: builtOf(t, pool, id)}}
	tok, got, err := ClaimSendable(ctx, pool, pairs)
	if err != nil || len(got) != 1 {
		t.Fatalf("claim: %v, %d pairs", err, len(got))
	}
	if _, err := pool.Exec(ctx, `UPDATE submission_claim SET claimed_at = claimed_at - 600 WHERE guest_id = $1`, id); err != nil {
		t.Fatal(err)
	}
	if n, err := RefreshSendableClaim(ctx, pool, tok); err != nil || n != 1 {
		t.Fatalf("refresh own claim: %d, %v", n, err)
	}
	if age := nowSeconds() - claimedAt(t, pool, id); age > 60 {
		t.Fatalf("claim not renewed, age %.0f s", age)
	}
	if n, err := RefreshSendableClaim(ctx, pool, "someone-else"); err != nil || n != 0 {
		t.Fatalf("refresh foreign token: %d, %v", n, err)
	}
	if err := ReleaseSendableClaim(ctx, pool, tok); err != nil {
		t.Fatal(err)
	}
	if n, err := RefreshSendableClaim(ctx, pool, tok); err != nil || n != 0 {
		t.Fatalf("refresh released claim: %d, %v", n, err)
	}
	if c := claimCount(t, pool, id); c != 0 {
		t.Fatalf("released claim came back: %d rows", c)
	}
}

func TestSendClaimedBatchesRefreshesBeforeEachBatchAndStopsWhenLost(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	id := seedGuest(t, pool)
	pairs := []ClaimPair{{GuestID: id, SubmitState: "pending", Built: builtOf(t, pool, id)}}
	tok, _, err := ClaimSendable(ctx, pool, pairs)
	if err != nil {
		t.Fatal(err)
	}
	var ages []float64
	send := func([]BatchPair) (BatchResult, error) {
		ages = append(ages, nowSeconds()-claimedAt(t, pool, id))
		// Pretend this batch took ten minutes.
		if _, err := pool.Exec(ctx, `UPDATE submission_claim SET claimed_at = claimed_at - 600 WHERE guest_id = $1`, id); err != nil {
			t.Fatal(err)
		}
		return BatchResult{Submitted: 1}, nil
	}
	results, err := sendClaimedBatches(ctx, pool, tok, make([]BatchPair, 3), 1, send)
	if err != nil || len(results) != 3 {
		t.Fatalf("results %d, err %v", len(results), err)
	}
	for i, age := range ages {
		if age > 60 {
			t.Fatalf("batch %d ran under a stale claim, age %.0f s", i, age)
		}
	}

	if err := ReleaseSendableClaim(ctx, pool, tok); err != nil {
		t.Fatal(err)
	}
	called := 0
	results, err = sendClaimedBatches(ctx, pool, tok, make([]BatchPair, 2), 1,
		func([]BatchPair) (BatchResult, error) { called++; return BatchResult{}, nil })
	if err != nil || len(results) != 0 || called != 0 {
		t.Fatalf("lost claim: results %d, called %d, err %v", len(results), called, err)
	}
	if c := claimCount(t, pool, id); c != 0 {
		t.Fatalf("lost claim was resurrected: %d rows", c)
	}
}
```
Command: `cd /home/user/jsfpecharoperations/go && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ubyport/ -count=1 -run 'Refresh|SendClaimedBatches|Claim' -v 2>&1 | tail -30`. Expected: all `--- PASS`, none `--- SKIP`.
Revert-bite checks (restore exactly, rerun green):
- (a) in `sendClaimedBatches` change `n, err := RefreshSendableClaim(ctx, pool, token)` to `n, err := int64(1), error(nil)`; run `-run SendClaimedBatches`; expect FAIL (stale age or the lost-claim part).
- (b) in `RefreshSendableClaim` change `WHERE claim_token = $2` to `WHERE claim_token = $2 OR true`; run `-run Refresh`; expect FAIL (foreign token renews a row).
If either does not fail, STOP.

**Step 6. Final run and report.** From `App/`: `.venv/bin/python -m pytest tests/test_claim_recheck_stay.py tests/test_claim_*.py tests/test_stale_submission.py tests/test_submission_*.py tests/test_filing_watchdog.py tests/test_icalsync.py tests/test_ical_skip_unchanged.py tests/test_sm_*.py -q --tb=short 2>&1 | tail -30` (all pass; a failing `test_sm_*` pin means STOP and name it). From `go/`: `UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ical/ ./internal/ubyport/ -count=1 2>&1 | tail -30` (both `ok`, not SKIP; `-v 2>&1 | grep -c SKIP` prints 0), `go vet ./internal/ical/ ./internal/ubyport/ 2>&1 | tail -10`, `gofmt -l internal 2>&1 | tail -5` (no output). From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -3` expected OK. Claim-recovery check: `test_stale_submission.py`, `test_submission_retry_cap.py` and `test_filing_watchdog.py` (they read `claimed_at` against the TTL) stay green. Write the report (§9) and set `Status: review`.

## 5. Do not touch

- Any file outside §3. No `door_codes.py`, no `billing*`, no iCal files (1140).
- AGENTS.md hard rules that apply: 1 (UbyPort filing correctness beats everything: the refresh must never create or extend a claim it does not own), 3 (public repo: no secrets or guest data in tests/logs), 5 (SQL stays Postgres-portable; no schema change), 8 (never push to `main`; merge only via `scripts/merge-pr-on-green.sh`; keep the PR draft). No new dependency; the new log lines carry ids and counts only.
- Do not change `SUBMISSION_CLAIM_TTL_SECONDS`, `SubmissionClaimTTL`, `claim_sendable`, `ClaimSendable`, `recover_stale_submissions`.

## 6. Commands

Python from `App/`, Go from `go/` with `UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest`: the Step 2, 5 and 6 commands, each ending `2>&1 | tail -30`. Expected output is stated per step. Never the full suite.

## 7. Acceptance

- [ ] `grep -c "refresh_sendable_claim" App/app/reporting.py` prints 2 or more; `grep -c "RefreshSendableClaim" go/internal/ubyport/sweep.go go/internal/ubyport/claim.go` shows at least 1 in each.
- [ ] The three new Python tests and the two new Go tests pass; Go output has no SKIP.
- [ ] Revert-bite checks (a)-(b) in Step 2 and (a)-(b) in Step 5 each failed as stated and were restored.
- [ ] A multi-batch send keeps `claimed_at` advanced (tests `multi_batch_send_keeps_the_claim_live`, `SendClaimedBatches...`); a released or stolen claim is not resurrected and stops the send.
- [ ] Claim-recovery and stale tests, `test_sm_*`, `go vet`, `gofmt -l` clean; `python3 scripts/context_lint.py 2>&1 | tail -3` is OK.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt or anchor is not found, or a count in Step 1/3/4 is not `1`;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a revert-bite check does not fail;
- a `test_sm_*` pin or a claim-recovery test fails;
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1140b-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

The reviewer reads every line of:
- `App/app/reporting.py`: `refresh_sendable_claim`, `_send_claimed_batches`, the `submit_for_apartment` call. Check the UPDATE is keyed by token only, and that a 0-row refresh breaks out before `submit_batch`.
- `go/internal/ubyport/claim.go` (`RefreshSendableClaim`) and `sweep.go` (`sendClaimedBatches`, `SubmitForApartment`): same two checks; the `defer ReleaseSendableClaim` still runs on every path.
- Known behaviour to confirm: a lost claim ends the send quietly (guests stay pending for the next sweep); the batch already in flight when the claim is lost is not interrupted.

## Owner steps

1. None for this brief. After review, Josef merges with `scripts/merge-pr-on-green.sh` once the draft may ship (green merges auto-deploy).
