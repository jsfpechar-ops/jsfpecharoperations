# 1164b report: stuck running filing recovered in every apartment mode (Go)

Status: blocked (one question, see Questions)

## Files changed

Commits on task/1164b-stuck-running-all-modes-go: steps 1, 2, 4 (bite runs leave no change).
Changed files:
 docs/context/known-issues.md      |   2 +-
 go/internal/ubyport/sweep.go      |  40 +++++++++++
 go/internal/ubyport/sweep_test.go | 135 ++++++++++++++++++++++++++++++++++++++
 3 files changed, 176 insertions(+), 1 deletion(-)

## Commands (last lines of output)

- Step 1 (before fix): `go test ... -run 'TestSweepRecover|TestSweepNever' -v`. FAIL: the four subtests of TestSweepRecoversAStuckRunningBatchWhereItSkipsTheApartment (manual, manual stale claim, inactive, auth failed). PASS: TestSweepNeverRecoversALiveClaimInManualMode, TestSweepRecoversAnAutoApartmentStuckBatchOnce, TestSweepRecoveryStaysInsideTheRequestedWorkspace. FAIL, as expected.
- Step 2: `gofmt -l internal/ubyport` silent. `go vet ./internal/ubyport/` silent. `go test ./internal/ubyport/ -count=1`: `ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport 44.491s`.
- Step 4: `grep -c 'K-F23 closed' docs/context/known-issues.md`: `1`. `python3 scripts/context_lint.py | tail -3`: `context lint: FAIL` (see Questions).
- Step 5: gofmt and vet silent. SKIP count (ubyport + ical, -v): `0`. `go test ./internal/ubyport/ ./internal/ical/ -count=1`: `ok ... ubyport 51.537s`, `ok ... ical 23.294s`.

## Revert bites

- Bite (a), delete the recoverStuckRunningBatches call in Sweep: `--- FAIL: TestSweepRecoversAStuckRunningBatchWhereItSkipsTheApartment` only. Restored: `ok`.
- Bite (b), `a.owner_user_id = $1 OR true`: `--- FAIL: TestSweepRecoveryStaysInsideTheRequestedWorkspace` only. Restored: `ok`.
- Bite (c), recovery replaced by a plain UPDATE that ignores the claim: `--- FAIL: TestSweepRecoversAStuckRunningBatchWhereItSkipsTheApartment`, `--- FAIL: TestSweepNeverRecoversALiveClaimInManualMode`, `--- FAIL: TestSweepRecoversAnAutoApartmentStuckBatchOnce`. Restored: `ok`.

## Section 7 (acceptance)

- [x] Stuck batch in manual, inactive and auth-failed apartments becomes outcome_unknown, guest pointed, one critical alert, nothing sent.
- [x] Live claim (10 s) in manual mode: row stays running, no alert.
- [x] Auto apartment: two sweeps leave one alert row.
- [x] Other workspace's sweep leaves the row alone.
- [x] Bites (a) one, (b) one, (c) three, each ok after restore.
- [x] gofmt and vet silent; SKIP count 0; K-F23 closed line written.
- [ ] context lint OK: FAILS (known-issues.md about 2522 tokens, cap 2500).

## Deviations

None in code. Steps 1 to 5 ran as written.

## Questions

1. `docs/context/known-issues.md` is over the 2500-token cap after the exact K-F23 line from the brief. Lint was OK before the edit (checked at HEAD~1). The new line is about 25 tokens longer than the line it replaces. Options for the orchestrator: (a) shorten the K-F23 line to fit, (b) move older K-F entries to the archive. I did not reword or compact other lines without a decision.

## Owner steps left

1. Decide the known-issues cap fix (question 1); then `python3 scripts/context_lint.py` must print OK.
2. Push the branch and open a draft PR (not done here).
