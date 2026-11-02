# 0834: Rewrite the red cleaning browser tests for the tag UI

Status: todo
Depends on: 0833 part 1 (committed) | Branch: claude/project-thread-6aeyrs
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens. Part A, then part B in a fresh run.

## 1. Objective

The host `/cleaning` page is now the Airbnb tile calendar showing cleaning tags only (no booking bars, no table, no legend). These tests in `App/tests/test_cleaning_browser.py` still assert the old UI and fail. Rewrite each for the tag UI, same intent, keep every data/behaviour assertion that still applies. Do not delete a test. Never weaken a test to pass without equivalent coverage; say in the report what changed and why. Read `docs/tasks/0815-report.md`, `docs/tasks/0833-report.md` and the two new tests at the file's end (`test_phone_cleaning_calendar_tags_only` and the desktop one) for the new selectors (tiles, `.cal-cleaning-tag`, side panel, day sheet, Add cleaning).

Part A (this run if the brief name ends `-A`): `test_calendar_and_large_list_geometry_and_filtering` (6 params), `test_fractional_checkout_and_same_day_cleaning_geometry` (2), `test_missing_code_is_omitted_from_host_list_and_calendar_dialog`, `test_cleaning_chip_label_starts_with_cleaning`.
Part B: `test_host_crud_and_drag_change_cleanings_without_moving_bookings` (drag of bars no longer exists on tiles: test create/edit/delete via the side panel or sheet and details dialog, and that bookings stay unmoved), `test_calendar_popup_types_create_in_place_and_localize_validation`, `test_missing_property_hours_keep_full_day_cleaning_marker_without_saved_defaults`, `test_cleaning_calendar_can_create_stay_and_refresh_turnover_in_place`, and `test_dashboard_calendar_creation_refreshes_cleaning_and_stay_in_place` in `test_dashboard_calendar_browser.py` (its /cleaning step expects a bar in week view: use the tag in month view).

## 2. Files

Only `App/tests/test_cleaning_browser.py` and (part B) `App/tests/test_dashboard_calendar_browser.py`. If a test needs a product change (a missing hook, tag text), stop and report it. Also write `docs/tasks/0834-A-report.md` / `0834-B-report.md`. Never stage or commit; never touch `docs/tasks/screenshots-0387/`; if the run rewrites tracked `docs/tasks/screenshots-0814/*` leave it, the orchestrator restores.

## 3. Command

From `App/`: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_cleaning_browser.py -q --tb=short -x -k "<names>" 2>&1 | tail -30` (600 s). At the end run the whole file; 0 skipped.

## 4. Stop and ask

A test needs a product change; 30 tool calls (report which tests are done).
