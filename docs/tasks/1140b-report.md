# 1140b report: renew the submission claim before each batch

Status: review
Branch: exec-1140b (no push, no PR: owner instruction for this run)

## 1. Files changed (`git diff --stat de4ff423~1 HEAD`)

- App/app/reporting.py (+`refresh_sendable_claim`, +`_send_claimed_batches`, `submit_for_apartment` uses it)
- App/tests/test_claim_recheck_stay.py (+3 tests, `import time`)
- go/internal/ubyport/claim.go (+`RefreshSendableClaim`)
- go/internal/ubyport/sweep.go (+`sendClaimedBatches`, `SubmitForApartment` uses it)
- go/internal/ubyport/claim_test.go (+2 tests, `claimedAt` helper)
- docs/tasks/1140b-claim-refresh-before-each-batch.md (Status: review)
- docs/tasks/1140b-report.md (this file)

## 2. Commands (last lines of output)

- Step 1 import: `import app.reporting` (no output)
- Step 2: `pytest tests/test_claim_recheck_stay.py -q` gave `7 passed in 1.24s`
- Step 5: `go test -run 'Refresh|SendClaimedBatches|Claim' -v` gave `--- PASS` for both new tests, `ok ... ubyport`
- Step 6 Python: `pytest <brief set> -q` gave `420 passed, 1 warning in 21.47s`
- Step 6 Go: `go test ./internal/ical/ ./internal/ubyport/ -count=1` gave `ok ... ical 12.950s`, `ok ... ubyport 32.528s`; SKIP count 0
- `go vet` clean; `gofmt -l internal` clean
- `python3 scripts/context_lint.py` gave `context lint: OK`

## 3. Checklist (§7)

- [x] `refresh_sendable_claim` count in reporting.py = 2; `RefreshSendableClaim` in sweep.go = 1, claim.go = 2
- [x] Three new Python tests and two new Go tests pass, no SKIP
- [x] Revert-bite checks: all four failed as expected and were restored (see 4)
- [x] Multi-batch send keeps the claim live; lost claim stops the send and is not resurrected
- [x] Claim-recovery, stale, `test_sm_*`, vet, gofmt clean; context lint OK

## 4. Revert-bite outcomes

- Python (a) `if False and not refresh...`: `test_a_multi_batch_send_keeps_the_claim_live` FAIL; restored, 7 passed.
- Python (b) `or True`: `test_a_lost_claim_stops_the_send_and_is_not_resurrected` FAIL (`[{}, {}] == []`); restored, 7 passed.
- Go (a) `n, err := int64(1), error(nil)`: `TestSendClaimedBatches...` FAIL (`batch 1 ran under a stale claim, age 600 s`); restored, ok.
- Go (b) `OR true` in the UPDATE: `TestRefreshRenews...` FAIL (`refresh foreign token: 1`); restored, PASS.

## 5. Deviations

- None to the diffs. `import time` added to the Python test file as the brief allows.
- Depends-on-1140 ignored per owner instruction.
- No PR opened and nothing pushed (owner instruction for this run).
- Context lint prints a WARN that 8 commits touched App/ after the last status.md update; status.md is not in this brief's file list, so it was not edited. Orchestrator updates it at review.

## 6. Questions

- None.

## 7. Owner steps left

1. Review the diff (the Risk list in the brief). Then open a PR from `exec-1140b` and keep it draft until it may ship.
2. After review, merge with `scripts/merge-pr-on-green.sh` (green merges auto-deploy).
