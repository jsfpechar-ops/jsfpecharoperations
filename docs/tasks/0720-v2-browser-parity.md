# 0720: v2 Overview passes the browser suite (Havel, dialogs, copy feedback, old-shell tests)
Status: todo
Depends on: 0719 | Base commit: claude/project-thread-50hyv5 after 0719 | Branch: task/0720-v2-browser-parity
Executor: Haiku 5.5 | Fits one session: 30 tool calls (split into 0720a/b if the list runs long; report what is left)

## 1. Objective
The browser suite has 67 failures since `/` moved to the v2 shell (local run on 0dd2e0b, list below). Fix them so the browser shards in CI go green, keeping every feature the old Overview had.

## 2. Context and decisions (orchestrator, 2026-11-01 18:25)
Sort each failing test into one of three groups and handle it as stated. Read the failing assertion first (`sed -n` the range), then decide.
- **A. A feature the host sees on `/` is missing or broken on v2** → fix the feature in app2.css (scoped `body.v2`), never by changing the test. Known cases:
  - Havel: `_havel_panel.html` renders `.havel-fab` and `#havel-sheet`, but their styles live only in `host.css` (grep `havel-fab`, `havel-sheet`, `havel-` in `App/app/static/host.css`). Copy the needed rules into app2.css under a marked block "v2 shared: Havel". On phone the fab and the panel sit above `.tabs` (bottom offset `calc(84px + env(safe-area-inset-bottom) + 16px)`), z-index above `.tabs`. Tests: `test_havel_browser.py`, `test_0386_havel_phone_look_browser.py`, `test_0391_havel_topics_first_browser.py`, `test_0395_havel_panel_layer_browser.py`, `test_havel_launcher_skeleton_browser.py`.
  - Dialog and sheet motion (`test_motion_browser.py`): copy the dialog/sheet fade and slide rules and the reduced-motion rules from host.css for the elements the v2 pages use. The old-shell rail checks in that file belong to group C.
  - Copy feedback, filter panels and row controls (`test_host_feedback_browser.py`, `test_host_filter_panels_browser.py`, `test_host_controls_browser.py`): fix on v2 if the test exercises `/`. The stays thread adds the `[data-copy-state-icon]` badge styles to app2.css on its own branch, so do not copy those. If a test fails only because of them, point that case at a page that is still on the old shell and note it.
- **B. The test checks the old Overview layout on `/` (old sidebar, `.needs-you` lane, old dashboard cards, the 0705 stylesheet strings).** The v2 Overview replaced that layout on purpose, and test_0710 now checks the v2 look. Update the assertion to the v2 equivalent when one exists (`section#needs-action` for needs-you, `#app-sidebar` / `.tabs` for navigation, `.card.need` for needs-you cards, `app2.css` key strings from base.html). If no v2 equivalent exists, point that case at a page still on the old shell (`/settings`, `/guide`, or `/payments`; check that the page has no `{% set v2 = true %}`) and say so in a comment. Files: `test_host_quiet_dashboard_browser.py`, `test_dashboard_phone_browser.py`, `test_host_wide_geometry_browser.py` (dashboard lanes), `test_0705_v2_shell_browser.py`, `test_onboarding_followup_browser.py` (line ~104 checks `.needs-you` on `/`), `test_navigation_prefetch_browser.py` (clicks `.ui-sidebar a` on `/`; on v2 use `#app-sidebar a[href="/reservations"]`), `test_design_shell_browser.py`, `test_door_code_window_browser.py` (read why it fails: a `getComputedStyle(null)` means a selector missing on `/`).
- **C. Old-shell behaviour (rail toggle, collapsed sidebar, tablet overlay, rail cross-fade).** Point those cases at an old-shell page (same list as B). Do not delete tests.
- `test_0201_tabbar_safe_area_browser.py` fails locally only because WebKit is not installed here. Leave it alone and say so. CI has WebKit.
- `test_0710_v2_mockup_match_browser.py` (overview at 768, menu at 320) is fixed by 0719; confirm it passes.
- Never skip, xfail or loosen a geometry tolerance. If a group A fix needs app.js or a route, stop and report.
- If you changed app2.css, bump its key in `base.html` to `20261101-0720` and `--write` the manifest.

Failing tests (local, 0dd2e0b):
```
test_0201_tabbar_safe_area_browser.py::test_phone_tab_bar_clears_the_home_indicator[360-780-cs-/]
test_0201_tabbar_safe_area_browser.py::test_phone_tab_bar_clears_the_home_indicator[360-780-en-/]
test_0201_tabbar_safe_area_browser.py::test_phone_tab_bar_clears_the_home_indicator[360-780-vi-/]
test_0201_tabbar_safe_area_browser.py::test_phone_tab_bar_clears_the_home_indicator[390-844-cs-/]
test_0201_tabbar_safe_area_browser.py::test_phone_tab_bar_clears_the_home_indicator[390-844-en-/]
test_0201_tabbar_safe_area_browser.py::test_phone_tab_bar_clears_the_home_indicator[390-844-vi-/]
test_0386_havel_phone_look_browser.py::test_cs_home_1280
test_0386_havel_phone_look_browser.py::test_no_ring_on_open
test_0386_havel_phone_look_browser.py::test_off_state_has_support_button
test_0386_havel_phone_look_browser.py::test_pill_composer
test_0386_havel_phone_look_browser.py::test_topics_are_chips
test_0391_havel_topics_first_browser.py::test_topics_first_then_box[1280]
test_0391_havel_topics_first_browser.py::test_topics_first_then_box[390]
test_0395_havel_panel_layer_browser.py::test_panel_above_calendar
test_0395_havel_panel_layer_browser.py::test_phone_panel_above_tabbar
test_0395_havel_panel_layer_browser.py::test_stale_start_screen_not_restored
test_0705_v2_shell_browser.py::test_app2_css_has_the_phone_top_bar_rule_and_no_font_picker
test_0705_v2_shell_browser.py::test_non_v2_dashboard_still_loads_the_old_stylesheets_and_sidebar
test_0705_v2_shell_browser.py::test_v2_branch_is_wired_in_base_html_and_the_v2_shell_exists
test_0710_v2_mockup_match_browser.py::test_v2_page_matches_mockup_styles[menu-320]
test_0710_v2_mockup_match_browser.py::test_v2_page_matches_mockup_styles[overview-768]
test_dashboard_phone_browser.py::test_phone_dashboard_compact
test_design_shell_browser.py::test_more_preserves_each_page_kind_and_sheet_links_work[/?lang=en-390-chromium]
test_design_shell_browser.py::test_more_preserves_each_page_kind_and_sheet_links_work[/?lang=en-820-chromium]
test_door_code_window_browser.py::test_disclosure_design_and_geometry_on_every_changed_page[cs-webkit]
test_door_code_window_browser.py::test_disclosure_design_and_geometry_on_every_changed_page[en-webkit]
test_door_code_window_browser.py::test_disclosure_design_and_geometry_on_every_changed_page[vi-webkit]
test_door_code_window_browser.py::test_live_preview_all_hours_missing_values_and_reflow[cs-webkit]
test_door_code_window_browser.py::test_live_preview_all_hours_missing_values_and_reflow[en-webkit]
test_door_code_window_browser.py::test_live_preview_all_hours_missing_values_and_reflow[vi-webkit]
test_havel_browser.py::test_chat_follows_the_host_across_pages[1280]
test_havel_browser.py::test_chat_follows_the_host_across_pages[390]
test_havel_browser.py::test_computer_panel_topics_handoff_and_answer
test_havel_browser.py::test_czech_greeting_on_the_phone
test_havel_browser.py::test_greeting_shows_once_after_a_reply
test_havel_browser.py::test_new_chat_and_other_user_clear_it
test_havel_browser.py::test_phone_launcher_and_sheet
test_havel_browser.py::test_phone_next_buttons_send_the_tapped_request
test_havel_launcher_skeleton_browser.py::test_havel_launcher_does_not_arm_the_navigation_skeleton
test_host_controls_browser.py::test_host_interactions_geometry_copy_and_archive_controls
test_host_feedback_browser.py::test_host_copy_feedback_truth_and_geometry
test_host_filter_panels_browser.py::test_filter_geometry_and_popovers_stay_inside_the_viewport_in_english_and_czech
test_host_quiet_dashboard_browser.py::test_dashboard_rich_needs_you_order_cap_and_geometry
test_host_quiet_dashboard_browser.py::test_dashboard_single_stay_needs_you_card
test_host_wide_geometry_browser.py::test_collapsed_sidebar_keeps_dashboard_and_stays_lanes_aligned
test_host_wide_geometry_browser.py::test_dashboard_760_header_and_actions_remain_in_the_shared_lane
test_host_wide_geometry_browser.py::test_host_wide_lanes_align
test_host_wide_geometry_browser.py::test_sidebar_click_respects_reduced_motion
test_host_wide_geometry_browser.py::test_sidebar_click_slides_the_rail_and_flips_the_toggle
test_host_wide_geometry_browser.py::test_sidebar_restore_and_resize_never_animate
test_host_wide_geometry_browser.py::test_tablet_rail_toggle_slides_the_overlay_only
test_motion_browser.py::test_dialogs_fade_in_and_phone_sheets_slide_up
test_motion_browser.py::test_fold_outs_slide_open_and_floating_menus_are_not_clipped
test_motion_browser.py::test_page_changes_cross_fade_with_the_rail_held_still
test_motion_browser.py::test_pages_without_javascript_stay_still
test_motion_browser.py::test_reduced_motion_keeps_pages_and_dialogs_still
test_navigation_prefetch_browser.py::test_sidebar_link_still_navigates_with_prefetch_rules
test_onboarding_followup_browser.py::test_rows_hover_as_one_surface_and_use_compact_menus[1440-cs]
test_onboarding_followup_browser.py::test_rows_hover_as_one_surface_and_use_compact_menus[1440-en]
test_onboarding_followup_browser.py::test_rows_hover_as_one_surface_and_use_compact_menus[1920-cs]
test_onboarding_followup_browser.py::test_rows_hover_as_one_surface_and_use_compact_menus[1920-en]
test_onboarding_followup_browser.py::test_rows_hover_as_one_surface_and_use_compact_menus[2048-cs]
test_onboarding_followup_browser.py::test_rows_hover_as_one_surface_and_use_compact_menus[2048-en]
test_onboarding_followup_browser.py::test_rows_hover_as_one_surface_and_use_compact_menus[360-cs]
test_onboarding_followup_browser.py::test_rows_hover_as_one_surface_and_use_compact_menus[360-en]
test_onboarding_followup_browser.py::test_rows_hover_as_one_surface_and_use_compact_menus[390-cs]
test_onboarding_followup_browser.py::test_rows_hover_as_one_surface_and_use_compact_menus[390-en]
```

## 3. Files
`App/app/static/app2.css`, `App/app/templates/base.html` (key), `App/tests/static_versions.json`, the failing test files above (group B/C changes only), report `docs/tasks/0720-report.md`.

## 4. Steps
1. Group A Havel. Run the five Havel files. Commit.
2. Group A motion/feedback/filters/controls. Commit.
3. Groups B and C, file by file (`-x -q --tb=line`). Commit every 2-3 files.
4. Key, manifest, then the command below. Commit + report.

## 5. Do not touch
`app.js`, `_shell_sidebar.html`, `dashboard.html` (unless a group A feature hook is missing there; then stop and ask), other pages' templates.

## 6. Commands (from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1`)
Per file: `.venv/bin/python -m pytest tests/<file> -q --tb=line -x 2>&1 | tail -15`. Final: every file in the list above in one run, `-q --tb=line -rf 2>&1 | tail -30` (0 skipped; test_0201 WebKit failures expected locally). Ruff: `.venv/bin/python -m ruff check app tests tools --select E9,F63,F7,F82,F401,F841 | tail -3`. Repo root: `python3 scripts/design_lint.py | tail -1; python3 scripts/context_lint.py | tail -1`.

## 7. Acceptance
All listed tests pass (except the local WebKit-only ones), 0 skipped, ruff clean, 0710 still green.

## 8. Stop and ask
Stop if a group A feature needs app.js, a route, or dashboard.html markup; or if a test can't be sorted into A/B/C.

## 9. Report
`docs/tasks/0720-report.md`: status, per test the group and what changed, test tails, what is left.
