# 2053 report: Go guest questions list parity

Status: review (parity step pending, orchestrator)
Branch: claude/nice-hawking-fw98ct (worktree agent-a476ac187200974d5), not pushed.

## Commits

- 120bcab 2053 step 2: `handoffRow.Day()` helper (wraps `lqDay(CreatedAt)`), in `go/internal/web/guest/leon_questions.go`
- 9af60f7 2053 step 3: list rows show message text, date and stay/QR sub line, Urgent/Unread (open only) and one state badge, in `go/internal/web/guest/templates/leon_questions.tmpl`
- 4183d89 2053 step 4: seed rows 7804 and 7904, new `TestHandoffListMatchesPythonRows`, in `go/internal/web/guest/leon_questions_db_test.go`
- 382757f 2053 steps 5-6: seed rows `question_urgent_unread` and `question_dismissed` in `scripts/e2e/seed_parity_extra.py`; two parity cases in `scripts/e2e/parity_cases.py`
- this commit: `docs/tasks/2053-report.md`

## Checks

- Step 1: i18n keys in `App/app/host_i18n.py` and `lqI18n` in Go match (en and cs). Checked.
- `go build ./internal/web/guest/` ok. `gofmt -l` clean.
- `go test ./internal/web/guest/... -count=1` with test DB: `ok` (4.5 s).
- Layout lint browser: `App/tests/test_go_pages_layout_lint_browser.py`: `6 passed, 1 warning in 68.77s`, 0 skipped.
- `python3 scripts/context_lint.py`: `context lint: OK` (warning: 24 App/ commits after last status.md update; orchestrator updates status).
- Parity (step 7): pending (orchestrator). Not run by executor, per the orchestrator exception.
- Screenshots (rule 7/10): pending (orchestrator, with the parity run). No 390/768/1280 images were opened by the executor.

## Deviations

- Row order in the new test: the brief expected 7904 before 7901. The Go SQL and `App/app/guest_handoff.py` share the same ORDER BY (open first, urgent desc, open by id ASC; then closed by id DESC). That gives 7901, 7904, 7903, 7902. I changed the test expectation to match the SQL. No SQL changed.

## Questions

- None open.

## Owner steps left

- None. Orchestrator: run parity step 7 (`PARITY_GROUP=F` cases `guide-questions-full-*`, `guide-question-urgent-unread-*`, `guide-question-dismissed-*`), then open the 390/768/1280 list screenshots and record them in the PR.
