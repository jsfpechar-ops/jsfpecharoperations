# 1161b: a crash-stuck `running` filing is recovered in every apartment mode (K-F23), Go twin of 1161

Status: blocked
Depends on: 1161 (Python twin, same rule) | Base commit: 174db7a2 (HEAD of branch claude/zealous-maxwell-a7ub54) | Branch: task/1161b-stuck-running-all-modes-go
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

HIGH RISK filing path: the reviewer reads every diff line in the Risk list. This is the brief that fixes production: the Go service runs the live `submit` job. Do both 1161 and 1161b before merging either.

## 1. Objective

Make the Go sweep (`go/internal/ubyport`, job `submit`) behave exactly as Python does after brief 1161: before its normal loop it runs `RecoverStaleSubmissions` for every apartment that has a `running` batch, whatever its `automation_mode`, `active` flag or `ubyport_auth_failed` alert. Today `Sweep` skips those apartments, so a crash-stuck `running` batch there stays invisible and the iCal date move it holds (1154b) is deferred with only a log line. Recovery rewrites the row to `outcome_unknown` and raises the existing critical alert; it never sends.

## 2. Context

Rule 1: UbyPort filing correctness beats every other feature. Read nothing else; the reasoning is here.

**Which runtime runs the sweep in production: Go.** `docs/context/status.md`: "Go jobs = queue: billing_snapshot, stripe_sweep, ical, push, submit". `go/cmd/ubyhost-web/main.go`: `goIntervals` has `"submit": 10` and the `"submit"` handler calls `ubyport.Sweep(ctx, d, nil)` (line ~308). `UBYHOST_GO_JOB_KINDS` (docs/ENVIRONMENT.md) must include `submit` and Python's `jobqueue` skips Go kinds. The Python sweep (1161) only runs on rollback.

**Why `RecoverStaleSubmissions(ctx, pool, aptID, now)` is safe for any apartment** (`go/internal/ubyport/recover.go`):
- Staleness is the send claim only: a `running` batch whose guests hold a claim with `claimed_at >= now - SubmissionClaimTTL` (300 s) is skipped, so a live send is never touched (`TestRecoverLiveClaimLeftAlone`).
- Scan and each write run under `lockSubmitApartment` (`pg_advisory_xact_lock(hashtext('submit_apartment'), aptID)`), the lock a send holds; the write is `UPDATE ... WHERE id = $3 AND state = 'running'` and an outcome recorded after the scan stands (`TestRecoverKeepsAnOutcomeRecordedAfterTheScan`).
- It is idempotent: a second run finds nothing and returns 0 without a new alert (`TestRecoverStaleBatches`, "second run").
- It never sends: it sets `outcome_unknown`, points unsent guests at the row and raises the critical alert `submission_outcome_unknown:<apt>` with the existing copy keys. No new copy (see 1161 section 2: the alert detail says the system resends; in manual mode it does not; owner decision, not changed here).

**Where it goes.** `Sweep` (sweep.go, `func Sweep(ctx context.Context, d SweepDeps, ownerUserID *int64) (SweepSummary, error)`, line 776) selects only `active = 1 AND automation_mode != 'manual'` apartments and skips an open `ubyport_auth_failed` alert. A new unexported helper `recoverStuckRunningBatches` is called once at the top of `Sweep`, before that query. It selects `DISTINCT s.apartment_id` from `submission s JOIN apartment a` with `s.state = 'running'` (scoped to `ownerUserID` when given), calls `RecoverStaleSubmissions` per apartment, and logs and continues on an error (one broken apartment must not stop every other apartment's filing, as `Sweep` already contains per-apartment failures). `sweepApartment` still calls `RecoverStaleSubmissions` itself; that stays and is a no-op after the pre-pass.

Anchors, current code (`go/internal/ubyport/sweep.go`; each occurs once):
```go
// Sweep is reporting.sweep: every active, non-manual apartment (or one
```
and
```go
func Sweep(ctx context.Context, d SweepDeps, ownerUserID *int64) (SweepSummary, error) {
	pool := d.Batch.Pool
	var summary SweepSummary
```
Imports `context`, `fmt`, `log`, `time`, `pgxpool` are already in sweep.go.

Test helpers already in the package (`go/internal/ubyport/*_test.go`): `claimTestPool(t)` (isolated Postgres schema from `UBYHOST_TEST_DATABASE_URL`), `sweepDeps(t, pool, "pw", sender)` (clock fixed at 2026-11-01T10:00Z via `d.Batch.Now`), `sweepSender{sizes}`, `sweepFixtureApartment(t, pool, contact)` (apartment with an owner), `notifyStay(t, pool, apt, uid, from, to)` (reservation and one guest), `InsertSubmission`, `storeRead`, `effectsCount`, `batchOpenAlert`, `ptrString`, `RaiseAlert`. `sweep_test.go` already imports `context, encoding/json, fmt, testing, time, pgxpool`.

## 3. Files

| Path | Action | What |
|---|---|---|
| go/internal/ubyport/sweep.go | edit | new `recoverStuckRunningBatches`, one call in `Sweep` |
| go/internal/ubyport/sweep_test.go | edit | append 1 helper and 4 test functions (one with 4 subtests) |
| docs/context/known-issues.md | edit | K-F23 line closed |
| docs/tasks/1161b-stuck-running-recovered-in-all-modes-go.md | status | `review` at the end |
| docs/tasks/1161b-report.md | create | report |

No other file may change. No schema, no copy, no dependency.

## 4. Steps

Commit after each step: `git add -A && git commit -qm "1161b step N"`. Work from `go/` for every command. Every `go test` needs `UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest` in front (start Postgres first if `pg_isready -h localhost` says no response: `pg_ctlcluster 16 main start`).

**Step 1. Tests first (they must fail before the fix).** Append this block to the end of `go/internal/ubyport/sweep_test.go` (the file currently ends with the function whose last lines are `t.Fatalf("open card = %d, want 0", got)`, then `}`, then `}`; append after that final `}` with one blank line between):
```go
// stuckRunning seeds an apartment (mode, active), one stay with an unsent guest and a
// running batch nobody points at, as a crash leaves it. claimAge < 0 means no claim row;
// otherwise it is the claim's age in seconds at the sweep clock.
func stuckRunning(t *testing.T, pool *pgxpool.Pool, d SweepDeps, mode string, active int, claimAge int) (ApartmentRef, int64, int64) {
	t.Helper()
	ctx := context.Background()
	ref := sweepFixtureApartment(t, pool, ptrString("host@example.test"))
	if _, err := pool.Exec(ctx, `UPDATE apartment SET automation_mode = $1, active = $2 WHERE id = $3`, mode, active, ref.ID); err != nil {
		t.Fatal(err)
	}
	_, guest := notifyStay(t, pool, ref.ID, fmt.Sprintf("stuck-%d", time.Now().UnixNano()), "2099-01-10", "2099-01-12")
	sub, err := InsertSubmission(ctx, pool, ref.ID, "auto", []int64{guest}, "ep", "2026-11-01T09:00:00+00:00")
	if err != nil {
		t.Fatal(err)
	}
	if claimAge >= 0 {
		if _, err := pool.Exec(ctx,
			`INSERT INTO submission_claim (guest_id, claim_token, claimed_at) VALUES ($1, 't', $2)`,
			guest, float64(d.Batch.Now().Unix())-float64(claimAge)); err != nil {
			t.Fatal(err)
		}
	}
	return ref, guest, sub
}

func TestSweepRecoversAStuckRunningBatchWhereItSkipsTheApartment(t *testing.T) {
	cases := []struct {
		name     string
		mode     string
		active   int
		claimAge int
		authFail bool
	}{
		{"manual", "manual", 1, -1, false},
		{"manual stale claim", "manual", 1, 600, false},
		{"inactive", "immediate", 0, -1, false},
		{"auth failed", "immediate", 1, -1, true},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			ctx := context.Background()
			pool := claimTestPool(t)
			s := &sweepSender{}
			d := sweepDeps(t, pool, "pw", s)
			ref, guest, sub := stuckRunning(t, pool, d, c.mode, c.active, c.claimAge)
			if c.authFail {
				if err := RaiseAlert(ctx, pool, "critical", "ubyport_auth_failed", "login refused", "",
					fmt.Sprintf("ubyport_auth_failed:%d", ref.ID), &ref.ID, nil, nil, nil); err != nil {
					t.Fatal(err)
				}
			}

			if _, err := Sweep(ctx, d, ref.OwnerUserID); err != nil {
				t.Fatal(err)
			}

			if st := storeRead(t, pool, "submission", sub, "state")["state"]; st != "outcome_unknown" {
				t.Fatalf("state %q, want outcome_unknown", st)
			}
			if got := storeRead(t, pool, "guest", guest, "submission_id")["submission_id"]; got != fmt.Sprint(sub) {
				t.Fatalf("guest points at %q, want %d", got, sub)
			}
			key := fmt.Sprintf("submission_outcome_unknown:%d", ref.ID)
			if n := effectsCount(t, pool, `SELECT count(*) FROM alert WHERE dedupe_key = $1 AND resolved_at IS NULL AND level = 'critical'`, key); n != 1 {
				t.Fatalf("critical alerts open = %d, want 1", n)
			}
			if len(s.sizes) != 0 {
				t.Fatalf("recovery sent %v, want nothing", s.sizes)
			}
		})
	}
}

func TestSweepNeverRecoversALiveClaimInManualMode(t *testing.T) {
	ctx := context.Background()
	pool := claimTestPool(t)
	s := &sweepSender{}
	d := sweepDeps(t, pool, "pw", s)
	ref, guest, sub := stuckRunning(t, pool, d, "manual", 1, 10)

	if _, err := Sweep(ctx, d, ref.OwnerUserID); err != nil {
		t.Fatal(err)
	}

	if st := storeRead(t, pool, "submission", sub, "state")["state"]; st != "running" {
		t.Fatalf("live claim: state %q, want running", st)
	}
	if got := storeRead(t, pool, "guest", guest, "submission_id")["submission_id"]; got != "<nil>" {
		t.Fatalf("live claim: guest pointed at %q", got)
	}
	if n := batchOpenAlert(t, pool, fmt.Sprintf("submission_outcome_unknown:%d", ref.ID)); n != 0 {
		t.Fatalf("live claim raised %d alerts", n)
	}
}

func TestSweepRecoversAnAutoApartmentStuckBatchOnce(t *testing.T) {
	ctx := context.Background()
	pool := claimTestPool(t)
	s := &sweepSender{}
	d := sweepDeps(t, pool, "pw", s)
	ref, _, sub := stuckRunning(t, pool, d, "immediate", 1, -1)

	for i := 0; i < 2; i++ {
		if _, err := Sweep(ctx, d, ref.OwnerUserID); err != nil {
			t.Fatal(err)
		}
	}

	if st := storeRead(t, pool, "submission", sub, "state")["state"]; st != "outcome_unknown" {
		t.Fatalf("state %q, want outcome_unknown", st)
	}
	// The retry pass may settle the alert itself in auto mode; the recovery pass
	// must not raise a second one.
	if n := effectsCount(t, pool, `SELECT count(*) FROM alert WHERE dedupe_key = $1`,
		fmt.Sprintf("submission_outcome_unknown:%d", ref.ID)); n != 1 {
		t.Fatalf("alert rows = %d, want 1", n)
	}
}

func TestSweepRecoveryStaysInsideTheRequestedWorkspace(t *testing.T) {
	ctx := context.Background()
	pool := claimTestPool(t)
	d := sweepDeps(t, pool, "pw", &sweepSender{})
	ref, _, sub := stuckRunning(t, pool, d, "manual", 1, -1)
	other := *ref.OwnerUserID + 100000

	if _, err := Sweep(ctx, d, &other); err != nil {
		t.Fatal(err)
	}

	if st := storeRead(t, pool, "submission", sub, "state")["state"]; st != "running" {
		t.Fatalf("state %q, want running for another workspace's sweep", st)
	}
}
```
Command: `UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ubyport/ -run 'TestSweepRecover|TestSweepNever' -count=1 2>&1 | tail -30`. Expected (fix not yet applied): `--- FAIL: TestSweepRecoversAStuckRunningBatchWhereItSkipsTheApartment` (all four subtests fail), `FAIL`; the other three tests pass.

**Step 2. The fix in `go/internal/ubyport/sweep.go`.**
(a) Insert directly above the line `// Sweep is reporting.sweep: every active, non-manual apartment (or one` (a blank line before and after the new function):
```go
// recoverStuckRunningBatches is reporting._recover_stuck_running_batches (K-F23).
// Sweep skips manual and inactive apartments and those with an open
// ubyport_auth_failed alert, so a batch a crash left running there stayed
// invisible and silently held an iCal date move. This rewrites such a batch of
// EVERY apartment (or one workspace's) through RecoverStaleSubmissions: the row
// becomes outcome_unknown, its guests are pointed at it and the critical alert is
// raised. It never sends, so it is safe in every mode. A failure is logged and
// contained to its apartment.
func recoverStuckRunningBatches(ctx context.Context, pool *pgxpool.Pool, ownerUserID *int64, now func() time.Time) {
	rows, err := pool.Query(ctx,
		`SELECT DISTINCT s.apartment_id FROM submission s JOIN apartment a ON a.id = s.apartment_id `+
			`WHERE s.state = 'running' AND ($1::bigint IS NULL OR a.owner_user_id = $1) ORDER BY s.apartment_id`,
		ownerUserID)
	if err != nil {
		log.Printf("stuck running scan failed: %v", err)
		return
	}
	var ids []int64
	for rows.Next() {
		var id int64
		if err := rows.Scan(&id); err != nil {
			rows.Close()
			log.Printf("stuck running scan failed: %v", err)
			return
		}
		ids = append(ids, id)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		log.Printf("stuck running scan failed: %v", err)
		return
	}
	for _, id := range ids {
		if _, err := RecoverStaleSubmissions(ctx, pool, id, now); err != nil {
			log.Printf("stuck running recovery failed apartment_id=%d: %v", id, err)
		}
	}
}

```
(b) Replace the two anchor lines
```go
	pool := d.Batch.Pool
	var summary SweepSummary
```
(inside `func Sweep(` only; `var summary SweepSummary` occurs once in the file) with
```go
	pool := d.Batch.Pool
	var summary SweepSummary
	recoverStuckRunningBatches(ctx, pool, ownerUserID, sweepNow(d))
```
Commands: `gofmt -l internal/ubyport` (expect no output), `go vet ./internal/ubyport/ 2>&1 | tail -30` (expect no output), then `UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ubyport/ -count=1 2>&1 | tail -30`. Expected: `ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport` (about 50 s).

**Step 3. Revert bites.** Commit step 2 first so `git checkout internal/ubyport/sweep.go` restores it. After each bite restore and rerun the bite command; expected `ok`.
Bite command (all three): `UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ubyport/ -run 'TestSweepRecover|TestSweepNever|TestSweepRecoveryStays' -count=1 2>&1 | grep -E "^(--- FAIL|ok|FAIL)"`.
(a) Delete the line `	recoverStuckRunningBatches(ctx, pool, ownerUserID, sweepNow(d))` from `Sweep`. Expected: `--- FAIL: TestSweepRecoversAStuckRunningBatchWhereItSkipsTheApartment` only.
(b) In `recoverStuckRunningBatches` replace `a.owner_user_id = $1)` with `a.owner_user_id = $1 OR true)`. Expected: `--- FAIL: TestSweepRecoveryStaysInsideTheRequestedWorkspace` only.
(c) In `recoverStuckRunningBatches` replace the line `		if _, err := RecoverStaleSubmissions(ctx, pool, id, now); err != nil {` with ``		if _, err := pool.Exec(ctx, `UPDATE submission SET state = 'outcome_unknown' WHERE state = 'running' AND apartment_id = $1`, id); err != nil {`` (a recovery that ignores the claim). Expected: `--- FAIL` for `TestSweepRecoversAStuckRunningBatchWhereItSkipsTheApartment`, `TestSweepNeverRecoversALiveClaimInManualMode` and `TestSweepRecoversAnAutoApartmentStuckBatchOnce`. (`now` becomes unused only if the compiler complains: it is a parameter, so it compiles.)

**Step 4. Close K-F23 in the docs.** In `docs/context/known-issues.md` replace the whole line starting `- K-F23 (937 review):` with
`- K-F23 closed (1161, 1161b): the sweep now rewrites a crash-stuck running filing to outcome_unknown for every apartment, manual, inactive or auth-failed included, so the critical alert shows and the date move keeps waiting; recovery never sends.`
Command: `grep -c 'K-F23 closed' ../docs/context/known-issues.md`. Expected `1`. From the repo root: `python3 scripts/context_lint.py | tail -3`. Expected `context lint: OK` (a status.md WARN is the orchestrator's).

**Step 5. Final checks.** `gofmt -l internal/ubyport` and `go vet ./internal/ubyport/ 2>&1 | tail -30`: no output. `UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ubyport/ ./internal/ical/ -count=1 -v 2>&1 | grep -c '^--- SKIP'`: expected `0`. Then `UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ubyport/ ./internal/ical/ -count=1 2>&1 | tail -30`: both `ok`.

## 5. Do not touch

`recover.go`, `RecoverStaleSubmissions`, `sweepApartment`, `RetryOutcomeUnknownBatches`, `go/internal/ical`, `go/cmd`, Python files (1161 owns them), copy files. Hard rules from AGENTS.md: 1 (filing correctness), 2 (no new outbound request or personal-data field), 4 (no dependency), 5 (SQL Postgres-portable, no schema change), 9 (no new copy).

## 6. Commands

All from `go/` with the test database URL as above. Step 1 (expect the four subtests failing), Step 2 (gofmt, vet silent; `ok`), Step 3 bites (as written, each restored to `ok`), Step 5 (SKIP count `0`; both packages `ok`). Python gates are in 1161.

## 7. Acceptance

- [ ] After `Sweep`, a `running` batch with no claim or a claim older than 300 s is `outcome_unknown` with its guest pointed at it and one open critical `submission_outcome_unknown:<apt>` alert, in a `manual` apartment, an inactive apartment and an apartment with an open `ubyport_auth_failed` alert; the sender received nothing.
- [ ] A claim younger than 300 s in a manual apartment: row stays `running`, guest not pointed, no alert.
- [ ] An auto apartment behaves as before; two sweeps leave exactly one alert row.
- [ ] `Sweep(ctx, d, &otherOwner)` leaves another workspace's stuck row alone.
- [ ] Bite (a) one failing test, (b) one, (c) three, each `ok` after `git checkout`.
- [ ] gofmt and vet silent; SKIP count 0; K-F23 closed; lint OK; only section 3 files changed.

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside section 3 needs a change;
- section 5 would be touched;
- Postgres cannot be started (the tests need it; report `blocked`);
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1161b-report.md` (600 tokens at most) and set `Status: review`. The report has: the files changed (`git diff --stat`); each command with the last 5 lines of its output; section 7 ticked; deviations; questions; owner steps left.

## Risk list (for the reviewer)

- `go/internal/ubyport/sweep.go`: `recoverStuckRunningBatches` and its one call at the top of `Sweep`. Check it only calls `RecoverStaleSubmissions` (no send, no `SubmitForApartment`), the owner scope, and that an error is logged and the loop goes on.
- `go/internal/ubyport/sweep_test.go`: the no-send assertion and the live-claim test.

## Owner steps

1. Push `task/1161b-stuck-running-all-modes-go` and open a draft PR; keep it draft until 1161 is ready.
2. Merge both with `scripts/merge-pr-on-green.sh`. Green merges auto-deploy; the Go service picks the fix up on its next restart, and the next `submit` run (within 10 minutes) rewrites any stuck row. No `.env` change.
