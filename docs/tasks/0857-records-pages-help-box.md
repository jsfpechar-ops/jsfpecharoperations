# 0857: Records pages: no white box around the title "?"

Status: todo
Depends on: 0855 | Branch: claude/project-thread-v4nqi5 (main checkout, do NOT commit; the orchestrator commits)
Executor: Haiku 5.5 | Fits one session: 20 tool calls, 40k tokens

## 1. Objective

Screenshots `/mnt/project-files/records-pages/housebook-390.png` and `stay_fees-1280.png` show the help "?" beside the h1 drawn inside a white rounded square with a border and shadow (about 44 px), with a smaller grey circle inside. Josef wants only the 32 px grey round "?" (like the mockup's round icon buttons), nothing around it. Keep the 44 px transparent tap area from 0855.

## 2. Context

0855 rules: `App/app/static/app2.css` lines ~1198-1202 (`.head-title-row>details.stays-how .ui-how-toggle` and `::before`). Some other rule (likely on `details.ui-how`, `details.stays-how`, `summary`, or a shared card/`details` rule in app2.css) paints the white box. Find it with one Playwright probe on /housebook at 390 and /stay-fees at 1280 (computed background, border, box-shadow of the details, the summary and their parents up to `.head-title-row`), using the rich-host fixture pattern from `tests/test_0710_v2_mockup_match_browser.py` in a temporary test file that you delete afterwards.

## 3. Files

`App/app/static/app2.css` (add the override inside the 0855 lines, scoped to `.head-title-row>details.stays-how`), `App/app/templates/base.html` (`app2.css?v=20261102-0857`), then `.venv/bin/python tests/test_static_versions.py --write` from `App/`.

## 4. Steps

Probe, fix, run the commands, probe again.

## 5. Do not touch

Anything outside §3. No new dependency, colour or JS.

## 6. Commands (from `App/`, each `2>&1 | tail -30`)

`UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "invoices or housebook or submissions or stay_fees" tests/test_page_help_0277.py -q -rs --tb=short` and `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_design_lint.py -q --tb=short`

## 7. Acceptance

- [ ] On all four pages (submissions, invoices, housebook, stay-fees) at 390 and 1280 the details and summary have transparent background, no border, no box-shadow; only the 32 px grey circle is visible.
- [ ] Commands: 0 failed, 0 skipped.

## 8. Stop and ask

Blocked if a fix fails twice or a file outside §3 needs a change.

## 9. Report

`docs/tasks/0857-report.md`, 150 tokens at most. Do not commit or push.
