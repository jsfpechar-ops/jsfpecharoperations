# 0173 report

Status: review

## Files changed
- `App/tests/test_host_redesign.py`: `test_fee_navigation_uses_active_owned_properties` now asserts the fee link is on the Invoices tab and absent from the sidebar.
- `docs/tasks/0173-report.md` (this file).

## Commands
- `.venv/bin/python -m pytest tests/test_host_redesign.py -q --tb=short` (App/): 12 passed.
- `grep -rn "stay-fees\|smart-locks" tests/*.py | grep -i "rail\|sidebar\|nav"`: 3 files hit (below). No other sidebar assertion found.
- `tests/test_host_fee_navigation.py`: 3 passed, 1 skipped (line 166, "Chromium is required"; no Chromium in this container).
- `tests/test_host_list_page_layout_browser.py`: 3 passed, 2 failed. `test_list_pages_share_order_edges_and_rhythm` is a known pre-existing failure. `test_every_row_opens_on_click_and_enter_and_inner_controls_do_not` failed: Playwright Chromium executable missing at `/opt/pw-browsers/...`.
- `tests/test_host_properties_navigation.py`: 7 passed, 1 failed. `test_properties_page_fits_every_width_and_both_languages` failed with the same missing Chromium error. Not a sidebar assertion.

## Acceptance (brief section 7)
- [x] test_host_redesign passes (12 passed).
- [x] No other test expects those links in the sidebar (grep above; the browser failures are environment, not assertions).

## Deviations
- None to the brief's steps. No App code touched.
- Not run: browser tests that need Chromium (environment has no browser). Not installed, since that is outside the brief.

## Questions
- None.

## Owner steps left
- Run the browser tests in an environment with Playwright Chromium installed to confirm the two environment failures and the skipped geometry test pass with 0 skipped.
- Push and open the PR when ready (not done here: push was not requested).
