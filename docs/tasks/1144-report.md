# Report 1144: claimed_at stamped at the INSERT

Status: blocked

## Files changed (steps 1 to 3)

```
go/internal/ubyport/claim.go      | 9 +++++++--
go/internal/ubyport/claim_test.go | 31 +++++++++++++++++++++++++++++++
```

## Commands run

1. Step 1 `cd go && go build ./...`: exit 0, no output after the module download lines.
2. Step 2 `cd go && go vet ./internal/ubyport/`: exit 0, no output.
3. Step 3 `UBYHOST_TEST_DATABASE_URL=postgres://uby:uby@localhost:5432/ubytest go test ./internal/ubyport/ -run 'TestClaimedAtIsStampedAtInsert' -count=1 -v`:
   ```
   === RUN   TestClaimedAtIsStampedAtInsertNotBeforeLockWaits
       claim_test.go:418: admin connect failed
   --- FAIL: TestClaimedAtIsStampedAtInsertNotBeforeLockWaits (0.01s)
   ```
   Cause: Postgres is up (`pg_isready` accepts connections), but `psql postgres://uby:uby@localhost:5432/ubytest` returns `FATAL: password authentication failed for user "uby"`. The test cannot reach the database, so it is not a logic failure.
4. Step 4 revert-bite: NOT RUN (blocked by the same connection failure).
5. §6 commands 1 to 4: NOT RUN.

## §7 acceptance

- [x] `git diff` lists only `claim.go` and `claim_test.go` (plus this report).
- [x] `grep -n 'claimedNow'` shows two lines (99, 103).
- [ ] New test PASSES with the fix and FAILS with the INSERT argument reverted: not verified.
- [ ] Commands 1 and 2 pass; command 3 prints `0`: not verified.

## Deviations

- Paths: the brief names `/home/user/jsfpecharoperations/go`; all work used `/home/user/wt-1144/go` as the orchestrator instructed.
- Step 3 was committed although its test has not yet run against a database (the code compiles: the test ran and reached the DB call).
- Done: steps 1 to 3 (code applied as written, committed). Left: step 4 (revert-bite), §6 commands 1 to 4, §7 ticks.

## Questions

- The `uby` password in the brief's `UBYHOST_TEST_DATABASE_URL` is rejected by the local Postgres. Which credentials should the test use?

## Owner steps left

1. Provide a working `UBYHOST_TEST_DATABASE_URL` for the executor (or fix the `uby` role password on the local cluster), then rerun the executor from step 4.
2. When the report says `review`, open the PR and merge only with `scripts/merge-pr-on-green.sh <PR number>`.
