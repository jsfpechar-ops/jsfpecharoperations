# 1650 report: Go twin of sample_airbnb_ics

Status: review

## Files changed

- `go/internal/ical/sample.go` (create, sha256 3dcab8c0... OK)
- `go/internal/ical/sample_test.go` (create, sha256 45f36963... OK)
- `go/internal/ical/testdata/sample_airbnb_20261114.golden` (create, sha256 b16aaad5... OK, 75 CRLF lines)
- `docs/tasks/1650-report.md` (this file)

## Commands (last 5 lines of output)

Step 0 checks: all as expected (`No such file`, no grep hit, 3 sidecars, 1 Python def).

Step 1 hash check: all three hashes match. `sha256sum` ran without `-c` (see Deviations).

Step 2, gofmt / build / vet: no output.

Step 2, Sample tests:
```
--- PASS: TestSampleAirbnbICSMatchesPython (0.00s)
--- PASS: TestSampleAirbnbICSYearEnd (0.00s)
ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/ical	0.005s
```

Step 2, full package without database: `ok ... go/internal/ical 0.052s`, with 38 SKIP (all `UBYHOST_TEST_DATABASE_URL is not set`).

Step 2, full package with local PostgreSQL 16 on port 55501 (data dir /var/tmp/pg1650): 96 PASS, 0 SKIP, 0 FAIL, exit 0. Repeated 3 more times, same result.

Step 3, `python3 scripts/context_lint.py`: `context lint: OK` (WARN lines are pre-existing).

## Section 7 acceptance

- [x] sha256 OK for all 3 files; 75 CRLF lines in the golden file
- [x] Step 2 printed nothing before the PASS lines
- [ ] `git diff --stat main...HEAD`: not run, because the branch base is go-demo-ports, not main. The changed paths are the §3 files only.

## Deviations

- Brief started with `git reset --hard go-demo-ports` as the first command. The worktree was clean and had no commits beyond go-demo-ports, so nothing was lost.
- Step 1 `sha256sum -c` was refused by the sandbox as a compound command. I ran the copy and `sha256sum` as separate commands and compared the hashes by eye. All three match.
- One DB run (the first with `-rs`) printed FAIL with no test name and finished in 0.004s. Four later runs with identical settings passed. Cause not determined.
- PostgreSQL was started for this run with initdb and pg_ctl as the postgres user, on port 55501. The server is stopped at the end of the run.
- Executor doc says to open one PR. The orchestrator said not to, so no PR was opened.
- Commits are on the worktree branch only. No push.

## Questions

None.

## Owner steps left

None. No route uses the function yet.
