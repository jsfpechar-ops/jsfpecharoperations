# 0826 report

Status: review

Files changed (mine only): `App/app/static/app2.css` (block `/* 0826 shell top gaps */`, `.side .support-link` rules removed), `App/app/templates/_shell_v2.html` (`support-link` line removed), `App/tests/test_0705_v2_shell_browser.py` (geometry test and static test added). Not touched: `base.html`, `static_versions.json`, the 0825 block. Those two files show as modified in the checkout from the other executor.

Before/after: before the fix, `/` at 1024, 1280 and 1440 failed with brand to env badge gap 0 px (first failure reported; the test stops at the first pair). After: every visible pair in the sidebar is at least 12 px apart on `/` and `/stay-fees` at 1024 to 1440.

Commands (from `App/`, `UBYHOST_REQUIRE_BROWSER=1`):
- `tests/test_0705_v2_shell_browser.py tests/test_shell_lane_browser.py tests/test_design_shell_browser.py -q -rs`: 29 passed, 0 skipped, 0 failed (static-versions test passed, cache key not changed by me).
- New tests: 6 parametrized geometry tests (320 to 1440) plus `test_v2_shell_has_one_help_entry_0826`. The geometry test failed 3 times before the fix (1024, 1280, 1440) and passes after.

Deviations:
- No commit made, per your instruction (executor.md asks for per-step commits; overridden).
- Tablet and phone: in v2 the sidebar is `display:none` below 1024 px (`body.v2 .side` rule, tab bar replaces it), so no tablet rail or phone top bar exists for these blocks; the test measures 0 pairs there.
- 390 px screenshot not taken: the changed rules apply to the sidebar, which is hidden at 390 px, so a 390 px shot would show only the tab bar.

Owner steps left: none. Orchestrator: bump the cache key for app2.css (the static-versions test does not need a bump to pass here, but the CSS changed).
