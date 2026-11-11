# 1104 report

Status: blocked
Executor: Haiku 5.5 | Branch: claude/project-thread-xhr13f (not pushed, no PR)

## Files changed
- App/app/templates/_property_calendars.html: span and copy button wrapped in `div.feed-url-row`
- App/app/static/app2.css: `.feed-url-row` rules replace the old `.feed-table .feed-url-value` rules
- App/app/templates/base.html: `app2.css?v=20261111-1104a`
- App/tests/test_calendar_sync_ui.py: `test_1104_feed_url_and_copy_button_share_one_row` (passes)
- App/tests/test_host_property_controls_browser.py: `test_1104_feed_url_and_copy_button_share_one_row` (fails, see below)

## Commands
1. `tests/test_calendar_sync_ui.py tests/test_calendar_platform_required.py tests/test_feed_*.py` (no -x): 63 passed, 1 failed. Failure: `test_feed_dns_pinning.py::test_two_concurrent_fetches_do_not_cross_pinned_addresses`, `OSError: [Errno 97] Address family not supported by protocol` when creating the IPv6 test server. Sandbox has no IPv6 socket support. Not related to this change; not checked on main.
2. Browser group (`host_property_controls`, `layout_lint`, `wp28_geometry`, `wp28_ui_sweep`, `design_guardrails`) with `-rs`: last run 2 failed, 45 passed, 0 skipped. Last 5 lines:
   ```
   tests/test_design_guardrails_browser.py:115: in test_every_host_page_passes_the_layout_guard
       assert not findings, ...
   E     guest-new 390 open: ['tap-target-small', 'a.ui-btn.ui-btn-quiet "Cancel"', 43, 44]
   2 failed, 45 passed in 362.35s (0:06:02)
   ```
   - `test_design_guardrails_browser.py::test_every_host_page_passes_the_layout_guard`: the known guest-new 390 Cancel finding. Only finding in the layout lint.
   - `test_host_property_controls_browser.py::test_1104_feed_url_and_copy_button_share_one_row`: at 1280 the URL is 102 px wide. The brief requires at least 120 px. Sameness, right-hand placement, 40 px button height and copy click all pass.
   - The earlier failure in `test_0984_calendar_rows_keep_state_and_actions_with_a_long_url` (1280, long URL pushed the copy button and Remove off-screen) was fixed in step 3 with `width:0` on `.feed-url-value`. It passes now.
3. `tests/test_privacy_first.py tests/test_host_i18n*.py`: NOT RUN (stopped at the checkpoint).

## Screenshots
Not taken. The 0984 test writes full-page shots when `UBYHOST_SHOTS_0984` is set; not run.

## Deviations
- The brief's CSS lines 2974-2975 are at 2976-2977 in the current file. Content matched, so I replaced by content.
- Added `width:0` to `.feed-url-row .feed-url-value` (step 3). Without it, the 640-character URL set the table column's min-content width and pushed the buttons off-screen at 1280.
- Template test checks `>Copy link<` once in the row. The raw count is 3 because of attributes.
- Done: steps 1 to 3 (the fix is step 3). Left: fix or decide the 1280 URL width (below), run command 3, take 390/768/1280 screenshots, write the UX notes in the PR body (no PR opened yet).

## Questions
- At 1280 the URL field is about 102 px. Options: (a) lower the test threshold to 100 px, or (b) give the URL column more width (a table-layout change not in the brief). Which one?

## Owner steps left
- None until the questions above are answered.
