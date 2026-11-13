# 1341 report

Status: review

## Files changed
Nine new files from the payload (go/internal/web/billing/{pyutil,admin,bankimport,analytics,page,golden_test,admin_test}.go, go/internal/web/billing/testdata/billing_admin_golden.json, App/scripts/billing_admin_golden.py, App/tests/test_billing_admin_golden.py). Payload file removed in step 6. Nothing outside §3 changed.

## Commands (last lines)
- Step 1 extractor: 9 `ok` lines, `files written: 9 (expected 9)`. sha256 prefixes match §4 table.
- Step 2 gofmt and go vet: no output.
- Step 3 golden script: `wrote .../billing_admin_golden.json`; sha256 `cd60ba1ab98968e8...` (matches).
- Step 4 go test with DB: `--- PASS` TestAdminReadSideMatchesPython, TestPureHelpersMatchPython, TestParseMatchesPython, TestInvoiceVS; `ok`.
- Step 4 go test without DB: `--- SKIP` TestAdminReadSideMatchesPython, three PASS; `ok`.
- Step 5 golden rerun: `wrote ...`; git status on testdata empty.
- Step 5 pytest: `1 passed in 0.69s`.
- Step 5 context_lint: `next free: task 1342 | migration 0046`, `context lint: OK` (WARN lines only, about other briefs).
- PostgreSQL on 54341 stopped; /var/tmp/pg1341 removed.

## Acceptance (§7)
- [x] Step 1 nine ok lines
- [x] gofmt and vet silent
- [x] go test ok with DB (four pass) and without (one skip)
- [x] golden sha256 matches; testdata status empty
- [x] pytest passes; lint OK
- [ ] `git diff --stat main...HEAD` check: not run (no push, main not fetched in worktree)
- [x] PostgreSQL stopped, directory gone

## Deviations
Done: steps 1 to 6. Did not push and did not open the draft PR (executor rules: no push; the coordinator asked for commit only). The orchestrator must push and open the draft PR.

## Questions
None.

## Owner steps left
1. Orchestrator: push `task/1341-go-billing-admin-data` and open a DRAFT PR (body: nothing routed or called yet; no new outbound request, no new personal-data field, no new dependency).
2. Owner: after CI is green, merge with `scripts/merge-pr-on-green.sh <PR number>`.

## Review follow-ups

1341-fix-1 fixed the CSV reader (own state machine copied from CPython's csv module) and year 0 in `validDate`. Known differences left, none on a path used yet:

3. `csvAmount` with `inf`: Go skips the row, Python fails the whole upload with an error.
4. `Trend(months <= 0)` differs from Python's list slicing; the page always passes 12.
5. Unicode digits in the `\d` regexes of Python are not matched by the Go `[0-9]` ones, and `"invoice": null` in a buyer snapshot reads differently (`_buyer`).
