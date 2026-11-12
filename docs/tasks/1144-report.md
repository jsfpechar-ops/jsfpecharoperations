# Report 1144: claimed_at stamped at the INSERT

Status: review

## Files changed

```
go/internal/ubyport/claim.go      | 9 +++++++--
go/internal/ubyport/claim_test.go | 31 +++++++++++++++++++++++++++++++
```

## Commands (last lines)

Step 1 `go build ./...`: exit 0, no output.
Step 2 `go vet ./internal/ubyport/`: exit 0, no output.
Step 3 (with fix): `--- PASS: TestClaimedAtIsStampedAtInsertNotBeforeLockWaits`, `PASS`, `ok ... internal/ubyport`.

Step 4 revert-bite (INSERT argument and claimedNow reverted to `now`):
```
    claim_test.go:444: claimed_at 1794495812 is 0 s after the first read, want about 100: stamped before the lock waits
--- FAIL: TestClaimedAtIsStampedAtInsertNotBeforeLockWaits (0.46s)
FAIL
```
Restored (git checkout to the committed fix), same test:
```
--- PASS: TestClaimedAtIsStampedAtInsertNotBeforeLockWaits (0.50s)
PASS
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ubyport	0.504s
```

§6 commands:
1. `-run 'Refresh|SendClaimedBatches|Claim'`: every test PASS (15 tests incl. the new one), `ok ... internal/ubyport 13.625s`.
2. `go test ./internal/ical/ ./internal/ubyport/`: `ok ... internal/ical 17.408s`, `ok ... internal/ubyport 47.906s`.
3. SKIP count: `0`.
4. `scripts/context_lint.py`: `context lint: OK` (existing WARN lines name other open briefs; none from this branch).

## §7 acceptance

- [x] `git diff --stat` lists only claim.go and claim_test.go (plus this report).
- [x] `grep -n claimedNow` shows two lines (assignment and INSERT argument).
- [x] New test PASSES with the fix and FAILS with the INSERT argument reverted (output above).
- [x] Commands 1 and 2 pass; command 3 prints `0`.

## Deviations

- Paths: brief's `/home/user/jsfpecharoperations/go` replaced by `/home/user/wt-1144/go` as instructed.
- Step 3 was committed before the DB was reachable (credentials were fixed by the orchestrator later); its run and the rest are above.
- The first attempt at the test failed on DB auth; this is resolved and not a code issue.

## Questions

None.

## Owner steps left

1. When ready, open the PR (orchestrator), CI green, then merge only with `scripts/merge-pr-on-green.sh <PR number>`.
