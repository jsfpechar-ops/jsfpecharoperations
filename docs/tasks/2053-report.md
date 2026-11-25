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

## Parity (orchestrator step)

Command (repo root, after `source scripts/e2e/parity_env.sh`): `PARITY_GROUP=F PARITY_ONLY=guide-questions-full-cs,guide-questions-full-en,guide-question-urgent-unread-cs,guide-question-urgent-unread-en,guide-question-dismissed-cs,guide-question-dismissed-en,guide-question-cs,guide-question-en,guide-question-answered-cs,guide-question-answered-en App/.venv/bin/python scripts/e2e/page_parity_visual.py 2>&1 | tail -30`. Last line: `{"rows": 30, "verdicts": {"identical": 30, "invisible": 0, "visible": 0, "accepted": 0, "error": 0}}`. Report: `/var/tmp/parity-visual/report-F.md`.

Per row (cs and en, 390/768/1280 each): all identical, diff_px=0.
- guide-questions-full (list): identical
- guide-question: identical
- guide-question-answered: identical
- guide-question-urgent-unread: identical
- guide-question-dismissed: identical

Go status 200 on every detail request and on /sw.js and /offline in the log.

Visible rows: none, so no row side PNG was needed. The list was checked at 390, 768 and 1280 in en (side PNGs, Python left, Go right):
- 390: both sides show the same five rows in the same order. Question text wraps onto a second line with the stay link beneath. State badges stack (Urgent, Not read by Leon (AI), Waiting on separate lines for the hot-water row). The fixed chat button sits over the last row's right edge.
- 768: both sides show the same five rows. Date and stay link follow the question on one line, and badges sit in the State column, wrapping only on the hot-water row.
- 1280: both sides show the same five rows in the same order, with the sidebar, the banner and the list card. Badges stay on one line per row except the hot-water row.

PNG folder: `/var/tmp/parity-visual/_2053/` (list side PNGs at 390, 768, 1280).
