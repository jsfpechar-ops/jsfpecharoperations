# 2049 report: host parity fixes

Status: review
Branch: claude/nice-hawking-fw98ct (worktree agent-ac767a790c15d7293), not pushed.

## Commits
- 84fb4ca 2049 step 1: Czech and English guest-question copy matches Python
- e5883a1 2049 step 2: admin-customer back arrow uses Python's 20px size (includes gofmt fix)
- 8ec7f33 2049 step 3: harness normalises the Go QR link base to BASE
- 4b0fdab 2049 step 4: dev-ui marked ACCEPTED in parity harness

## Files changed
- go/internal/web/guest/leon_questions.go (12 strings)
- go/internal/hostweb/layout/layout.go (BackIconPx field, backIconPx helper)
- go/internal/hostweb/layout/shell.html (icon size from BackIconPx)
- go/internal/web/customers/detail.go (BackIconPx: 20)
- scripts/e2e/page_parity_visual.py (re import, 127.0.0.1 port normalised to BASE)
- scripts/e2e/parity_cases.py (dev-ui ACCEPTED)
- docs/tasks/2049-report.md

## Commands
- `go test ./internal/web/guest/...` : ok
- `gofmt -l internal/hostweb/layout/ internal/web/customers/` : clean after gofmt
- `go build ./...` : ok
- `go test ./internal/hostweb/layout/... ./internal/web/customers/...` : ok, goldens unchanged
- `python3 -m py_compile` on both harness files : ok
- `App/.venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x -rs` : 4 passed, 0 skipped
- Step 5 parity rerun (page_parity_visual.py) : pending (orchestrator)
- `tests/test_go_pages_layout_lint_browser.py` : not run in this session (brief names it; the user-named test was run)

## Checklist
- [x] 12 strings in step 1 changed, no keys added
- [x] go test ./internal/web/guest/... green
- [x] layout and customers Go tests green, goldens untouched
- [x] harness compiles
- [ ] parity: pending (orchestrator)
- [x] layout lint browser test green, 0 skipped (4 passed)

## Screenshots
- Layout lint run wrote shots under scratchpad 2049-shots/layout-lint/.
- guest-questions-390.png (en, host Guest questions empty state): no layout issue. Shows "No questions yet / Your reply appears on the guide." and the Guide button. The changed strings (Dismiss, Sent, Card, cs texts) do not appear on this view.
- admin-customer 390/768/1280: NOT produced by this run. The back arrow change (20 px) needs the parity rerun (orchestrator) to produce admin-customer screenshots.

## Deviations
- Step 2 first commit had an unformatted layout.go; amended into commit e5883a1 after gofmt.
- Step 5 parity rerun skipped per owner exception (orchestrator runs it).
- Brief lists /tmp/shots; screenshots were written to the scratchpad path given in the task.

## Questions
- None new. The vi finding stays with the owner (brief section 2).

## Owner steps left
- Orchestrator: run page_parity_visual.py for the 9 cases, confirm 27 rows identical/invisible with dev-ui accepted, and view admin-customer 390/768/1280.
