# 0797: Last older tests for the v2 Odeslání, Faktury, Domovní kniha pages

Status: todo
Depends on: 0795 (in branch) | Branch: claude/project-thread-v4nqi5 (main checkout, do NOT commit; the orchestrator commits)
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Fix 0795's "Still failing" items 1-3 (`docs/tasks/0795-report.md`). Item 4 (stay fees) belongs to 0796: do not touch it.

## 2. Context

Read `docs/tasks/0795-report.md` "Still failing".

## 3. Files

`App/tests/test_design_shell_browser.py`, `App/tests/test_host_filter_panels_browser.py`, `App/tests/test_host_controls_browser.py`, `App/app/templates/invoices.html` (month control only), `App/app/static/app2.css` (0792 and 0793 blocks only). Nothing else. Another executor edits `stay_fees.html` and the 0794 block at the same time.

## 4. Steps

1. `test_design_shell_browser.py::test_collapsed_rail_expands_again_with_the_same_button` and `::test_collapsed_account_menu_is_whole_inside_the_viewport`: decision: the v2 shell has no collapse button. Point these tests at an old-shell page that still has `button[data-sidebar-collapse]`: use `/payments` (held, stays on the old shell; the settings thread made the same change). Change only the URL the test loads.
2. `test_host_filter_panels_browser.py` (2 tests, `/invoices` month control, old markup, trigger 73 px vs wrapper 216 px at 360 px): make the invoices month control use the same v2 markup/classes as the month control on `/reservations` or `/housebook` (whichever is already v2; grep `month` in those templates). CSS only inside the `/* 0792 ... v2 */` block of `App/app/static/app2.css`. If the test asserts old-shell-only geometry that the v2 pages intentionally dropped, drop `/invoices` from its page list with the comment "v2, covered by 0710".
3. `test_host_controls_browser.py::test_host_interactions_geometry_copy_and_archive_controls`: housebook PDF dialog buttons 78.5 and 98.3 px wide must be equal: add one rule in the `/* 0793 ... v2 */` block (e.g. equal `flex:1 1 0` in the dialog's action row). Verify the selector with Playwright first.

## 5. Do not touch

Anything outside §3. No new dependency, colour or JS.

## 6. Commands (from `App/`, each `2>&1 | tail -30`)

1. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_design_shell_browser.py tests/test_host_filter_panels_browser.py tests/test_host_controls_browser.py -q -rs --tb=short`
2. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "invoices or housebook or submissions" -q -rs --tb=short`

## 7. Acceptance

- [ ] Command 1: the 5 named tests pass, 0 skipped (list any other failure by name; do not fix it).
- [ ] Command 2: 0 failed, 0 skipped.

## 8. Stop and ask

Blocked if a fix fails twice, a file outside §3 needs a change, or 30 tool calls.

## 9. Report

Report `docs/tasks/0797-report.md`, 300 tokens at most. Do not commit or push.
