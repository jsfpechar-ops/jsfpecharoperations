# 0819: Records pages: real 32 px "?" next to the title, no footer fine print

Status: todo
Depends on: 0818 | Branch: claude/project-thread-v4nqi5 (main checkout, do NOT commit; the orchestrator commits)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Orchestrator screenshots after 0818 (`/mnt/project-files/records-pages/*.png`, rich-host fixture) still show: (a) on `/stay-fees` 1280 the help is a ~10 px icon plus a chevron, not a 32 px round "?" with no chevron; (b) on `/housebook` 390 there is no "?" beside the h1 (a "How does this work?" box sits inside the yellow notice instead; the notice itself is fixture-only, leave it); (c) `/housebook` shows the footer line "1 entries. Exports use the current filter." (fine print, and wrong plural). Fix on all four pages: submissions, invoices, housebook, stay-fees.

## 2. Context

0816/0818 rules live in `App/app/static/app2.css` (`.head-title-row`, `details.stays-how`, block `/* 0818 ... */`). Measure the summary and its svg with one Playwright snippet at 390 and 1280; the selector probably misses the page's details class or the icon size attribute wins. Look at how the help disclosure is rendered on phone (< 1024) in each template.

## 3. Files

`App/app/static/app2.css`, `App/app/templates/submissions.html`, `invoices.html`, `housebook.html`, `stay_fees.html`, i18n files (delete the footer string if unused), `App/app/templates/base.html` + `App/tests/static_versions.json` (key `20261102-0819`, then `.venv/bin/python tests/test_static_versions.py --write` from `App/`), tests asserting the footer text (update).

## 4. Steps

Measure, fix (a)-(c), run the commands, measure again.

## 5. Do not touch

Anything outside §3. No new dependency, colour or JS.

## 6. Commands (from `App/`, each `2>&1 | tail -30`)

1. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "invoices or housebook or submissions or stay_fees" tests/test_motion_browser.py tests/test_page_help_0277.py -q -rs --tb=short`
2. `.venv/bin/python -m pytest tests/test_static_versions.py tests/test_design_lint.py tests/test_design_reports.py tests/test_host_i18n.py tests/test_stay_fee_send_panel.py -q --tb=short`

## 7. Acceptance

- [ ] On all four pages at 390 and 1280: one visible round "?" 32x32 px (+-2), its centre within 4 px of the h1's vertical centre, no chevron, no text.
- [ ] No footer line under the housebook list.
- [ ] Commands 1-2: 0 failed, 0 skipped.

## 8. Stop and ask

Blocked if a fix fails twice, a file outside §3 needs a change, or 30 tool calls.

## 9. Report

`docs/tasks/0819-report.md`, 200 tokens at most. Do not commit or push.
