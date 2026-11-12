# 1138 report

Status: review
Last commit: 58299851 (`1138 step 5`); the report commit follows it.

## 1. Files changed (steps 1 to 5, against the step-1 parent)

- App/app/reporting.py: `claim_sendable` re-reads stay window and `updated_at` of guest and reservation.
- App/tests/test_claim_recheck_stay.py (new): 4 tests.
- go/internal/ubyport/submit.go: `ClaimBuilt` type, `BatchPair.Built`.
- go/internal/ubyport/collect.go: reads `updated_at`, fills `Built`.
- go/internal/ubyport/claim.go: `ClaimPair.Built`, recheck in the claim, fail closed on nil.
- go/internal/ubyport/sweep.go: passes `Built`.
- go/internal/ubyport/claim_test.go: 4 edited tests, `builtOf` helper, 3 new tests.

`git log 116def7d..HEAD` also lists brief commits for 1136 and 1137 and earlier 1138 brief commits. Those were already on the branch, not made in this run.

## 2. Commands (last lines of output)

- Step 1: `cd App && .venv/bin/python -m pytest tests/test_filed_by_hand.py tests/test_connection_reuse.py -q --tb=short -x 2>&1 | tail -30`
  `31 passed in 6.01s`
- Step 2: `cd App && .venv/bin/python -m pytest tests/test_claim_recheck_stay.py -q --tb=short -x -rs 2>&1 | tail -30`
  `4 passed in 0.84s`
- Step 3: `cd go && go build ./internal/ubyport/` and `gofmt -l`: no output.
- Step 4: `cd go && go vet ./internal/ubyport/`: no output.
- Step 5: `UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ubyport/ -count=1 -run 'Claim' -v`
  PASS: TestClaimOnlyOnce, TestClaimReplacesStaleLease, TestClaimSkipsRowsThatMovedOn, TestClaimDropsGuestWhoseWindowMovedAfterBuild, TestClaimDropsPairWithoutBuiltValues, TestClaimKeepsGuestWhoseBuiltValuesStillMatch. TestReleaseFreesGuest PASS (run by name). Go package full run: `ok ... 37.581s`, 0 SKIP.
- Step 6 gate: `.venv/bin/python -m pytest tests/test_ubyport_*.py tests/test_submission_*.py tests/test_stale_submission.py tests/test_filed_by_hand.py tests/test_claim_*.py tests/test_connection_reuse.py tests/test_zz_review.py tests/test_sm_go_parity.py tests/test_sm_guest_submit_state.py tests/test_sm_submission_state.py -q --tb=line -rs`
  `1 failed, 293 passed, 3 warnings`. Failure: `test_sm_go_parity.py::test_machine_matches_go[billing_account.status]`: `trial_pending`/`paused` in Python, not in Go tables.go. This branch does not touch `go/internal/statemachine` or billing code, so the failure is not caused by this change (not re-checked at base).
- Lint: `python3 scripts/context_lint.py 2>&1 | tail -3`: `context lint: OK`.

## 3. Acceptance (§7)

- [x] `stay_from` compare in `claim_sendable`.
- [x] test_claim_recheck_stay.py: 4 passed.
- [x] Go: three new tests PASS, package ok, 0 SKIP.
- [x] `ClaimPair{` pairs carry `Built:` except the gone-row and nil-Built pairs (not re-grepped).
- [ ] Step 6 gate: one unrelated failure (billing_account parity, see above).
- [x] context lint OK.
- [x] diff limited to §3 files (plus brief status and this report).

## 4. Deviations

1. Step 2: `fresh_db` copied verbatim (fixture only, plus `import pytest` and `from app import config, db, reporting`) into the new test file, per orchestrator decision. conftest.py untouched.
2. Step 3: brief anchor `stayTo string` is gofmt-aligned as `stayTo       string` in collect.go; the field `updated string` was added directly below it.
3. Step 5: the new `builtOf`/new tests were inserted before `TestReleaseFreesGuest` instead of appended at file end (same package, no effect).
4. Brief Status set to `in-progress` during the run, then `review`.

## 5. Questions

1. Is the billing_account parity failure known (test_sm_go_parity)? It is outside §3; it needs an owner or other-brief decision.

## 6. Owner steps left

1. Review the PR diff of the four files named in the brief's risk list.
2. Decide on the billing parity failure before merge.
3. Push and open the PR yourself (not done by the executor).
