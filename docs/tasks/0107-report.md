# 0107 report

Status: review
Branch: `task/0107-small-primary-button-contrast` (base `f759ccd`, task 0105 head). Not pushed.

## Files changed

`git diff --stat task/0105-restore-dashboard-stay-rows` (tracked change):

```
 App/app/static/host-design0123.css | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)
```

Added: `App/tests/test_host_button_contrast_browser.py` (new test), `docs/tasks/0107-small-primary-button-contrast.md` (brief copy, `Status: review`), `docs/tasks/0107-report.md`, `docs/tasks/0107-screenshots/stay-fees-1280.png`, `docs/tasks/0107-screenshots/stay-fees-360.png`.

The CSS change is line 21 only: `:not(.err-text):not(.warn-text)` gains `:not(.btn)`.

## Commands and output (last 5 lines, as the run printed them)

Environment: `App/.venv` created from `requirements.txt` and `requirements-dev.txt`, plus `playwright==1.63.0` (same pin as CI). Chromium came from `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`, because the Playwright bundle revision did not match the preinstalled browser. Nothing was installed with `playwright install`.

1. Before the fix, from `App/`: `UBYHOST_BROWSER_EXECUTABLE=... UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_button_contrast_browser.py -q -rs`
   ```
   E   AssertionError: ('stay-fees/1280', {'text': 'Set up stay fee', 'color': 'rgb(98, 98, 93)', 'background': 'rgb(185, 77, 70)'}, 1.23)
   E   assert 1.2302189872085447 >= 4.5
   tests/test_host_button_contrast_browser.py:161: AssertionError
   -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
   1 failed, 1 warning in 2.45s
   ```
   The first failure was at 1280. The loop stops at the first failing button, so 360 px was not checked separately before the fix.

2. After the fix, with `UBYHOST_CAPTURE_0107=1`: `1 passed, 1 warning in 3.83s` (exit 0). Re-run after the last edit: `1 passed, 1 warning in 3.04s`. 0 skipped.

3. Subset: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests -q -rs -k "host_list_layouts or stay_fee or host_quiet_dashboard"`
   ```
   142 passed, 3537 deselected, 1 warning in 70.19s (0:01:10)
   ```
   0 skipped.

4. Full suite: `UBYHOST_UBYPORT_ENV=mock UBYHOST_DEPLOYMENT=staging UBYHOST_ENABLE_SCHEDULER=0 .venv/bin/python -m pytest tests -q -rs` (run with the fix in place)
   ```
   SKIPPED [1] tests/test_dashboard_missing_banner.py:174: evidence capture
   SKIPPED [1] tests/test_invoice_autofill.py:300: set UBYHOST_SHOTS_DIR to capture acceptance screenshots
   SKIPPED [1] tests/test_source_badge.py:90: set UBYHOST_SHOTS_DIR to capture acceptance screenshots
   12 failed, 3664 passed, 3 skipped, 7 warnings in 1318.82s (0:21:58)
   ```
   The 3 skips are evidence-capture guards (they need `UBYHOST_SHOTS_DIR`), not missing browsers.

5. Pre-existing check: the 12 failing tests were run against the unfixed CSS (the one selector reverted, then restored) over the 11 files that hold them:
   ```
   12 failed, 70 passed, 1 warning in 252.56s (0:04:12)
   ```
   The same 12 failed. They are: `test_dashboard_calendar_creation_refreshes_cleaning_and_stay_in_place`, `test_two_concurrent_fetches_do_not_cross_pinned_addresses` (in `test_feed_dns_pinning.py`), `test_stays_fit_lane_at_every_width_and_sidebar_state`, `test_invoice_item_geometry_and_localized_screenshots`, `test_properties_page_fits_every_width_and_both_languages`, `test_property_and_operator_controls_render_and_work_in_browser`, `test_page_families_through_rail_cards_search_and_back`, `test_before_send_scrubs_click_ids_and_urls`, `test_create_page_fits_and_follow_ups_move_below_when_narrow`, `test_three_views_four_groups_one_editor_and_unique_ids`, `test_create_offers_the_calendar_first_and_works_without_js`, `test_stay_page_cards_hold_their_buttons`. The fix does not cause them, but I did not confirm them on PR head 34b7933 itself.

6. Context lint, from the repo root: `python3 scripts/context_lint.py`
   ```
   WARN  1 commit(s) touched App/ after the last status.md update. Orchestrator: update docs/context/status.md at review.
   next free: task 0124 | migration 0011
   context lint: OK
   ```
   The `decisions.md` cap error mentioned in the brief did not appear.

## Section 7 acceptance, ticked honestly

- [x] The new test passes after the fix at 1280 and 360 px. It failed before the fix at 1280 (see 1). The 360 px failure before the fix was not observed separately.
- [x] Screenshots show white text on coral for "Set up stay fee" at both widths (`stay-fees-1280.png`, `stay-fees-360.png`).
- [ ] "No other visual change on the page" is not verified. I made no before/after pixel comparison. The selector also affects other `.btn.small` elements in the host shell, which now keep their own colour instead of the grey ink.
- [x] Browser tests: 0 skipped in the new test and in the `-k` subset. The full suite has 3 evidence-capture skips.

## Deviations

- The brief's §2 excerpt contains `.dashboard-row-property-context`. The line on this base does not have it (task 0105 removed it). The rest of the excerpt matched, so I proceeded and added only `:not(.btn)`.
- The brief asks for "the same demo data" as `test_host_list_layouts_browser.py`. That file reuses dashboard fixtures and creates no stay-fee properties. The new test therefore has its own module fixture: one host with two properties that have no `stay_fee_rate_czk` ("Not set up").
- The brief asks for at least one button. The test asserts at least two, because the fixture creates two unset properties.
- The brief's §6 names `test_host_list_layouts` and the other subset tests. Those are covered by the `-k` run above.
- The brief's §6 list of pre-existing failures names `test_feed_dns_pinning`. In the run, the failing test in that file is `test_two_concurrent_fetches_do_not_cross_pinned_addresses`. `test_08_dashboard_shows_the_stay_as_awaiting_the_guest` passed in this run.
- The brief's `test_host_list_layouts_browser` fixture pattern was followed for the server thread, the `_launch` skip rule, and the security-prompt dismissal.
