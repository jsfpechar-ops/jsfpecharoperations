# 0361 report: one sharded browser job

Status: review

## Files changed

- `.github/workflows/ci.yml`: `test` job gets the node passkey step (step 2). `guest-browser`, `calendar-review` and `door-code-access-review` replaced by `browser-shard` (4 shards) and `browser` (step 3).
- `.github/workflows/deploy-lightsail.yml`: `"guest-browser"` becomes `"browser"` (step 4).
- Deleted: `mobile-more.yml`, `passkeys-client.yml`, `checkin-alerts.yml` (step 5).
- `App/tests/test_guest_browser_e2e.py`, `docs/DESIGN.md`: one word each (step 5).
- `docs/tasks/0361-report.md` (this file); `docs/tasks/0361-one-browser-job.md` (Status line).

Commits: `0361 step 2` (c8f259a), `0361 step 3` (9692c53), `0361 step 4` (7c73a34), `0361 step 5`, `0361 step 6`.

## Commands (last lines)

- §6 (a), survey, 6 batches over 53 files:
  - batch 1: `1 failed, 53 passed in 264.65s`
  - batch 2: `6 failed, 75 passed, 2 warnings in 386.78s`
  - batch 3: `24 passed in 178.29s`
  - batch 4: `40 passed in 308.79s`
  - batch 5: `10 failed, 248 passed in 418.31s`
  - batch 6: `1 failed, 11 passed in 45.41s`
  - Total: 451 passed, 18 failed, 0 skipped. Wall time 1611 s (about 27 min).
- §6 (b): `ok`
- §6 (c): `context lint: OK`. The `guest-browser` grep printed nothing from source. Its only match was a git-ignored `App/tests/__pycache__/*.pyc`.

## Survey table (Chromium only, `UBYHOST_SHELL_BROWSERS=chromium`)

| File | Passed | Failed (first failing test) | Skipped |
|---|---|---|---|
| test_0199_phone_geometry_browser | 2 | 1 (test_lock: lock-en-360 gap 218) | 0 |
| test_0201_tabbar_safe_area_browser | 13 | 0 | 0 |
| test_0251_tablet_browser | 1 | 0 | 0 |
| test_0252_touch_sweep_browser | 1 | 0 | 0 |
| test_0281_card_borders_browser | 1 | 0 | 0 |
| test_0282_signature_dialog_browser | 1 | 0 | 0 |
| test_0284_states_browser | 2 | 0 | 0 |
| test_0285_rows_browser | 2 | 0 | 0 |
| test_a11y_guard_browser | 4 | 0 | 0 |
| test_cleaning_browser | 26 | 0 | 0 |
| test_dashboard_calendar_browser | 14 | 0 | 0 |
| test_dashboard_phone_browser | 1 | 0 | 0 |
| test_dashboard_rows_browser | 1 | 0 | 0 |
| test_design_guardrails_browser | 10 | 0 | 0 |
| test_design_setup_wizard_browser | 7 | 0 | 0 |
| test_design_shell_browser | 15 | 0 | 0 |
| test_dev_ui_browser | 2 | 0 | 0 |
| test_door_code_window_browser | 8 | 6 (all `-webkit`: test_disclosure_design_and_geometry_on_every_changed_page x3, test_live_preview_all_hours_missing_values_and_reflow x3; WebKit not installed locally) | 0 |
| test_download_skeleton_browser | 1 | 0 | 0 |
| test_guest_browser_e2e | 16 | 0 | 0 |
| test_guest_guide_browser | 2 | 0 | 0 |
| test_host_button_contrast_browser | 1 | 0 | 0 |
| test_host_controls_browser | 1 | 0 | 0 |
| test_host_feedback_browser | 1 | 0 | 0 |
| test_host_filter_panels_browser | 4 | 0 | 0 |
| test_host_fit_browser | 1 | 0 | 0 |
| test_host_geometry | 2 | 0 | 0 |
| test_host_help_browser | 6 | 0 | 0 |
| test_host_invoice_items_browser | 5 | 0 | 0 |
| test_host_list_cards_browser | 1 | 0 | 0 |
| test_host_list_layouts_browser | 2 | 0 | 0 |
| test_host_list_page_layout_browser | 5 | 0 | 0 |
| test_host_property_controls_browser | 3 | 0 | 0 |
| test_host_quiet_dashboard_browser | 2 | 0 | 0 |
| test_host_stay_actions_browser | 1 | 0 | 0 |
| test_host_stay_detail_layout_browser | 1 | 0 | 0 |
| test_host_unsaved_changes_browser | 15 | 0 | 0 |
| test_host_wide_geometry_browser | 6 | 0 | 0 |
| test_invoice_stay_browser | 2 | 0 | 0 |
| test_lock_navigation_browser | 3 | 0 | 0 |
| test_onboarding_followup_browser | 16 | 0 | 0 |
| test_onboarding_wizard_browser | 70 | 0 | 0 |
| test_onboarding_wizard_survival | 24 | 0 | 0 |
| test_passkeys_client_browser | 95 | 0 | 0 |
| test_posthog_snippet_browser | 1 | 0 | 0 |
| test_properties_inline_controls_browser | 12 | 0 | 0 |
| test_property_create_browser | 12 | 1 (test_create_page_is_short_and_has_each_field_once) | 0 |
| test_property_navigation_browser | 11 | 1 (test_three_views_four_groups_one_editor_and_unique_ids) | 0 |
| test_push_settings_browser | 3 | 8 (turning_alerts_on_sends_one_test x3 langs; the_alerts_row_fits_wide_layouts x4; logging_out_turns_alerts_off_on_this_device) | 0 |
| test_pwa_browser | 4 | 0 | 0 |
| test_shell_lane_browser | 4 | 0 | 0 |
| test_stay_fee_pay_steps_browser | 1 | 0 | 0 |
| test_wp28_geometry | 6 | 1 (test_operator_signature_block_is_styled) | 0 |
| **Total (53 files)** | **451** | **18** | **0** |

Failing files outside WebKit: test_0199, property_create, property_navigation, push_settings, wp28_geometry. Their failures were not investigated or fixed (brief §4 step 1).

## §7 acceptance

- [x] Survey table in the report: every browser file, with passed, failed and skipped, plus total time.
- [x] `ci.yml` has no `guest-browser`, `calendar-review` or `door-code-access-review` job. It has `browser-shard` (4 shards) and `browser`.
- [x] `deploy-lightsail.yml` requires `browser`.
- [x] The three side workflows are deleted.
- [x] §6 (b) prints `ok`; §6 (c) passes.

## Deviations

- Survey: the §6 (a) command also wrote JUnit XML to the scratchpad for per-file counts. Output was filtered to keep it short. No test code changed.
- The browser run rewrote tracked PNGs under `docs/tasks/0102-evidence/`. I restored them with `git checkout`, so no commit contains them.
- Step 3: the `Summarize required browser checks`, `browser_summary`, `Annotate failed tests` and 8 `Test failure detail` steps were copied verbatim from the old `guest-browser` job by script. Per §4a, the old `Upload calendar and dashboard review screenshots` and `Upload onboarding screenshots` steps were not copied.
- No PR opened, per the orchestrator's instruction.

## Questions

1. The `browser` gate will be red until the 18 survey failures are fixed. Confirm that fix briefs come before merge, as §Owner steps says.
2. The dropped `Upload onboarding screenshots` step: confirm its screenshots are covered by the new `browser-shots-N` artifact, or that losing them is acceptable.

## Owner steps left

1. Write fix briefs for the failing files above. Merge only after every browser shard is green.
2. After merge, the main ruleset (owner settings pass) requires `browser`, not `guest-browser`.
