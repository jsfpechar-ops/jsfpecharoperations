# 1421 report (executor, Haiku 5.5)

Status: review. One big PR mode: commits on the current branch, nothing pushed, no PR opened.

## Files changed (step 1 commit `d606a4244`)
- go/internal/web/invoices/draft.go (create)
- go/internal/web/invoices/draft_test.go (create)
- go/internal/web/invoices/testdata/draft_golden.json (create)
- App/scripts/invoices_golden.py (create)
- App/tests/test_go_invoices.py (create)
- docs/tasks/1421-report.md (create), docs/tasks/1421-go-invoices-draft.md (Status line only)

## Commands (last lines)
- sha256sum of the 5 files: all 5 match §2.
- gofmt -l / go build ./... / go vet: no output.
- go test ./internal/web/invoices/... ./cmd/ubyhost-web/...: `ok` for both packages. No `--- SKIP` lines. No database URL was set; the brief says these tests use none.
- go test -v -run 'TestBuildDraftMatchesPython|TestStayProblemMatchesPython': 57 `--- PASS` lines.
- python3 scripts/context_lint.py: `context lint: OK` (warnings only, not from this brief).

## §7 acceptance
- [x] 5 sha256 values match
- [x] gofmt, build, vet clean
- [x] go test ok for both packages, no SKIP
- [x] 57 PASS lines
- [ ] Golden --check and pytest: CI only (see Deviations)
- [x] Step commits show only §3 paths
- [x] Nothing pushed, no branch created

## Deviations
- Step 0 first ran before the worktree was reset: `go/internal/web/invoices` did not exist. After `git reset --hard claude/happy-babbage-2zeeam` the dependency check passed (handlers.go, dec.go present).
- `App/.venv` does not exist, so `invoices_golden.py --check` and `pytest tests/test_go_invoices.py` were skipped per the brief. CI only.
- `go test` was run without `UBYHOST_TEST_DATABASE_URL`; no PostgreSQL was started on port 5603.

## Questions
None.

## Owner steps left
None.
