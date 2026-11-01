# 0548 report: cleaning phone test data and tests

Status: blocked (steps 1 to 4 done; step 5 screenshots not taken; 3 tests need an owner decision)

## Done
- Step 1 (`0548 step 1`, d31a22a): `dashboard_rich_host` adds two manual cleaning events on "Review Flat" via `cleaning.save_event` (today 11:00-14:00, and +2 days 11:00-14:00). Imports `cleaning`. Overview result unchanged.
- Step 2 (`0548 step 2`, df7faf0): phone viewports moved to 768 px in `test_cleaning_browser.py`: `test_calendar_and_large_list_geometry_and_filtering` (`[768, 1024, 1280]`), `test_three_property_auto_gantt_keeps_cleaning_markers_visible` and `test_fractional_checkout_and_same_day_cleaning_geometry` (768 pairs), `test_missing_property_hours_keep_full_day_cleaning_marker_without_saved_defaults` (width 768), `test_add_stay_and_cleaning_dialogs_open_centred_in_both_tabs` (`(768, 844)`), `test_cleaning_form_pages_fit_the_viewport_and_take_screenshots` (`[1280, 768]`, height 844 at 768). The waits were the calendar selector, so the width change fixes them.
- Step 3 (`0548 step 3`, 7ab8ca9): `test_0541_cleaning_header` expects 2 share links on `/cleaning` and 1 inside the head; `test_design_cleaning` expects 2 links and one `.actbar.cleaning-phone`.
- Step 4: check run, no further change (the 3 failures below need decisions, not test fixes).
- Step 5: not done (see Left).

## Test tails
- `test_0710 -k overview`, after step 1: `1 failed, 11 passed, 21 deselected` (same as baseline: 768 px, 21 style differences, shared).
- `test_0710 -k cleaning`, after step 1: `3 failed, 9 passed, 21 deselected in 48.84s`. 390 now has 6 differences (was 8; the card and green row are gone). 768 has 8 differences (shared). 320 fails in the security-prompt click (shared with brief 0719).
- Calendar tests after step 2: `3 failed, 15 passed, 6 deselected in 31.22s`.
- Step 4 set: `3 failed, 80 passed in 49.44s` (the same 3 as above).
- `python3 scripts/design_lint.py`: `design lint: OK`.

## Left (owner decisions)
1. `test_fractional_checkout_and_same_day_cleaning_geometry[768-en]` and `[768-cs]`: the test sets `mobile = width <= 760`, so at 768 it takes the desktop branch and expects the pill to be at least 120 px wide. The app gives 102.28 px. Either the 768 px pill is an app layout issue or the test needs a decision about this width. App code is out of scope for this brief.
2. `test_missing_property_hours_keep_full_day_cleaning_marker_without_saved_defaults`: it now runs at 768 but hard-codes `mobile=True` for the marker check (count visible, label hidden), which fails at 768. Decide whether this test stays phone-only (it then cannot wait for the calendar) or is rewritten for 768.
3. Step 5 screenshots not taken: `docs/tasks/screenshots-0548/` was not created. The session cookie from `dashboard_rich_host["client"].cookies` is None when the test runs from a throwaway module under /tmp, and when test_0710's `test_v2_screenshots` runs the same way, so the app pages cannot be logged in for screenshots. Not diagnosed. The overview tests in test_0710 do get the cookie from their own module. Throwaway files are in `/tmp/shots0548/` (outside the repo).

## Deviations
- Commit trailer: the environment attribution says `Co-Authored-By: Claude Haiku 5.5`, and the brief and the launch message say Opus 5.5. I used Haiku 5.5 because the environment directive takes precedence. The owner should confirm.
- Nothing pushed. No changes to `docs/tasks/screenshots-0710`. No app code, template, CSS or shared helper changed.
