# 0241 report

Status: review

## Commits (branch claude/project-thread-0io75h, not pushed, no PR)

- 0241 step 1 (admin.py context keys): import OK, no output.
- 0241 step 2 (base.html stack condition): no test in brief.
- 0241 step 3 (dashboard.html replaced): `23 passed, 1 warning in 2.69s`
- 0241 step 4 (needs_you.py wording): `19 passed, 1 warning in 2.14s`
- 0241 step 5 (test_alert_stack.py sed): grep count `7`.
- 0241 step 6 (test_dashboard_queue_copy.py): `27 passed, 1 warning in 2.77s`
- 0241 step 7 (test_host_language.py): `18 passed, 1 warning in 2.25s`
- 0241 step 8 (test_dashboard_missing_banner.py replaced): `18 passed, 1 warning in 2.50s`
- 0241 step 9 (two small edits plus coordinator's deadline-test edit): `28 passed, 1 warning in 2.84s`
- 0241 step 10 (test_signed_in_chrome.py): `29 passed, 1 warning in 2.70s`
- 0241 step 11 (new test_needs_you_dashboard_0241.py): `15 passed, 1 warning in 2.29s`
- 0241 step 12 (section 10 follow-up, three test files): `57 passed, 1 warning in 6.51s`. Clears the three real command-2 failures; the test_host_ux_acceptance failures are Chromium-not-found and not part of this follow-up.
- 0241 report commit (this file).

## §6 results

1. Command 1: `99 passed, 1 warning in 5.78s`. Acceptance §7 met.
2. Command 2 (files matching the old `/?lang` pattern, run with test_alert_stack first): `8 failed, 569 passed, 3 warnings in 48.95s`. Listed, not fixed:
   - tests/test_endtoend.py::test_24_an_incomplete_stay_past_the_deadline_raises_an_alert
   - tests/test_host_ux_acceptance.py::test_every_page_family_fits_every_width_language_and_rail_state
   - tests/test_host_ux_acceptance.py::test_page_families_through_rail_cards_search_and_back
   - tests/test_host_ux_acceptance.py::test_keyboard_reaches_rail_tabs_and_editor_with_visible_focus
   - tests/test_host_ux_acceptance.py::test_without_javascript_tabs_reload_and_the_shared_editors_save
   - tests/test_overview_headcount.py::test_a_known_headcount_shows_the_count
   - tests/test_status_colours.py::test_the_stay_pill_is_blue_on_the_work_queue
   - tests/test_status_colours.py::test_the_stay_pill_is_czech_for_a_czech_host (line 152: no pill reading "Ready to report")
   No "no such table" errors. Line numbers for the other seven were cut by tail; rerun with `--tb=line` to get them.
3. Lint: `context lint: OK`. Warnings only (existing briefs name the same files; 25 commits after last status.md update).

## Deviations

- Step 9: the deadline test failed on the dashboard (no "overdue by" badge; the card shows the red overdue line). Coordinator approved changing that test. Applied exactly as sent; then passed.
- Step 10: `test_dashboard_opens_with_the_what_needs_you_card` asserted the card comes before `data-calendar`, but the page header's `data-calendar-add` button sits above the card. Changed the anchor to `id="calendar"` (the calendar section). Intent unchanged.
- Step 3 was committed with test_alert_stack passing (the brief allowed a failure there).
- Browser tests (`*_browser.py`) were not run or edited.

## Questions

None.

## Owner steps left

None. Push and PR are not done (per brief). Owner decides on the 8 command-2 failures.
