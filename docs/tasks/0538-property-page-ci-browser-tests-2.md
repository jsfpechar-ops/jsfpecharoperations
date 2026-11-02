# 0538: property pages on v2: rest of the CI browser tests (follow-up to 0537)
Status: todo
Depends on: 0537 (this branch, report section "0537" in docs/tasks/0534-report.md) | Branch: claude/project-thread-819gyo
Executor: Haiku 5.5, two executors in parallel (part A and part B), each in its own worktree | Fits one session each: 30 tool calls, 60k tokens

## 1. Objective
Finish what 0537 left: point the remaining CI browser tests at the v2 properties list and property page markup. The orchestrator answered the 0537 stop questions in section 2.

## 2. Context
Orchestrator decisions on the 0537 stops:
- Door-code window title 14 px vs the test's 16 px: on v2, inner section headings are 14px/600 by the mockup (`summary b`, brief 0536 item 4). The threshold is stale. On v2 pages expect 14.
- Help tips on the property page: on v2 the `?` button is hidden inside `details` on purpose (0536 item 6). Rewrite the two property-page help tests to assert that the hint text is visible under its input. Keep the button tests for pages that still show the button.
- `test_host_list_cards_browser.py` below 1024 px: the table is hidden there on purpose and the phone cards show (0533). Below 1024 px, use `.props-phone` as the panel and `a.card.prop` as the row action, since the whole card is the link. From 1024 px, use `.props-card`.
- `test_host_wide_geometry_browser.py`: the v2 shell does not render the alert stack (`App/app/templates/base.html` line 69, `v2` skips `_host_alerts.html`; this is shared shell behaviour, not this branch). For v2 pages, expect `alertStack` to be None, the same way the dashboard branch of that test does, and note it. Properties lane: `.props-card` from 1024 px, `.props-phone` below. Investigate the fee-lane timeout and fix the selector if it points at old property-page markup.
- Old property-page markup and its replacement:
  - The tabs and views (`.property-tabs`, `data-property-view`) are now one page of `details.prop-sec#sec-<key>`. Use `?view=settings&section=lock`, which opens the lock section on the server.
  - The health and overview cards (`a.host-property-card`, `.host-property-grid`, `[data-leon-card]`) are now `aside.preview .pv` rows. The Leon row is a `.pv .r` that links to Leon.
  - The calendars count is now a Kalendáře row in the aside.

Part A (property page): test_door_code_window_browser.py (rest), test_host_help_browser.py, test_lock_navigation_browser.py, test_0199_phone_geometry_browser.py::test_lock (KeyError 'E'), test_0396_leon_opt_in_browser.py, test_0284_states_browser.py, test_0251_tablet_browser.py, test_onboarding_wizard_browser.py (overview-cards part only), test_0503_page_inits_once_browser.py, test_wp28_geometry.py.

Part B (list, geometry, shard 2): test_host_list_cards_browser.py, test_host_wide_geometry_browser.py, test_onboarding_followup_browser.py, test_0201_tabbar_safe_area_browser.py, test_0399_open_buttons_click_browser.py, test_0282_signature_dialog_browser.py, test_dashboard_calendar_browser.py, test_host_controls_browser.py.

For each file: run it alone with `--tb=line`. If a failure is about the properties list or property page markup, fix the selector or the assert. If it is about another page, list it as not ours with its failure line.

## 3. Files
Only the test files of your part. No app, template, CSS or JS change. Report: your own section "0538 part A" or "0538 part B" in `docs/tasks/0534-report.md`.

## 4. Steps
1. Fix your part's files, one commit per two or three files.
2. Run every file of your part again; ruff on tests. Commit the report section.

## 5. Do not touch
App code, templates, CSS, JS, the other part's files, the 0710 comparison logic. No new dependency.

## 6. Commands (from `App/` in your worktree)
`export UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, then `.venv/bin/python -m pytest <file> -q --tb=line -rfs -p no:cacheprovider 2>&1 | tail -30`; `.venv/bin/ruff check tests --select E9,F63,F7,F82,F401,F841 | tail -5`. Restore stray tracked PNGs.

## 7. Acceptance
Every file of your part passes with 0 skipped, apart from failures listed as not ours.

## 8. Stop and ask
Standing rule: tests that assert removed property-page or list markup may get new selectors or asserts (selector or assertion only; list each). A test may be deleted only if it tests nothing but removed markup; list it. Stop if a save/POST test fails, or a real layout bug shows on the new pages (report the numbers).

## 9. Report
Your section in `docs/tasks/0534-report.md`: status, tails, the section 8 list, the not-ours list. Stage by name, never `git add -A`; never commit `App/.venv`. Do not push. If you run out of calls, commit what passes and list what is left.
