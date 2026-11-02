# 0548 report: cleaning phone test data and tests

Status: blocked (steps 1 to 5 done; 3 tests still fail and need an owner decision; not pushed)

## Done
- Step 1 (`0548 step 1`, d31a22a): `dashboard_rich_host` adds two manual cleaning events on "Review Flat" via `cleaning.save_event` (today 11:00-14:00, and +2 days 11:00-14:00). Overview result unchanged.
- Step 2 (`0548 step 2`, df7faf0): phone viewports moved to 768 px in `test_cleaning_browser.py`: `test_calendar_and_large_list_geometry_and_filtering` (`[768, 1024, 1280]`), `test_three_property_auto_gantt_keeps_cleaning_markers_visible` (768 pairs), `test_missing_property_hours_keep_full_day_cleaning_marker_without_saved_defaults` (width 768), `test_add_stay_and_cleaning_dialogs_open_centred_in_both_tabs` (`(768, 844)`), `test_cleaning_form_pages_fit_the_viewport_and_take_screenshots` (`[1280, 768]`, height 844 at 768).
- Step 3 (`0548 step 3`, 7ab8ca9): `test_0541_cleaning_header` expects 2 share links on `/cleaning`, 1 inside the head. `test_design_cleaning` expects 2 links and one `.actbar.cleaning-phone`.
- Step 4 (`0548 step 4`, aa756dd, coordinator instruction): `test_fractional_checkout_and_same_day_cleaning_geometry` parametrized at 1024 (`mobile=False`), phone-only branches removed from that test only. `test_missing_property_hours_keep_full_day_cleaning_marker_without_saved_defaults` at width 1024 with `mobile=False`. The helper `_assert_cleaning_day_marker` is unchanged.
- Step 5 (`0548 step 5`, a0af722, coordinator instruction): screenshots from `test_0710 -k screenshots` (`UBYHOST_SHOTS_V2=1`), copied to `docs/tasks/screenshots-0548/`: `cleaning-390.png`, `cleaning-1280.png`, `mockup-clean-390.png`. `docs/tasks/screenshots-0710` restored (`git checkout` and `git clean`).

## Test tails
- `test_0710 -k overview`, after step 1: `1 failed, 11 passed, 21 deselected` (same as baseline: 768 px, 21 style differences, shared).
- `test_0710 -k cleaning`, after step 1: `3 failed, 9 passed, 21 deselected in 48.84s`. 390 now has 6 differences (was 8). 768 has 8 (shared). 320 fails in the security-prompt click (shared with brief 0719).
- Targeted run after step 4: `3 failed, 2 passed, 19 deselected in 9.48s`. Failures: `fractional_checkout[1024-en]`, `[1024-cs]`, `missing_property...`, all `assert 97.14 >= 120`.
- Step 4 set after step 4: `3 failed, 80 passed in 52.98s` (the same 3).
- `test_0710 -k screenshots`: `1 passed, 32 deselected in 19.13s`.
- `python3 scripts/design_lint.py`: `design lint: OK` (run after step 1).

## Left (owner decisions)
1. `test_fractional_checkout_and_same_day_cleaning_geometry[1024-en]` and `[1024-cs]`, and `test_missing_property_hours_keep_full_day_cleaning_marker_without_saved_defaults`: the shared helper `_assert_cleaning_day_marker` (desktop branch) requires the cleaning pill to be at least 120 px wide. At 1024 px the pill is 97.14 px. At 1280 px the same checks pass. The checks were kept unchanged as instructed. Decide either to change the 120 px threshold for this width, or to change the pill layout at 1024 px (app code, out of scope for this brief).
2. Visual defect seen in `docs/tasks/screenshots-0548/cleaning-390.png`: the today card's "Review Flat" title and a white element overlap the left edge of the card. Not investigated; the brief excludes app code.
3. Phone mockup Úklid shot not produced: `test_v2_screenshots` writes only desktop-view mockups (`mockup-clean-390.png`). `show_phone_screen(page, "uklid")` was not run, so there is no phone mockup image in this folder.

## Deviations
- Commit trailers: steps 1 to 3 and this report use `Co-Authored-By: Claude Haiku 5.5`, because the environment attribution directive said so. Steps 4 and 5 use `Claude Opus 5.5` as the coordinator instructed.
- Nothing pushed. No app code, template, CSS or shared helper changed.
- The earlier cookie problem with a throwaway test module under `/tmp` is no longer relevant: the coordinator's route through `test_0710 -k screenshots` worked.
