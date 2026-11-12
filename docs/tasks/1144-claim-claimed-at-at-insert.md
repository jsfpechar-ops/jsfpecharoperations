# 1144: ClaimSendable must stamp claimed_at at the INSERT, not before the lock waits (K-F21)

Status: todo
Depends on: 1142 | Base commit: 28106c93 | Branch: task/1144-claim-claimed-at-at-insert
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

HIGH RISK filing path: the reviewer reads every diff line in the Risk list. Go only; the Python twin does not have the bug (see §2).

## 1. Objective

In Go `ClaimSendable`, read the clock again right at each `INSERT INTO submission_claim`, so `claimed_at` is the time the claim was really born. Today it is read once at the top, before the per-guest advisory-lock waits, so after a long wait the claim is born already aged and its first refresh (1142: refresh only matches `claimed_at >= now - TTL`) can fail on a claim that was never stale.

## 2. Context

Rules: UBYPORT_CORE filing correctness beats everything. Live cutoff everywhere is `claimed_at >= now - SubmissionClaimTTL`.

Current Go (`go/internal/ubyport/claim.go`, lines 48-52), the single clock read:
```go
	now := nowSeconds()
	if _, err := tx.Exec(ctx, `DELETE FROM submission_claim WHERE claimed_at < $1`,
		now-SubmissionClaimTTL.Seconds()); err != nil {
		return "", nil, err
	}
```
The advisory locks are taken after it (`SELECT pg_advisory_xact_lock(hashtext($1), $2)`, can block for as long as another worker holds the guest), then the INSERT reuses the old `now` (lines 97-100):
```go
		tag, err := tx.Exec(ctx,
			`INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES ($1, $2, $3)
			 ON CONFLICT (guest_id) DO NOTHING`,
			p.GuestID, token, now)
```
The clock helper (lines 148-151):
```go
// nowSeconds is Python's time.time(): a float of Unix seconds.
func nowSeconds() float64 {
	return float64(time.Now().UnixNano()) / 1e9
}
```

Which uses of `now` change:
- The INSERT `claimed_at`: MUST use a fresh read (the bug).
- The stale-claim DELETE (`claimed_at < now - TTL`) runs BEFORE the locks and is the only comparison against the TTL in this function; there is no second steal check after the locks. KEEP it on the early `now`: an older cutoff deletes fewer rows, so it can only err toward leaving a claim in place (the `ON CONFLICT DO NOTHING` then drops the pair, fail closed), and it mirrors Python, which also deletes before the locks. Do not move or duplicate the DELETE.

Python twin (`App/app/reporting.py` `claim_sendable`, ~line 1650): it calls `time.time()` inline inside the INSERT parameters (`(guest["id"], token, time.time())`), after `db.lock_key` has been taken, so it is already fresh. No Python change, no Python test.

Test seam: `nowSeconds` is a plain func and used only in `claim.go` and `claim_test.go`. Make it a package variable so a test can swap the clock. Callers `nowSeconds()` stay valid. Existing test helpers in `go/internal/ubyport/claim_test.go` that this brief uses: `claimTestPool(t)` (skips without `UBYHOST_TEST_DATABASE_URL`), `seedGuest(t, pool)`, `builtOf(t, pool, id)`, `claimedAt(t, pool, id)`, `ReleaseSendableClaim`. Tests need `UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest`; a skipped test does NOT count as passing.

## 3. Files

| Path | Action | What |
|---|---|---|
| go/internal/ubyport/claim.go | edit | `nowSeconds` becomes a var; INSERT reads the clock fresh |
| go/internal/ubyport/claim_test.go | edit | one new test with a fake advancing clock |

No other file may change.

## 4. Steps

### Step 1: make the clock injectable (claim.go)

Find exactly:
```go
func nowSeconds() float64 {
	return float64(time.Now().UnixNano()) / 1e9
}
```
Replace with:
```go
//
// It is a variable so a test can advance the clock between two reads.
var nowSeconds = func() float64 {
	return float64(time.Now().UnixNano()) / 1e9
}
```
The comment line above it (`// nowSeconds is Python's time.time(): ...`) stays; the added `//` line continues that comment block.

Command: `cd /home/user/jsfpecharoperations/go && go build ./... 2>&1 | tail -30`
Expected: no output.

### Step 2: stamp claimed_at at the INSERT (claim.go)

Find exactly:
```go
		tag, err := tx.Exec(ctx,
			`INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES ($1, $2, $3)
			 ON CONFLICT (guest_id) DO NOTHING`,
			p.GuestID, token, now)
```
Replace with:
```go
		// Read the clock again here: the lock waits above can take long, and
		// a claim stamped with the time before them is born already aged.
		claimedNow := nowSeconds()
		tag, err := tx.Exec(ctx,
			`INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES ($1, $2, $3)
			 ON CONFLICT (guest_id) DO NOTHING`,
			p.GuestID, token, claimedNow)
```
Leave `now := nowSeconds()` and the DELETE untouched (it is still used by the DELETE).

Command: `cd /home/user/jsfpecharoperations/go && go vet ./internal/ubyport/ 2>&1 | tail -30`
Expected: no output.

### Step 3: add the test (claim_test.go)

Append at the end of the file (after the last test; the imports `context`, `testing` already exist):
```go
func TestClaimedAtIsStampedAtInsertNotBeforeLockWaits(t *testing.T) {
	pool := claimTestPool(t)
	ctx := context.Background()
	id := seedGuest(t, pool)
	pairs := []ClaimPair{{GuestID: id, SubmitState: "pending", Built: builtOf(t, pool, id)}}

	// Fake clock: every read is 100 s later than the one before, as if the
	// lock waits between the first read and the INSERT took 100 s each.
	real := nowSeconds
	start := real()
	reads := 0
	nowSeconds = func() float64 {
		reads++
		return start + float64(reads-1)*100
	}
	t.Cleanup(func() { nowSeconds = real })

	_, got, err := ClaimSendable(ctx, pool, pairs)
	nowSeconds = real
	if err != nil || len(got) != 1 {
		t.Fatalf("claim: %v, %d pairs", err, len(got))
	}
	if reads < 2 {
		t.Fatalf("clock read %d time(s); the INSERT must read it again", reads)
	}
	// Read 1 is the stale-claim DELETE (start), read 2 is the INSERT (start+100).
	if at := claimedAt(t, pool, id); at < start+99 {
		t.Fatalf("claimed_at %.0f is %.0f s after the first read, want about 100: stamped before the lock waits", at, at-start)
	}
}
```
Command: `cd /home/user/jsfpecharoperations/go && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ubyport/ -run 'TestClaimedAtIsStampedAtInsert' -count=1 -v 2>&1 | tail -30`
Expected: `--- PASS: TestClaimedAtIsStampedAtInsertNotBeforeLockWaits` and `ok`; no `SKIP`.

### Step 4: revert-bite (the test must fail without the fix)

1. In claim.go change ONLY the last argument back: `p.GuestID, token, claimedNow)` to `p.GuestID, token, now)`. Leave the `claimedNow := nowSeconds()` line (Go would then report it unused; so also change that line to `_ = nowSeconds()`).
2. Command: `cd /home/user/jsfpecharoperations/go && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ubyport/ -run 'TestClaimedAtIsStampedAtInsert' -count=1 -v 2>&1 | tail -30`
   Expected: `--- FAIL` with "stamped before the lock waits" (claimed_at about 0 s after start).
3. Restore both lines exactly as in Step 2 (`claimedNow := nowSeconds()` and the argument `claimedNow`). Confirm with `git diff go/internal/ubyport/claim.go | tail -30` that the diff is only Step 1 and Step 2.
4. Re-run the command from Step 3. Expected: PASS.

If the test passes in item 2, STOP (§8): the test does not bite.

## 5. Do not touch

- `App/` (Python is not affected), `docs/` other than your report, migrations, any other Go file.
- The stale-claim DELETE and its `now` variable; the lock loop; `RefreshSendableClaim`.
- Hard rules: no new dependency; never push to `main`; no full test suite.

## 6. Commands

1. `cd /home/user/jsfpecharoperations/go && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ubyport/ -run 'Refresh|SendClaimedBatches|Claim' -count=1 -v 2>&1 | tail -30` expect every test `--- PASS`, then `ok`.
2. `cd /home/user/jsfpecharoperations/go && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ical/ ./internal/ubyport/ -count=1 2>&1 | tail -30` expect two `ok` lines.
3. `cd /home/user/jsfpecharoperations/go && UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ubyport/ -count=1 -v 2>&1 | grep -c SKIP` expect `0`.
4. `cd /home/user/jsfpecharoperations && python3 scripts/context_lint.py 2>&1 | tail -30` expect no new error.

The Python test-map row (Filing, UbyPort, claim) is not run: no Python file changed.

## 7. Acceptance

- [ ] `git diff --stat` lists only `go/internal/ubyport/claim.go` and `go/internal/ubyport/claim_test.go` (plus the report).
- [ ] `grep -n 'claimedNow' go/internal/ubyport/claim.go | tail -30` shows two lines (assignment and INSERT argument).
- [ ] The new test PASSES with the fix and FAILS with the INSERT argument reverted (Step 4 output pasted in the report).
- [ ] Command 1 and 2 pass; command 3 prints `0`.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- the new test passes with the fix reverted;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1144-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output, including the Step 4 FAIL and PASS lines.
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

- `go/internal/ubyport/claim.go`: the INSERT argument and the `nowSeconds` var (every other `nowSeconds()` caller must still compile and behave the same).
- Confirm the DELETE still uses the early `now`.
- `go/internal/ubyport/claim_test.go`: the fake clock is restored by `t.Cleanup` even if the test fails.

## Owner steps

1. Open the pull request when the report says `review`, check the CI is green.
2. Merge it only with `scripts/merge-pr-on-green.sh <PR number>`.
