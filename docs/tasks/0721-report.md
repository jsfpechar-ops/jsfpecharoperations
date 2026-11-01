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
