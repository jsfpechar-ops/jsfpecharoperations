# 1139 report: iCal cancel respects a live submission_claim

Status: review. Branch exec-1139, not pushed, no PR (run instruction).

## 1. Files changed (vs starting commit 267046ee)

| File | Lines |
|---|---|
| App/app/icalsync.py | 64 changed lines (helper, two call sites) |
| App/tests/test_icalsync.py | +73 |
| go/internal/ical/reconcile.go | 89 changed lines (lockStayGuests, cancelReservationUnlessClaimed, cancelExistingStay) |
| go/internal/ical/reconcile_test.go | 3 call sites |
| go/internal/ical/syncfeed.go | event and sweep call sites |
| go/internal/ical/syncfeed_test.go | +68 (two tests) |
| docs/tasks/1139-ical-cancel-respects-submission-claim.md | Status: review |
| docs/tasks/1139-report.md | this file |

Total vs 267046ee: 6 code files, 293 insertions, 27 deletions. `git diff --stat 4fff483d` also lists files from the merged 1138 branch history; those are not from this run.

## 2. Commands (last 5 lines)

- `.venv/bin/python -c "import app.icalsync"`: no output (pass).
- `pytest tests/test_icalsync.py tests/test_ical_skip_unchanged.py -q` (after step 2): `61 passed in 5.81s`.
- Same command after step 3: `63 passed in 6.42s`.
- Python area (step 7.1): `91 passed in 9.34s`.
- `go build ./internal/ical/ && go vet ./internal/ical/`: silent.
- `gofmt -l internal/ical/`: silent.
- Targeted Go run (`DeferredWhileClaimLive|CancelExistingStay|CancelEvent|VanishedStayCancelled -v`): all `--- PASS`, including both new tests, `ok`.
- Go full package (step 7.2): `ok github.com/jsfpechar-ops/.../go/internal/ical 10.838s`.
- Go SKIP count (step 7.3): `0`.
- `python3 scripts/context_lint.py`: `context lint: OK`.

## 3. Section 7 (acceptance)

- [x] Both languages cancel only through the guarded helper (Python `_cancel_reservation_unless_claimed`, Go `cancelReservationUnlessClaimed`).
- [x] `lock_key` / `lockStayGuests` take per-guest locks in ascending id.
- [x] Deferred cancel stores no digest and leaves the stay active; next sync cancels after the claim is deleted (all four new tests).
- [x] Four new tests fail under the guard revert and pass restored (below).
- [x] Go ical PASS against Postgres, 0 SKIP; vet silent; Python area green.
- [x] Only §3 files changed; lint OK.

## 4. Revert bite

- Python: removed the `NOT EXISTS` predicate and its parameter. `-k claim_is_live`: both new tests FAILED (`'cancelled' == 'active'`, and `stats["cancelled"] == 1`). Restored with `git checkout`: 3 passed.
- Go: removed the `NOT EXISTS` predicate and `liveClaimAfter()` argument. `-run DeferredWhileClaimLive`: both FAILED (`status = "cancelled", want active`, digest stored). Restored: PASS.

## 5. Deviations

- Done: steps 1 to 7 (all committed as `1139 step k`). Left: none.
- Python revert `-k claim_is_live` selected 3 tests, not 2: one pre-existing test also matches the keyword. All 3 pass after restore.
- Revert backups were restored with `git checkout` instead of `cp` to /tmp (same content, committed state).
- Step 3: first append anchor was not unique (5 matches). Re-anchored on a longer block; no content change.
- Go step 4: the existing comment above `cancelExistingStay` is 2 lines, not 3. Replaced as the brief specifies.
- Brief Status set to `review`. No PR, no push (run instruction overrides executor.md).

## 6. Questions

- Brief §2 open question: should a `running` / `outcome_unknown` submission with no live claim also defer a cancel? Not covered here (by design).

## 7. Owner steps left

1. Push the branch: `git push -u origin exec-1139` (from the worktree).
2. Open the PR and review the Risk list in the brief.
3. Merge only with `scripts/merge-pr-on-green.sh` once green.
