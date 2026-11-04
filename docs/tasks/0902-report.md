# 0902 report (executor: Haiku 5.5)

Status: blocked

## Files changed (uncommitted, working tree)

- `App/app/templates/dashboard.html`: `overview_card` macro replaced by `ny_row` (`<li class="needs-you-item need">`, same data attributes, paste details, action button, dismiss form). Section `#needs-action` now renders `<ul class="needs-you-list">` with the first 5 rows, then `<details class="needs-you-more">` with `needs_you.more` for the rest. Count badge `ui-badge ui-badge-action` in the heading. Calm card kept.
- `App/app/static/app2.css`: removed the dead `.needs-you-card-item` and 0722 phone-hide rules; retargeted the surviving rules to `.needs-you-item`; appended a `/* 0902 */` block (row layout, tone left border, 768+ two-column grid, phone full-width button). No overlay pseudo-elements.
- `App/app/templates/base.html`: app2.css cache key set to `?v=0902`.
- `App/tests/static_versions.json`: regenerated with `tests/test_static_versions.py --write`.
- Tests with old-structure assertions only: `tests/test_0375_needs_you_and_open.py`, `tests/test_0284_states_browser.py`, `tests/test_dashboard_queue_copy.py`, `tests/test_signed_in_chrome.py`, `tests/test_dashboard_missing_banner.py` (selectors; one count line), `tests/test_0765_phone_today_window_browser.py` (`.card.need` to `.needs-you-item.need`).
- `docs/design/catalog.json`: not changed. `needs-you-item` and `needs-you-list` are already listed. The `ny-phone-only`, `ny-sum-phone`, `ny-sum-desk` entries are now unused and were left in place.

## Test runs

Environment: `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome`, `UBYHOST_REQUIRE_BROWSER=1`. The default Playwright headless-shell path does not exist here, so `UBYHOST_BROWSER_EXECUTABLE` is needed.

- Brief set (8 files): 27 passed, 2 failed before the test fixes above.
- After the fixes, all files except one assertion passed: 63 passed, 1 failed (`tests/test_dashboard_missing_banner.py:143`, expects `Show 2 more`). Last 5 lines:
  `E   assert 'Show 2 more' in '<!doctype html> ...'`
  `1 failed, 8 passed` (for `test_dashboard_missing_banner.py` plus `test_0765_phone_today_window_browser.py`)
- Skipped: none seen in the runs so far (`-rs` used).

## Not done

- Step 5: `test_dashboard_missing_banner.py:143` still fails. The new toggle text is `needs_you.more` with N = lines minus 5, so the seeded scenario's expected count needs checking. I did not investigate.
- Step 6: screenshots (`docs/tasks/screenshots-0902/`) not taken. No visual check done.
- Step 7: `test_layout_lint_browser.py` not run.
- No commit, no push, no PR (owner override).

## Deviations

Done: steps 1 to 5 (step 5 has one failing assertion). Left: step 5 (one assertion), step 6, step 7.

## Questions

- Should the `Show 2 more` assertion be updated to the new count, or is the seeded scenario expected to produce a different number of lines?
- The unused `ny-*` catalog entries: remove them or leave them?

## Owner steps left

None until the orchestrator reviews and commits.
