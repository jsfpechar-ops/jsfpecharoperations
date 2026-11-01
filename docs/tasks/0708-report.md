# 0708 report (executor: Haiku 5.5)
Status: blocked

## Files changed
None. No test file or route was edited, and no new test file was created.

## Commands
- Brief §6 command, first run: `tests/test_0706_v2_overview_browser.py` does not exist yet (it is part of this brief), so pytest exits 4 with "file or directory not found". Not run with it.
- Same set without the missing file, in background, log at `/tmp/0708_run1.log`: started, did not finish within the session. Output so far: `F...................................FFFFFFFFF` (first failures are in the `test_0705_v2_shell_browser.py` group). Full failure list not collected.
- The run was still going when the call budget ran out.

## Steps
- Steps 1-9 not done. Left: update each failing file under §2 rules (dashboard, needs-you, 0375, 0520, headcount, host_quiet, design_dashboard, query_budget, 0705 non-v2 test), create `tests/test_0706_v2_overview_browser.py`, check the batched-path test (§2), then run §6 with 0 skipped.

## Deviations
Done: none of the test edits. Left: all of §4 steps.
Monitor waits used many tool calls while the browser suite ran (about 10+ min), which cut the budget for editing.

## Questions
- None blocking. Next session should start from the full failure list (run the set in background and `grep -E "^(FAILED|ERROR)"` on the log), not from the first partial output.

## Owner steps left
- None. Nothing was pushed; no PR opened.

## Session 2 (executor Haiku 5.5, after 4cf4df6)
Commits: df8dc24 (queue_copy, empty, missing_banner, design, 0520), 60c593d (0250, calendar, 0375, welcome_back, workflow_strip, design btn), this report commit.

### Test files changed
- test_dashboard_queue_copy.py: the three seeded stays now arrive today (offset 0), so each gets a Dnes row. `_needs_action_heading` accepts `<h2 id=...>`. Needs-you lines are `div.card.needs-you-card-item` with one `class="btn` action. Current/completed section test is an absence check (0706). Rows check the arrival label instead of `dashboard-row-dates`. 14 passed.
- test_dashboard_empty.py: the empty-state copy, the calendar link, "Either the calendars have nothing booked" and the onboarding banner are absence checks (0706). 6 passed.
- test_dashboard_missing_banner.py: `_setup_lines` reads `div.card.needs-you-card-item`; action class `btn`; show-more is 4 cards before the fold (was 5), "Show 2 more". 5 passed.
- test_design_dashboard.py: header button is `class="btn" href="/reservations?new=1"`; refresh hooks are absence checks; `needs-you` becomes `data-needs-you-card`. 1 of 3 passes (see Remaining).
- test_0520_overview_today.py: Dnes table found by `<thead><tr><th>` up to `</table>`; order check uses `data-needs-you-card`, `class="card cal"`, and the `<h2>` after the calendar. 5 passed.
- test_0250_property_cards.py: pill helper matches the `host-property-card-open-text` span, because the Guest links card renders its pill as an `<a>` (6 spans + 1 link = 7). 3 passed.
- test_dashboard_calendar.py: the JS calendar test opens `/?lang=en&cal_view=calendar`. 34 passed.
- test_0375_needs_you_and_open.py: asserts `overview_card(line, loop.first)`, `class="ic"`, `if first else ' ghost'`. 2 passed.
- test_welcome_back_0275.py: the welcome-back line is an absence check on `/`. The dismiss POST block was DELETED (the banner is gone from `/`; the POST endpoint is not tested here any more). 6 passed.
- test_workflow_strip_0232.py: the strip on `/` is an absence check; the strip on `/guide` is still tested by its own test. 3 passed.
- test_admin_funnel.py: no edit. Passes alone (9 passed). It fails in the combined run (see Remaining).
- test_needs_you_dashboard_0241.py: no edit (see Remaining).

Deleted assertions: only the welcome-back dismiss POST block (test_welcome_back_0275.py::test_dashboard_shows_and_dismiss_clears). Everything else is an absence check or a changed selector. No test skipped or xfailed. No app code changed.

### Final run
Command from the brief (browser files excluded by the glob, host_geometry not excluded):
`9 failed, 144 passed, 4627 deselected in 43.22s`

### Remaining (not fixed; app or decision needed)
1. test_design_dashboard.py::test_no_raw_style_or_pill_in_the_dashboard_template: dashboard.html has inline `style="..."` (e.g. the needs-you wrappers, `.cal` margins, `bar.style`). Decision: move these to CSS (template/CSS, 0707) or relax the rule.
2. test_design_dashboard.py::test_the_zero_state_keeps_the_welcome_card_and_one_h1 and test_signed_in_chrome.py::test_the_zero_state_overview_has_one_h1: the empty `/` has 2 `<h1>` (the head h1 plus the onboarding welcome section). App fix needed.
3. test_needs_you_dashboard_0241.py::test_alerts_show_once...: `_host_alerts.html` (`data-host-alerts`) is still rendered on `/`, so the alert shows twice (stack and card). Decision: hide the stack on `/`, which is an app change.
4. test_signed_in_chrome.py::test_dashboard_opens_with_the_what_needs_you_card: `ValueError: substring not found` at line 215, not investigated.
5. test_endtoend.py::test_08_dashboard_shows_the_stay_as_awaiting_the_guest: expects 'Vinohrady 1' on `/`. v2 Dnes shows only today's stays, so this awaiting stay is no longer listed. Decision: assert on `/reservations` instead, or accept the change.
6. test_query_budget.py::test_batched_pages_render_exactly_as_the_per_stay_path: the dashboard differs between the batched and per-stay paths (diff not printed yet). The brief's batched-path finding is still open.
7. test_host_geometry.py::test_dashboard_actions_share_height_and_gap: browser test that was run here (it is in the brief command and was not excluded). Playwright `wait_for_selector` timed out after 30 s. Not investigated; check it in the browser run.
8. test_admin_funnel.py::test_overview_cards_and_bars: passes alone, fails in the combined run (`assert 33 = ...`). Probably state left by an earlier test. Not investigated.

### Owner steps left
- None. Nothing pushed; no PR.
