# 1222-fix-1 report

Status: review

## Files changed
- go/internal/billingjob/account.go (day10 added after parseDate)
- go/internal/billingjob/run.go (parseDate check, day10 for both dates)
- go/internal/billingjob/apartments.go, trial.go, dunning.go (day10)
- go/internal/billingjob/unit_test.go (TestDay10)
- App/scripts/billing_run_golden.py, App/scripts/billing_invoice_golden.py (forced temp DB, Postgres URL popped)
- docs/tasks/1222-fix-1-report.md

## Commands (last lines of output)
Go (gofmt, vet, build exit 0):
    ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billingjob	2.087s
    ok  	github.com/jsfpechar-ops/jsfpecharoperations/go/cmd/ubyhost-web	0.007s

Golden scripts:
    wrote /home/user/jsfpecharoperations/go/internal/billingjob/testdata/invoicer.golden.json
    ValueError: buyer_missing
    wrote /home/user/jsfpecharoperations/go/internal/billingjob/testdata/run.golden.json
git status testdata: no output (unchanged).

## Section 7
- [x] §6 passes, no FAIL or SKIP lines, goldens unchanged
- [x] Step 4 grep: only day10 and parseDate code lines, plus three comment hits
- [x] git diff --stat 47262ae lists only §3 files and the brief

## Deviations
- Step 4 grep also matches comments: account.go:91, account.go:103, run.go:242 (pre-existing, untouched).
- Not pushed, no PR opened (owner instruction: commit, do not push).
- Commits: "1222 step 1" to "1222 step 6", then "1222-fix-1" for the report.

## Questions
- run golden prints "ValueError: buyer_missing" before "wrote"; exit code 0. Expected? Not investigated.
