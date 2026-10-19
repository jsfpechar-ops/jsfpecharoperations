# 0132 report

Status: blocked
Depends on: 0131 | Base commit: df8b842 | Branch: claude/project-thread-td6fpc | Head at start: 8744e8d

## Files changed
- App/app/templates/_components.html (steps 1-13)
- App/app/static/host2.css (step 14, appended hooks)
- docs/design/catalog.json (step 15)
- App/tests/test_first_property_step.py, test_stays_empty_workspace.py, test_properties_table_chips.py (step 10, empty-state regexes)
- App/tests/test_status_colours.py, test_deadline_after_reporting.py, test_host_quiet_dashboard_browser.py (step 16)

## Commands (last lines)
- Step 10: `pytest test_first_property_step.py test_stays_empty_workspace.py test_properties_table_chips.py` -> `56 passed, 1 warning`
- Step 16: `pytest test_status_colours.py test_deadline_after_reporting.py test_send_controls.py test_source_badge.py test_overhaul.py` -> `2 failed, 93 passed, 1 skipped`
  - FAILED test_status_colours.py::test_the_guest_card_keeps_its_amber_id_not_checked_pill (no pill for 'ID not checked')
  - FAILED test_status_colours.py::test_the_properties_list_setup_pill_is_amber_not_red (no pill containing 'to fix')
  - Cause: both pills are literal `class="pill amber"` in App/app/templates/reservation_detail.html (lines 224 and the setup pill), a page template, so the new PILL regex does not match them. Not fixed (page-owned).
  - SKIPPED test_source_badge.py:90 needs UBYHOST_SHOTS_DIR (screenshot test).
- design_lint: design lint: OK
- ruff: All checks passed!

## Section 7
- [ ] `grep -c 'class="pill'` in _components.html = 1 (one left, line in onboarding_* macro, out of scope per section 5)
- [ ] svg check: not run
- [ ] listed tests pass: NO (2 page-owned failures above)
- [ ] 390 px screenshot: not taken

## Remaining steps
- Step 17: create App/tests/test_design_shared_macros.py (not done)
- Step 18: commit of the test file (not done)
- Section 6 browser command (UBYHOST_REQUIRE_BROWSER=1, 0 skipped): not run
- Section 7 screenshot (390 px Stays list): not taken; shots dir ready at scratchpad shots/0132

## Deviations
- Steps 1-9 and 11-13 applied by an exact-anchor replacement script (abort on any miss, one commit per step). No anchor missed.
- Step 10: test_stays_empty_workspace.py line 224 (`<a class="btn" href="/apartments">`, the empty-state button) changed to `ui-btn ui-btn-secondary`, as step 10 allows.

## Questions
1. The two test_status_colours.py failures read literal page-template pills (reservation_detail.html). Brief section 3 says page-template pills move with their page briefs, but these tests are not listed there. Keep them failing until the page brief, or make PILL also accept `class="pill"` for now?

## Owner steps left
None.
