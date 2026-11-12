# 1147 report: claim-refresh TTL boundary test and real missing-row test

Status: review

## Files changed (since 1144 merge, 24eebd88..HEAD)

```
App/tests/test_claim_recheck_stay.py | 36 +++++++++++++++++++++++++++----
go/internal/ubyport/claim_test.go    | 41 ++++++++++++++++++++++++++++++++++
```
Plus this report and the brief status line. `App/app` and `go/internal/ubyport/claim.go` have no diff.

## Commands (last lines)

- Step 2 `pytest tests/test_claim_recheck_stay.py -q`: `9 passed in 2.16s`
- Step 3 same file: `10 passed in 1.95s`, no skips
- Step 6 `go test -run TestRefreshBoundary -v`: `--- PASS: TestRefreshBoundaryIsInclusiveAtExactlyTheTTL`, `ok`
- Step 6 `gofmt -l internal`: no output
- Step 8.1 SQLite: `10 passed in 2.14s`
- Step 8.2 Postgres (`UBYHOST_DATABASE_URL=postgresql://...ubytest`): `10 passed in 8.92s`
- Step 8.3 `go test ./internal/ubyport/ -count=1`: `ok`; `go vet`: no output
- Step 8.4 `scripts/context_lint.py`: `context lint: OK` (WARN: 2 commits touched App/ after last status.md update; left to orchestrator as the brief says)

## Revert-bite

- Step 4 (`>=` to `>` in reporting.py): FAILED `test_refresh_boundary_is_inclusive_at_exactly_the_ttl` with `assert False is True`; other 9 passed. Restored; 10 passed.
- Step 5 (`renewed == expected` to `renewed > 0`): FAILED `test_a_claim_missing_one_guest_row_is_treated_as_lost` with `assert True is False`; other 9 passed. Restored; 10 passed.
- Step 7 (Go `>=` to `>`): FAIL `refresh at exactly the cutoff: 0, <nil> (want 1)`. Restored; PASS.

## Section 7 acceptance

- [x] `grep -c "gid + 1000"` prints 0
- [x] `grep -c "^def test_refresh_boundary_is_inclusive_at_exactly_the_ttl"` prints 1
- [x] File: 10 passed, 0 skipped, SQLite
- [x] Go `TestRefreshBoundaryIsInclusiveAtExactlyTheTTL` PASS, no SKIP
- [x] All three revert-bites failed the named test and were restored; App/app and claim.go diff empty
- [x] Only the two test files changed (plus brief and report)

## Deviations

- None to the code. Worktree commands used `/home/user/wt-1147` instead of the brief's `/home/user/jsfpecharoperations` paths, as instructed.
- Step 2 anchor and Edit used the file as on disk; the file-changed notice after step 3 was my own append, confirmed by `git diff` before commit.

## Questions

- None.

## Owner steps left

1. Review the test diff (two test files).
2. Merge with `scripts/merge-pr-on-green.sh` once CI is green. No push or PR was made by the executor.
