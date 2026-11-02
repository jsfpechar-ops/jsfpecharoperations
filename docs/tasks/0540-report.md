# 0540 report
Status: review
Done: steps 1 to 6 and addendum 1 and 2.

Commits: 97d8d65 (step 1), f9c1220 (step 2), f284668 (step 3), 9666920 (step 4), ca1bd61 (step 5), step 6 (this commit, see git log).

Tests (final):
- Set 1 (`tests/test_0540_cleaning_tables.py tests/test_cleaning.py tests/test_design_cleaning.py tests/test_copy_cleanup.py tests/test_no_em_dashes.py`): 60 passed.
- Set 2 (`tests/test_cleaning_browser.py tests/test_design_guardrails_browser.py -rs`): 37 passed, 0 skipped.
- design_lint: OK.
- context_lint: OK (warnings only, unrelated).

Assertions changed (existing tests):
- tests/test_cleaning.py::test_readable_list_and_settings_escape_host_text_and_show_leading_zero_code: host checks for 001234, &lt;script&gt; and script-not-in moved to GET /cleaning/properties/{home}?lang=en. On /cleaning only "15:00" is checked (addendum 2). The 11:00 check is dropped there; the _hour checkout assert below covers it.
- tests/test_cleaning_browser.py, host page only (test_calendar_and_large_list_geometry_and_filtering): .cleaning-card count goes to .cleaning-section tr[id^=cleaning-]; date heading .cleaning-date-group h3 goes to .cleaning-section h2 and its 12-14 px size check is removed; h4 size and card padding checks removed; .cleaning-pin is now asserted absent on the host list (no door code, per addendum); the .cleaning-instructions and .cleaning-pin font-size checks are removed (no instructions on host list); the garden filter check now reads the row.
- tests/test_cleaning_browser.py, host-side zero-count checks in test_missing_code_is_omitted_from_host_list_and_calendar_dialog: scoped to .cleaning-section. The shared-view lines are unchanged.
- tests/test_cleaning_browser.py::test_host_crud_and_drag_change_cleanings_without_moving_bookings: rows are found by #cleaning-<id> (created_id). The wait for the drag date and the "Edit cleaning" link are replaced by reading the saved date from cleaning.schedule() and clicking the row's first link. The host table has no time element, so the saved date is checked from data, not DOM.
- tests/test_cleaning_browser.py::test_calendar_popup_types_create_in_place_and_localize_validation: the note text check is replaced by a 4-cell row check, because the host table shows no notes.
- tests/test_design_guardrails_browser.py (cleaning facts test): reads the column left positions of table rows per section instead of .cleaning-facts. The test name is unchanged.
- tests/test_dashboard_calendar_browser.py (cleaning calendar popup check, the line that asserted "Calendar popup" in the host row): now waits for the row #cleaning-<id> to be visible and asserts "27.10.2026" in it, because the host table shows no notes.
- Shared-view lines (cleaner page, .cleaning-card count 2, Door code checks at the shared-view URL) are not changed.

Deviations: the schedule-based date checks are a substitute for DOM time attributes the table does not render; the owner may want a time element in the day cell instead.

git diff --stat origin/main: run at the review step; the commit set is the six App/ files above plus App/tests/test_cleaning_browser.py, App/tests/test_design_guardrails_browser.py, App/tests/test_cleaning.py and this report.

Owner steps left: review the PR; no deploy. Branch not pushed.
