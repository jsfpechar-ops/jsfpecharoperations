# 0721 report (executor, partial)

Status: blocked
Done: steps 1 (0375 test). Left: dashboard restores, havel, prefetch decision, endtoend check.

## Commits
- 6e5a7b6 `0721 step 1`: test_0375 asserts the 0719 icon markup (`class="ic {{ ph_tone }}"`).
- Follow-up commit: test_0375 ghost assertion now `"if first else ' ghost line'"`. Test file passes (2 passed).

## Per test (local 7ffde44 run: 14 failed, 40 passed)
- test_0375 ...primary_only_on_first_line: FIXED (test string only; template unchanged).
- test_dashboard_empty (2), test_dashboard_missing_banner (3), test_dashboard_order (3), test_signed_in_chrome::test_a_stay_that_needs_the_host_gets_one_line_with_one_button: NOT STARTED. Needs dashboard.html restore against `git show origin/main:App/app/templates/dashboard.html`. Chrome test: "the stay arriving tomorrow has no line" (test_signed_in_chrome.py:234).
- test_havel_palette::test_no_match_opens_havel_with_the_query: NOT FIXED. Brief premise is off: `_shell_v2.html:16` already has `data-command-open`. The failure is `[data-command-open]:visible` not found at 390 px on /guide (a visible one is needed at phone width). Needs a layout decision, not just attributes.
- test_navigation_prefetch::test_signed_in_shell_renders_prefetch_rules_with_exclusions: NOT FIXED, STOP (brief §8). Cause: the speculation block is in `base.html:265` (shared, not in `_shell_v2.html`). The `/admin/*` exclusion is only emitted when `current_user.role == 'admin'`, and the test asserts it for a host. Proposed fix, owner/orchestrator to confirm: make the `/admin/*` entry unconditional in base.html:265 (drop the `{% if ... admin %}` wrapper). That file is outside brief §3.
- test_demo_seed::test_seed_imports_stays_without_fetching_the_calendar: PASSED in the local run. No change.
- test_feed_dns_pinning::test_two_concurrent_fetches_do_not_cross_pinned_addresses: ENVIRONMENT. Same `OSError [Errno 97] Address family not supported by protocol` on origin/main worktree.
- test_reporting_help_0097::test_reporting_and_fee_list_geometry_and_tips_in_the_browser: SAME FAILURE ON origin/main (`Locator.tap` timeout 30 s, element not visible). Environment or pre-existing; not fixed.
- test_endtoend.py: NOT RUN (out of budget). Brief step: run -x on origin/main.

## Notes
- Running test_havel_palette regenerates `docs/tasks/screenshots-0322/guide-ask-390.png`; restored with `git checkout --`.
- Temporary worktree /tmp/wtmain0721 (origin/main) created for env checks; removed at the end of this run.

## Left for the next session
1. dashboard.html restores (8 tests above).
2. havel palette: decide the phone-width search entry point.
3. prefetch: approve the base.html `/admin/*` change or give another direction.
4. test_endtoend on origin/main, then the 0710 browser test, ruff, design_lint, context_lint.

## Owner steps
- None yet. Nothing pushed.

## Session 2

Status: blocked (dashboard finish-card question needs an owner or orchestrator decision)

### Commits
- `0721 step 2`: base.html `/admin/*` speculation exclusion restored unconditional (main's form). test_host_account_navigation's "no admin controls" check now asserts `href="/admin` (the JSON exclusion is not a control).
- `0721 step 3`: `_setup_lines` helper in test_dashboard_missing_banner.py matches the 0719 `card needs-you-card-item need` markup. Test-only change.

### Tails
- `pytest tests/test_navigation_prefetch.py tests/test_host_account_navigation.py -q`: `19 passed in 5.50s`
- `pytest tests/test_dashboard_missing_banner.py -q`: `5 passed in 1.64s`
- `pytest tests/test_dashboard_empty.py -q` (branch): 2 failed, lines 105 and 153 (`bookings#calendars` href and `onboarding-banner` present on `/`). Not fixed.
- `pytest tests/test_dashboard_order.py -q` (branch, dashboard.html unchanged): 3 failed, lines 132, 144, 154. Not fixed.
- test_signed_in_chrome::test_a_stay_that_needs_the_host_gets_one_line_with_one_button: not started.

### Per test
- test_havel_palette::test_no_match_opens_havel_with_the_query: FAILS ON origin/main too (`Locator.click` timeout 30 s, waiting for `[data-command-open]:visible`). Pre-existing; left alone.
- test_dashboard_missing_banner (3 listed): FIXED by the helper markup change (5 passed).
- test_dashboard_empty (2 listed): open. The page still shows the calendar-connect link and `onboarding-banner` in this state. Needs a condition fix in dashboard.html or `_components.html`.
- test_dashboard_order (3 listed): open, and this is a contract conflict, not a markup slip. The branch test files (edited by 0706, comments "removed from Overview by the v2 rebuild") assert that the one-line finish strip text ("Setup is done. Your guest link and PIN are ready.", `onboarding.finish_strip`) and its `section=guests#communication` link are absent on `/`, and that `class="onboarding-finish"` is absent for an overdue stay AND for a future stay. The current v2 dashboard.html renders the tall `onboarding_finish` card unconditionally at its line ~94.
  - Tried: main's split (`focus_is_urgent` gives the strip, else the tall card). It made 5 order tests fail instead of 3 (new failures at lines 123, 134, 165). Reverted, not committed.
  - origin/main's test files are the pre-0706 versions, so running them on main proves nothing about the current assertions (5 and 6 passed on main, but for the old expectations).
  - Question for the owner: should Overview show the finish card at all? If no (the 0706 intent), delete the finish block and the strip from dashboard.html and the assertions match. If yes, the assertions must change.
- test_navigation_prefetch: FIXED (see step 2).
- test_signed_in_chrome: not started.
- test_demo_seed, test_feed_dns_pinning, test_reporting_help_0097, test_endtoend: not re-run in this session (session 1 recorded them).

### Not done
- Duplicate PIN alert item (brief item 4): not started.
- Ruff check: not run.
- test_endtoend on origin/main: not run.

### Owner steps
- Decide the finish-card question above. Nothing pushed.

## Session 3

Status: review (steps 1-3 and 5-6 done; step 4 left)

### Commits
- `0721 step 1` (3622bea): test_dashboard_order.py and test_dashboard_empty.py restored to origin/main (`git checkout origin/main --`). Every diff hunk was a 0706 edit, so nothing else was lost.
- `0721 step 2` (c4c209a): dashboard.html keeps the finish card. An urgent `focus` gives the one-line strip (`onboarding_finish_strip`, after the needs-action section); otherwise the tall `onboarding_finish` card. The 0717 handoff is the same macro, so there is no duplicate block. The empty state from main (`dashboard.empty.no_stays` / `no_feed` with the calendar link) is back after the banner.
- `0721 step 3` (7300848): test_signed_in_chrome.py line regex accepts the 0719 `need` modifier (`class="card needs-you-card-item[^"]*"`). The template and needs-you data already render the "arrives tomorrow" line; only the regex was stale. Test-only change.

### Tails
- `pytest tests/test_dashboard_order.py tests/test_dashboard_empty.py tests/test_onboarding.py tests/test_needs_you_dashboard_0241.py tests/test_design_dashboard.py -q`: `32 passed in 2.74s`
- `pytest tests/test_signed_in_chrome.py::test_a_stay_that_needs_the_host_gets_one_line_with_one_button -q`: `1 passed in 1.43s`
- `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers UBYHOST_REQUIRE_BROWSER=1 pytest tests/test_0710_v2_mockup_match_browser.py -q`: `22 passed in 35.43s` (0 skipped)
- `ruff check app tests tools --select E9,F63,F7,F82,F401,F841`: `All checks passed!`

### Left
- Step 4 (duplicate PIN alert): not started, budget spent on steps 1-3.
- test_signed_in_chrome.py as a whole, test_dashboard_missing_banner.py, test_havel_palette (fails on origin/main too, pre-existing): not re-run this session.
- No 390 px screenshots taken (no new page; dashboard.html change is covered by the 0710 browser test).

### Owner steps
- None. Nothing pushed.
