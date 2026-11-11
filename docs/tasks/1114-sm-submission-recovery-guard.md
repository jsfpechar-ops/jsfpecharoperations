# 1114: Stale-submission recovery must not overwrite an outcome recorded after its scan

Status: todo
Depends on: PR #920 merged to main (tables and pin tests present) | Base commit: main after PR #920 | Branch: task/1114-sm-submission-recovery-guard
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

HIGH RISK: filing. This is the police-filing attempt record (`submission.state`). Exact diffs only. Change nothing else.

## Open questions (for the owner; this brief does not decide them)

1. **The reverse direction is left as it is.** A send whose final write lands on a row that recovery has already marked `outcome_unknown` overwrites it, because the send's writes match the row by id only: `App/app/reporting.py:1763` (`outcome_unknown`), `:1801` (`transport_error`), `:1864` (the outcome from `plan_outcome`); `go/internal/ubyport/store.go:113` (`RecordOutcomeUnknown`), `:132` (`RecordTransportError`), `:159` (`RecordOutcome`). This brief does **not** change them. Reason: a late real answer is the truth about the register, and it carries the proof. `docs/UBYPORT_CORE.md` step 4 says "Persist proof: submission status, error text for the host, and the Doručenka PDF on the submission row". Refusing the late write would drop the Doručenka, and in `submit_batch` (`reporting.py:1862-1864`) and `RecordOutcome` (`store.go:154-159`) the guest writes run in the same transaction before the submission write, so a guard on the submission write alone would leave guests `sent` on a row that says `outcome_unknown`. `docs/UBYPORT_CORE.md` says nothing about `outcome_unknown` or `stale` (grep finds nothing). Owner to rule: is "a late real answer replaces `outcome_unknown`" intended? If it is, the round 1 table should list `outcome_unknown -> ok/ok_duplicate/partial/error/transport_error` (it does not today).
2. **A late answer after the automatic resend has started.** If recovery marks a batch `outcome_unknown` and the scheduler then resends it once (`_retry_outcome_unknown_batches`, `reporting.py:2072`; Go `sweep.go:597`), and only then the original send's answer arrives, the register may get the batch twice (the resend answers 150, duplicate). That window exists only when a send runs past the 5 minute claim TTL (`SUBMISSION_CLAIM_TTL_SECONDS`, `reporting.py:97`). Not changed here.
3. **The Go fix adds a test seam** (`var afterRecoverScan = func() {}` in `recover.go`). Go has no monkeypatch, and the only other ways to land a write between the scan and the write are real goroutines with sleeps, which the brief rules forbid. It does nothing in production.

## 1. Objective

`recover_stale_submissions` (Python) and `RecoverStaleSubmissions` (Go) read `running` rows in one transaction and write `outcome_unknown` in a later one with `WHERE id = ?` only. If the live send records its real outcome (for example `ok`) in between, recovery overwrites that terminal state with `outcome_unknown`, points the guests at the batch and raises a false critical alert. The fix adds `AND state = 'running'` to the recovery UPDATE in both languages; when it changes no row, recovery skips that submission, leaves its guests alone and does not count it.

## 2. Context

Rules that apply (AGENTS.md): rule 1 (UbyPort filing correctness beats every other feature), rule 5 (SQL only through `App/app/db.py` helpers or a cursor from `db.immediate()`, Postgres-portable; `?` placeholders in Python, `$n` in Go), rule 8 (never push to `main`).

The fault, verified on PR #920's code. `App/app/reporting.py`, `recover_stale_submissions` (starts at line 2010). The scan, in its own transaction:

```python
    with db.immediate() as cur:
        db.lock_key(cur, "submit_apartment", apartment_id)
        cur.execute(
            "SELECT id, guest_ids FROM submission WHERE apartment_id = ? AND state = 'running'",
            (apartment_id,),
        )
```

The write, in a later transaction per candidate, matched by id only (line 2043):

```python
    stale: List[int] = []
    for submission_id, guest_ids in candidates:
        with db.immediate() as cur:
            db.lock_key(cur, "submit_apartment", apartment_id)
            db.update_in(
                cur, "submission", submission_id,
                {"state": "outcome_unknown", "finished_at": db.utcnow(), "error_text": reason},
            )
            for guest_id in guest_ids:
```

`db.update_in` (`App/app/db.py:2101`) runs `UPDATE {table} SET ... WHERE id = ?` and returns nothing. `submit_batch`'s outcome write (`reporting.py:1864`) does not take the `submit_apartment` lock, so the lock does not keep it out. A send whose claim is older than 5 minutes (`SUBMISSION_CLAIM_TTL_SECONDS = 5 * 60`, line 97) is a candidate.

Go twin, `go/internal/ubyport/recover.go`, `RecoverStaleSubmissions`: scan at line 68, write at line 122-126:

```go
			if _, err := tx.Exec(ctx,
				`UPDATE submission SET state = 'outcome_unknown', finished_at = $1, error_text = $2 WHERE id = $3`,
				UTCNow(), staleSubmissionReason, c.id); err != nil {
				return err
			}
```

Rows-affected idioms already in use. Python, `reporting.py:2215-2221` (`_resend_unknown_chain`):

```python
        cur.execute(
            "UPDATE submission SET retried_at = ? WHERE id = ? AND retried_at IS NULL AND state = ?",
            (db.utcnow(), latest["id"], "outcome_unknown"),
        )
        if cur.rowcount != 1:
            return False  # another worker took this retry
```

Go, `go/internal/ubyport/sweep.go:596-603`:

```go
	tag, err := tx.Exec(ctx,
		`UPDATE submission SET retried_at = $1 WHERE id = $2 AND retried_at IS NULL AND state = 'outcome_unknown'`,
		UTCNow(), latestID)
	if err != nil {
		return nil, err
	}
	if tag.RowsAffected() == 0 {
```

On Postgres (READ COMMITTED), a concurrent send's outcome write holds the row lock; recovery's guarded UPDATE waits, then re-checks `state = 'running'` on the new row and changes nothing. On SQLite, `BEGIN IMMEDIATE` serialises the two.

The only encrypted column of `submission` is `request_xml` (`db.py:2363`); recovery does not write it, so a raw `cur.execute` is safe in place of `db.update_in`.

Zero rows updated means: the send recorded its own outcome after the scan. Recovery then (Python) `continue`s to the next candidate: the `with` block commits an empty transaction, the guest UPDATEs do not run, the id is not added to `stale`; (Go) returns `nil` from the transaction function before the guest UPDATEs, and the id is not added to `stale`. If no candidate was marked, both return 0 and raise no alert (the existing `if not stale: return 0` / `if len(stale) == 0 { return 0, nil }`).

The pin test `App/tests/test_sm_submission_state.py` reads the guard from the SQL text: `WHERE id = ? AND state = 'running'` pins as `("running",)` instead of `ANY`. The set of moves (`running -> outcome_unknown`) does not change, so `SUBMISSION_TRANSITIONS` keeps its entries; only its comment, which says every write has no state check, is corrected.

Go tests need Postgres: `claimTestPool` (`go/internal/ubyport/claim_test.go:19`) skips when `UBYHOST_TEST_DATABASE_URL` is unset. CI job `go` in `.github/workflows/ci.yml` runs `go test ./... -count=1` with that variable set.

Verified by the brief writer on a scratch copy of PR #920 (SQLite, Python 3 venv from `App/requirements*.txt`): the new Python test fails on today's code with `assert 1 == 0` and passes after step 3; the pin test passes after step 9; the filing test-map row passes (665 passed, 1 skipped) without `test_endtoend.py`, and `test_endtoend.py` passes alone (28 passed). On unmodified PR #920 code, `test_endtoend.py` fails when run in the same pytest command as the rest of the row, so step 10 runs it separately. Go: `gofmt -l`, `go vet ./...` clean; `go test ./internal/ubyport -run TestRecover` compiles and skips (no Postgres here). The Go test was not run against a database.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/tests/test_stale_submission.py` | edit | add one test after `test_recovery_alone_never_submits` |
| `App/app/reporting.py` | edit | guarded recovery UPDATE; comment above `SUBMISSION_TRANSITIONS` |
| `go/internal/ubyport/recover.go` | edit | test seam; guarded recovery UPDATE; count only marked batches |
| `go/internal/ubyport/recover_test.go` | edit | add one test |
| `App/tests/test_sm_submission_state.py` | edit | two pins: `ANY` becomes `("running",)` |
| `docs/tasks/1114-report.md` | create | report |

No other file may change.

## 4. Steps

### Step 1. Python failing test

File `App/tests/test_stale_submission.py`. Anchor (line 135, unique): `grep -nF '    assert calls == []' App/tests/test_stale_submission.py`

Diff:

```diff
     assert calls == []
+
+
+def test_recovery_keeps_an_outcome_recorded_after_its_scan(monkeypatch):
+    """Brief 1114: the send records ok between recovery's scan and its write."""
+    db.init_db()
+    now = db.utcnow()
+    apartment = db.insert("apartment", {"internal_name": "Late answer", "created_at": now})
+    reservation = db.insert(
+        "reservation",
+        {"apartment_id": apartment, "uid": "late-1", "date_from": "2026-01-01",
+         "date_to": "2026-01-03", "status": "active", "created_at": now, "updated_at": now},
+    )
+    guest_id = _guest(reservation, "Late", now)
+    # No claim on the guest, so the scan counts the batch as stale.
+    batch = _batch(apartment, [guest_id], now)
+    real_lock_key = db.lock_key
+    locks = []
+
+    def lock_then_answer(cur, name, key):
+        real_lock_key(cur, name, key)
+        if name != "submit_apartment":
+            return
+        locks.append(key)
+        if len(locks) == 2:
+            # The scan has committed and the write transaction has begun: the
+            # send records its answer now, before recovery writes.
+            cur.execute(
+                "UPDATE submission SET state = 'ok', finished_at = ? WHERE id = ?",
+                (db.utcnow(), batch),
+            )
+
+    monkeypatch.setattr(db, "lock_key", lock_then_answer)
+
+    assert reporting.recover_stale_submissions(apartment) == 0
+    assert len(locks) == 2
+    assert db.query_one("SELECT state FROM submission WHERE id = ?", (batch,))["state"] == "ok"
+    assert db.query_one("SELECT submission_id FROM guest WHERE id = ?", (guest_id,))["submission_id"] is None
+    assert alerts.open_alert(f"submission_outcome_unknown:{apartment}") is None
 
 
 def _sweep_apartment(monkeypatch):
```

Command, from `App/`:

```
.venv/bin/python -m pytest tests/test_stale_submission.py -q --tb=short -x -k recorded_after_its_scan 2>&1 | tail -30
```

Expected: `1 failed`, with `E   assert 1 == 0` (recovery marked the batch). This is the fault. Commit `1114 step 1`.

### Step 2. Python fix: guard the recovery write

File `App/app/reporting.py`, inside `recover_stale_submissions`. Anchor: `grep -nF '{"state": "outcome_unknown", "finished_at": db.utcnow(), "error_text": reason},' App/app/reporting.py` (one hit, line 2045).

Diff:

```diff
     for submission_id, guest_ids in candidates:
         with db.immediate() as cur:
             db.lock_key(cur, "submit_apartment", apartment_id)
-            db.update_in(
-                cur, "submission", submission_id,
-                {"state": "outcome_unknown", "finished_at": db.utcnow(), "error_text": reason},
-            )
+            cur.execute(
+                "UPDATE submission SET state = 'outcome_unknown', finished_at = ?, error_text = ? "
+                "WHERE id = ? AND state = 'running'",
+                (db.utcnow(), reason, submission_id),
+            )
+            if cur.rowcount != 1:
+                # The send recorded its own outcome after the scan above (brief
+                # 1114): that outcome stands, and its guests are left alone.
+                continue
             for guest_id in guest_ids:
```

Command: `python3 -m py_compile App/app/reporting.py 2>&1 | tail -30` from the repo root. Expected: no output. Commit `1114 step 2`.

### Step 3. Python test passes

Command, from `App/`:

```
.venv/bin/python -m pytest tests/test_stale_submission.py -q --tb=short -x 2>&1 | tail -30
```

Expected: `16 passed`. Commit only if a file changed (none should).

### Step 4. Go test seam

File `go/internal/ubyport/recover.go`. Anchor: `grep -nF '// RecoverStaleSubmissions marks the running batches of one apartment whose' go/internal/ubyport/recover.go` (line 49).

Diff:

```diff
 	return ids, nil
 }
 
+// afterRecoverScan runs after RecoverStaleSubmissions has committed its scan and
+// before its first write. It does nothing; tests replace it to record an outcome
+// in between (brief 1114).
+var afterRecoverScan = func() {}
+
 // RecoverStaleSubmissions marks the running batches of one apartment whose
```

Command, from `go/`: `go vet ./internal/ubyport 2>&1 | tail -30`. Expected: no output. Commit `1114 step 4`.

### Step 5. Go: call the seam after the scan

File `go/internal/ubyport/recover.go`. Anchor: `grep -nF '	var stale []int64' go/internal/ubyport/recover.go` (one hit). The two lines above it are `		return 0, err` and `	}`, then a blank line.

Diff:

```diff
 	if err != nil {
 		return 0, err
 	}
+	afterRecoverScan()
 
 	var stale []int64
 	for _, c := range candidates {
```

Command, from `go/`: `go vet ./internal/ubyport 2>&1 | tail -30`. Expected: no output. Commit `1114 step 5`.

### Step 6. Go failing test

File `go/internal/ubyport/recover_test.go`. Anchor: `grep -nF '// TestReportingTodayIsUTCDate pins the day the completeness checks use' go/internal/ubyport/recover_test.go` (line 137). Insert the block directly above that line (a blank line already separates it from the function before).

Diff:

```diff
+// TestRecoverKeepsAnOutcomeRecordedAfterTheScan is brief 1114: the send records
+// ok after recovery's scan has picked the batch as stale. Recovery must keep ok,
+// leave the guest alone and raise no alert.
+func TestRecoverKeepsAnOutcomeRecordedAfterTheScan(t *testing.T) {
+	pool := claimTestPool(t)
+	ctx := context.Background()
+	g1 := seedGuest(t, pool)
+	apt := storeApartmentOf(t, pool, g1)
+	// No claim on g1, so the scan counts the batch as stale.
+	sub, err := InsertSubmission(ctx, pool, apt, "auto", []int64{g1}, "ep", recoverStamp)
+	if err != nil {
+		t.Fatal(err)
+	}
+	afterRecoverScan = func() {
+		if _, err := pool.Exec(ctx,
+			`UPDATE submission SET state = 'ok', finished_at = $1 WHERE id = $2`,
+			recoverStamp, sub); err != nil {
+			t.Fatal(err)
+		}
+	}
+	t.Cleanup(func() { afterRecoverScan = func() {} })
+
+	n, err := RecoverStaleSubmissions(ctx, pool, apt, recoverNow)
+	if err != nil || n != 0 {
+		t.Fatalf("outcome after scan: n=%d err=%v", n, err)
+	}
+	if st := storeRead(t, pool, "submission", sub, "state")["state"]; st != "ok" {
+		t.Fatalf("recovery overwrote ok with %q", st)
+	}
+	if got := storeRead(t, pool, "guest", g1, "submission_id")["submission_id"]; got != "<nil>" {
+		t.Fatalf("recovery pointed g1 at %q", got)
+	}
+	if c := effectsCount(t, pool, `SELECT count(*) FROM alert WHERE dedupe_key = $1`,
+		fmt.Sprintf("submission_outcome_unknown:%d", apt)); c != 0 {
+		t.Fatalf("recovery raised %d alerts", c)
+	}
+}
+
 // TestReportingTodayIsUTCDate pins the day the completeness checks use: 23:30 UTC
```

Command, from `go/`:

```
go test ./internal/ubyport -run TestRecoverKeepsAnOutcomeRecordedAfterTheScan -count=1 -v 2>&1 | tail -30
```

Expected without a database: `--- SKIP: TestRecoverKeepsAnOutcomeRecordedAfterTheScan` with `UBYHOST_TEST_DATABASE_URL is not set`, then `ok`. If `UBYHOST_TEST_DATABASE_URL` is set: `--- FAIL` with `outcome after scan: n=1` (the fault). Commit `1114 step 6`.

### Step 7. Go fix: guard the recovery write

File `go/internal/ubyport/recover.go`. Anchor: `grep -nF "error_text = \$2 WHERE id = \$3\`," go/internal/ubyport/recover.go` (one hit; the line with `UPDATE submission SET state = 'outcome_unknown'`).

Diff:

```diff
 	var stale []int64
 	for _, c := range candidates {
+		marked := false
 		err := withTx(ctx, pool, func(tx pgx.Tx) error {
 			if err := lockSubmitApartment(ctx, tx, aptID); err != nil {
 				return err
 			}
-			if _, err := tx.Exec(ctx,
-				`UPDATE submission SET state = 'outcome_unknown', finished_at = $1, error_text = $2 WHERE id = $3`,
-				UTCNow(), staleSubmissionReason, c.id); err != nil {
+			tag, err := tx.Exec(ctx,
+				`UPDATE submission SET state = 'outcome_unknown', finished_at = $1, error_text = $2 WHERE id = $3 AND state = 'running'`,
+				UTCNow(), staleSubmissionReason, c.id)
+			if err != nil {
 				return err
 			}
+			if tag.RowsAffected() == 0 {
+				// The send recorded its own outcome after the scan (brief 1114):
+				// that outcome stands, and its guests are left alone.
+				return nil
+			}
+			marked = true
 			for _, guestID := range c.guestIDs {
```

Command, from `go/`: `go vet ./internal/ubyport 2>&1 | tail -30`. Expected: no output. Commit `1114 step 7`.

### Step 8. Go: count only batches that were marked

File `go/internal/ubyport/recover.go`. Anchor: `grep -nF '		stale = append(stale, c.id)' go/internal/ubyport/recover.go` (one hit).

Diff:

```diff
 		if err != nil {
 			return 0, err
 		}
-		stale = append(stale, c.id)
+		if marked {
+			stale = append(stale, c.id)
+		}
 	}
```

Command, from `go/`:

```
test -z "$(gofmt -l .)" && echo fmt-ok; go vet ./... 2>&1 | tail -30; go test ./internal/ubyport -run TestRecover -count=1 -v 2>&1 | tail -30
```

Expected: `fmt-ok`; no vet output; three `TestRecover...` tests `SKIP` without a database (or `PASS` with one), then `ok`. Commit `1114 step 8`.

### Step 9. Correct the transition table's comment

File `App/app/reporting.py`. Anchor: `grep -nF '# fails when a writer changes. None is the INSERT that creates the row. Every' App/app/reporting.py` (one hit, line 2746). Do not write the table's name in the comment (a test counts it).

Diff:

```diff
 # only: nothing reads this at runtime, and tests/test_sm_submission_state.py
-# fails when a writer changes. None is the INSERT that creates the row. Every
-# later write matches the row by id alone, with no state check in SQL; the
-# source state is the one the writer's code path holds.
+# fails when a writer changes. None is the INSERT that creates the row. The
+# stale-batch recovery (Python and Go) writes only while the row is still
+# 'running' (brief 1114). Every other later write matches the row by id alone,
+# with no state check in SQL; the source state is the one the writer's code
+# path holds.
```

Command: `python3 -m py_compile App/app/reporting.py 2>&1 | tail -30` from the repo root. Expected: no output. Commit `1114 step 9`.

### Step 10. Update the two pins

File `App/tests/test_sm_submission_state.py`. Anchors: `grep -nF '"recover_stale_submissions", ANY,' App/tests/test_sm_submission_state.py` (line 32) and `grep -nF '"RecoverStaleSubmissions", ANY,' App/tests/test_sm_submission_state.py` (line 37).

Diff:

```diff
-    ("App/app/reporting.py", "recover_stale_submissions", ANY, "outcome_unknown", "running"),
+    ("App/app/reporting.py", "recover_stale_submissions", ("running",), "outcome_unknown", "running"),
```

```diff
-    ("go/internal/ubyport/recover.go", "RecoverStaleSubmissions", ANY, "outcome_unknown", "running"),
+    ("go/internal/ubyport/recover.go", "RecoverStaleSubmissions", ("running",), "outcome_unknown", "running"),
```

Command, from `App/`:

```
.venv/bin/python -m pytest tests/test_sm_submission_state.py tests/test_stale_submission.py -q --tb=short -x 2>&1 | tail -30
```

Expected: `23 passed`. Commit `1114 step 10`.

### Step 11. Filing test-map row

From `App/`, two commands (on PR #920's code `test_endtoend.py` fails when it shares one pytest run with the rest of this row; alone it passes):

```
.venv/bin/python -m pytest tests/test_ubyport_*.py tests/test_soap.py tests/test_worker.py tests/test_submission_*.py tests/test_stale_submission.py tests/test_filed_by_hand.py tests/test_filing_watchdog.py tests/test_police_*.py tests/test_deadline*.py tests/test_claim_*.py tests/test_sm_submission_state.py -q --tb=short -x 2>&1 | tail -30
.venv/bin/python -m pytest tests/test_endtoend.py -q --tb=short -x 2>&1 | tail -30
```

Expected: first `665 passed, 1 skipped` (counts may differ slightly on newer main; 0 failed is what matters); second `28 passed`.

### Step 12. Context lint

From the repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`. Expected: no errors.

### Step 13. Report

Write `docs/tasks/1114-report.md` (§9) and set this brief's `Status: review`. Commit `1114 step 13`.

## 5. Do not touch

- `submit_batch` and every other function in `App/app/reporting.py` outside the two blocks in steps 2 and 9; `SUBMISSION_TRANSITIONS` entries; `TERMINAL_SUBMISSION_STATES`.
- `go/internal/ubyport/store.go` (`RecordOutcome`, `RecordTransportError`, `RecordOutcomeUnknown`) and `sweep.go`: the late-answer direction is an owner question (Open questions 1).
- `App/app/db.py`, every migration, `.github/`.
- AGENTS.md rules 1, 3, 5, 8: no push to `main`, no merge.

## 6. Commands

| Step | Command (from) | Expected |
|---|---|---|
| 1 | `.venv/bin/python -m pytest tests/test_stale_submission.py -q --tb=short -x -k recorded_after_its_scan 2>&1 \| tail -30` (App/) | `1 failed`, `assert 1 == 0` |
| 3 | `.venv/bin/python -m pytest tests/test_stale_submission.py -q --tb=short -x 2>&1 \| tail -30` (App/) | `16 passed` |
| 8 | `test -z "$(gofmt -l .)" && echo fmt-ok; go vet ./... 2>&1 \| tail -30; go test ./internal/ubyport -run TestRecover -count=1 -v 2>&1 \| tail -30` (go/) | `fmt-ok`, `ok`, SKIP or PASS |
| 10 | `.venv/bin/python -m pytest tests/test_sm_submission_state.py tests/test_stale_submission.py -q --tb=short -x 2>&1 \| tail -30` (App/) | `23 passed` |
| 11 | the two commands of step 11 (App/) | 0 failed |
| 12 | `python3 scripts/context_lint.py 2>&1 \| tail -30` (root) | no errors |

The Go test runs against Postgres only in CI job `go` (`.github/workflows/ci.yml`, `go test ./... -count=1` with `UBYHOST_TEST_DATABASE_URL`). The Python test also runs on Postgres in CI job `test-postgres-full`.

## 7. Acceptance

- [ ] Step 1 output shows the new test failing with `assert 1 == 0` before step 2.
- [ ] `grep -nF "WHERE id = ? AND state = 'running'" App/app/reporting.py` finds the recovery write.
- [ ] `grep -nF "WHERE id = \$3 AND state = 'running'" go/internal/ubyport/recover.go` finds one line.
- [ ] Steps 3, 10, 11 pass; step 8 prints `fmt-ok` and `ok`.
- [ ] `git diff --stat` lists only the files in §3.
- [ ] CI job `go` is green on the PR (the new Go test PASSes there, not SKIPs; check its log for `TestRecoverKeepsAnOutcomeRecordedAfterTheScan`).

## 8. Stop and ask

Stop, and write the report, if:

- an excerpt is not found;
- a test fails twice;
- step 1 passes on today's code (the fault is not reproduced: report `blocked`, do not apply step 2);
- you reach 25 tool calls or about 50k tokens (write the report as `blocked`, see executor.md);
- a new dependency seems needed;
- a file outside §3 needs a change;
- §5 would be touched;
- a step is unclear;
- you need push, merge, secrets, SSH or deploy (hand that to the owner with the exact command).

## 9. Report

Write `docs/tasks/1114-report.md` (600 tokens at most) and set `Status: review`. The report has:

1. The files changed (`git diff --stat`).
2. Each command, with the last 5 lines of its output (step 1's failing output included).
3. §7 ticked.
4. Deviations.
5. Questions.
6. Owner steps left.

## Risk list (for the reviewer)

Read in full:

- `App/app/reporting.py`: `recover_stale_submissions` (the whole function) and the comment above `SUBMISSION_TRANSITIONS`.
- `go/internal/ubyport/recover.go`: `afterRecoverScan` and `RecoverStaleSubmissions`.
- `App/tests/test_stale_submission.py`: `test_recovery_keeps_an_outcome_recorded_after_its_scan`.
- `go/internal/ubyport/recover_test.go`: `TestRecoverKeepsAnOutcomeRecordedAfterTheScan`.
- `App/tests/test_sm_submission_state.py`: the two changed `PINNED_WRITES` rows.

Check: on zero rows the guest UPDATEs do not run and the batch is not counted or alerted, in both languages; the Go job log shows the new test PASS, not SKIP.

## Owner steps

1. Read Open questions 1 and 2 and add one line to `docs/context/decisions.md` saying whether a late real answer may replace `outcome_unknown` (today it does).
2. When the PR's checks are green, including the job named `go`, merge it with `scripts/merge-pr-on-green.sh`.
