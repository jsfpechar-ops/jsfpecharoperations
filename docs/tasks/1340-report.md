# 1340 report: Go billing engine

Status: review

## 1. Files changed (`git diff --stat a83df54 HEAD`, before step 6)

- App/scripts/billing_engine_golden.py (new, 558 lines)
- App/tests/test_billing_engine_golden.py (new, 25 lines)
- go/internal/billing/engine.go, engine_test.go, errors.go, invoicer.go, order.go (new)
- go/internal/billing/testdata/engine_golden.json (new, 9501 lines)
- docs/tasks/1340-payload.txt removed in step 6 (`git rm`), so not in the final diff
- docs/tasks/1340-report.md (this file)

Not touched: quote.go, snapshot.go, go.mod, go.sum, App/app/*, docs/context/*.

## 2. Commands (last lines of output)

- Step 1 extractor: `ok` x7, then `files written: 7 (expected 7)`. sha256 prefixes match the table.
- Step 2 `gofmt -l` and `go vet`: no output.
- Step 3 golden script: `wrote .../engine_golden.json`; sha256 `5c43a6d54b315a31375b06b18bf72e1cdf467e15860c94fed2992d60893d6f63`.
- Step 4 `go test` with DB URL: `ok  github.com/jsfpechar-ops/jsfpecharoperations/go/internal/billing  17.495s`.
- Step 4 `go test` without DB URL (-v): PASS for pure tests, SKIP for TestEngineMatchesPython, TestPlaceSendFailureKeepsOrder, TestAuditActorContext, TestWriteMonthSnapshotMatchesFixturePrices; ends `ok ... 0.014s`.
- Step 5 golden rerun: `wrote ...`; `git status --porcelain go/internal/billing/testdata` empty.
- Step 5 pytest: `1 passed in 0.48s`.
- Step 5 context_lint: `next free: task 1341 | migration 0046`, `context lint: OK` (WARN lines are other briefs).
- PostgreSQL 16 on port 54340 stopped after step 5.

## 3. Acceptance (section 7)

- [x] Step 1 seven ok lines
- [x] gofmt and vet empty
- [x] go test ok with and without the database URL (sub-test count not separately counted)
- [x] golden sha256 matches step 3; testdata porcelain empty after rerun
- [x] pytest passes; context_lint OK
- [x] Diff: only section 3 files after step 6 (quote.go and snapshot.go untouched)

## 4. Deviations

- Commit messages follow the brief (`1340 step k`), with the two trailer lines from the task instructions (Opus 5.5 co-author).
- No push and no draft PR: the instruction for this run said do not push. The orchestrator opens the PR.
- The payload file was read only by the step 1 extractor script, never printed.

## 5. Questions

None.

## 6. Owner steps left

1. Orchestrator pushes `task/1340-go-billing-pages` and opens a DRAFT PR.
2. Merge when CI is green (`scripts/merge-pr-on-green.sh`).

## Review (Opus) follow-ups

For the page brief:

- Go adds `ORDER BY id` to the open-invoice reissue query; Python has none. Harmless.
- Place check-then-update is not atomic: a double submit can issue two invoices, same as Python.
- A zero `today` means local now.
- CI has no guard that fails when the Go DB tests skip.
