# 0850: CI browser failures left on the v2 records pages (Faktury, Domovní kniha)

Status: todo
Depends on: 0797 (in checkout) | Branch: claude/project-thread-v4nqi5 (main checkout, do NOT commit; the orchestrator commits)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Fix the CI browser failures of PR #707 (run 41446464644) that are not stay fees (0796) and not 0797's items. Each is a real v2 regression on `/invoices` or `/housebook`: fix the page, not the test, unless the test asserts old-shell markup the v2 page intentionally dropped (then update the selector, comment "v2, 0792/0793").

## 2. Context

Failures (CI messages):
1. `tests/test_0252_touch_sweep_browser.py:103`: at ipad1024 `/housebook` the row "Open" buttons are `outside` (their box leaves the scroll container / viewport).
2. `tests/test_a11y_guard_browser.py:164`: `/invoices` at 1280 `focus-not-visible` on `input#filter-month` (outline none) and on the `.card.stays-desk` scroll div (focusable, no focus ring). Give both the shared v2 focus ring (grep `focus-visible` in app2.css for the token used).
3. `tests/test_host_button_contrast_browser.py::test_empty_state_action_is_centred_under_its_text`: `/invoices` empty state: action centre 420.5 px off the text centre. Centre the action under the text (look how `.ui-empty` is done on `/reservations`).
4. `tests/test_host_list_page_layout_browser.py:158` `test_tabs_are_links_that_mark_the_open_page`: `assert 'data-sub-tabs' in html`: find which page entry (print it); if it is invoices/housebook/submissions, the v2 head buttons replaced the tab strip: drop that page from the test's list with the comment above. If it is `fees`, skip it (0796 owns it).
5. `tests/test_dev_ui_browser.py::test_catalog_page_fits_the_viewport_and_the_coral_budget[390|1280]`: timeout waiting for `details.ui-how summary`. Find what the catalog page renders now and why (`grep -n "ui-how" App/tests/test_dev_ui_browser.py App/app/templates/dev_ui*.html`). Fix only if one of this branch's files caused it (`git diff origin/main --stat`); otherwise report.
6. `tests/test_motion_browser.py:139` `test_pages_without_javascript_stay_still`: find which page fails; fix if it is one of the four records pages.

## 3. Files

`App/app/templates/invoices.html`, `housebook.html`, `submissions.html`; `App/app/static/app2.css` (0791, 0792, 0793 blocks only); the six test files above (selector/page-list updates only, rule in §1). Not `stay_fees.html` or the 0794 block (0796 runs at the same time).

## 4. Steps

Reproduce each with `-k` first, fix, rerun. One Playwright measuring script in `/tmp/claude-0/scratch-0850/` if needed.

## 5. Do not touch

Anything outside §3. No new dependency, colour or JS.

## 6. Commands (from `App/`, each `2>&1 | tail -30`)

`UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0252_touch_sweep_browser.py tests/test_a11y_guard_browser.py tests/test_host_button_contrast_browser.py tests/test_host_list_page_layout_browser.py tests/test_dev_ui_browser.py tests/test_motion_browser.py -q -rs --tb=short`

## 7. Acceptance

- [ ] The command: no failure except entries on `fees`/`stay-fees` (list them), 0 skipped.

## 8. Stop and ask

Blocked if a fix fails twice, a file outside §3 needs a change, or 30 tool calls.

## 9. Report

`docs/tasks/0850-report.md`, 300 tokens at most. Do not commit or push.
