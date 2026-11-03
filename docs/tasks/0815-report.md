# 0815 report (executor)

Status: blocked
Done: steps 1 and 2 (JS, CSS, no template or version change). Step 3 (tests, screenshots) partly done. Left: see Open items.

## Files changed (not staged, not committed)
- `App/app/static/dashboard-calendar.js`: `hostCleaning` flag; `phoneDots()` and `tiles()` now true for the host cleaning page (not the read-only one); cleaning tags in the month tile (`.cal-clean-tag`, `.cal-clean-chip`, `has-cleaning`); bookings dropped from week and gantt on the host cleaning page; the day sheet and day dialog list only cleanings; the add button reads `labels.add_cleaning`.
- `App/app/static/dashboard-calendar.css`: every `[data-cleaning="false"]` selector became `[data-readonly="false"]` (same specificity; host dashboard unchanged, host cleaning page now gets the Airbnb rules); `/* 0815 */` block at the end (tags, chips, hides `#cleaning-list` and `.cleaning-legend` on the host cleaning page).
- `App/tests/test_cleaning_browser.py`: two tests appended (`test_phone_cleaning_calendar_tags_only`, `test_desktop_cleaning_calendar_tags_and_side_panel`). Not green.

Not changed: templates, `?v=`, `static_versions.json` (skipped per brief).

## Test results (UBYHOST_REQUIRE_BROWSER=1, skipped: none)
- `test_dashboard_phone_browser.py`, `test_dashboard_calendar_browser.py`, `test_0199_phone_geometry_browser.py`: `1 failed, 26 passed`. The failure is `test_dashboard_calendar_creation_refreshes_cleaning_and_stay_in_place` at line 507, a step on the cleaning page that expects a cleaning bar in week view. Expected from the new design; test not yet updated.
- `test_cleaning_browser.py` (last full run, before the two new tests): 15 failed, 35 passed. Failing cleaning tests: `test_calendar_and_large_list_geometry_and_filtering` (6), `test_fractional_checkout_and_same_day_cleaning_geometry` (2), `test_missing_code_is_omitted_from_host_list_and_calendar_dialog`, `test_host_crud_and_drag_change_cleanings_without_moving_bookings`, `test_calendar_popup_types_create_in_place_and_localize_validation`, `test_missing_property_hours_keep_full_day_cleaning_marker_without_saved_defaults`, `test_cleaning_calendar_can_create_stay_and_refresh_turnover_in_place`, `test_cleaning_chip_label_starts_with_cleaning`. All use bars, labels or the visible list on the host page.
- New phone test: fails in `loaded()`. Cause: the host cleaning page on phone has `section.dashboard-calendar` at `display:none`. An untouched HEAD copy shows the same, so this is pre-existing.

## Open items (owner or orchestrator decision)
1. Phone host cleaning page hides the whole calendar at HEAD (cards only). Brief 0815 section 2 assumes it is visible. Find and override that hide rule, or confirm the owner wants the phone cleaning page as cards. Not found in the CSS within budget.
2. Update the 8 cleaning test groups above to the tag UI (tags instead of `.cal-cleaning-label` or bars; list hidden on the host page). Range select (long press) at 390 is not tested.
3. Screenshots `docs/tasks/screenshots-0814/cleaning-*.png` not produced. Test runs with `UBYHOST_TASK_SHOTS=1` also overwrote the tracked `calendar-*.png` files in that folder. Restore them with `git checkout -- docs/tasks/screenshots-0814/` unless 0832 wants its new ones.
4. Table actions: `_cleaning_table.html` has only the edit link per row. Calendar details open `event.url` for cleanings, so the list is hidden on the host page without losing an action. Not checked against the server URL.
5. Year view on the host cleaning page still counts bookings (not drawn, not in brief).
6. Concurrent edits: 0832 changed `dashboard.html`, `_dashboard_calendar.html` and `test_dashboard_calendar_browser.py` in the same checkout. My CSS selector switch touched only `dashboard-calendar.css`.
