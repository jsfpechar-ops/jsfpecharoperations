# 0783 report

Status: blocked

## Commits
- 0204e06 0783 item 1: settings alerts wait without string predicate (CSP eval)
- e061286 0783 item 2: archive chips keep ui-chip beside chip
- item 3 (partial): restore static help tips inside details (body.v2 details .help-tip-body, app2.css)

## Files changed
- App/tests/test_push_settings_browser.py (item 1)
- App/app/templates/settings_archived.html, App/tests/test_design_settings.py (item 2)
- App/app/static/app2.css (item 3)

## Item 1 cause
The test's `wait_for_function` takes a string predicate. Playwright compiles it with eval in the page, and the page CSP (script-src without 'unsafe-eval') blocks it: EvalError. The page itself is fine. Fix: poll `page.evaluate(...)` in a loop with a 30 s limit. Test file: 11 passed.

## Item 2
Chips now `class="chip ui-chip"`; test assertion changed to match. design_settings: 3 passed.

## Item 3 (not fixed)
`test_host_wide_help_tips_are_wired_reachable_and_fit[360]` and `[390]`: 2 failed, 2 passed (-k fit). Failing tips: property-guests `communication-help` (360), entities `entity-invoice-help` (390). Both pages render without `body.v2` (base.html sets it only when `v2` is true), so app2.css v2 rules do not apply. The base popover rule is `.help-tip[data-js] > .help-tip-body {position: fixed}` in App/app/static/host.css. Full help file: 4 passed, 2 failed.

## Not done
- Item 4 (docs/design/catalog.json, design_lint).
- Cache key bump in base.html and static_versions.json, and test_static_versions.
- Section 6 commands: 0710 mockup suite, settings_technical, entity_editor_*, privacy_requests, static_versions, design_lint, context_lint: not run.
- Screenshots: not taken.

## Deviations
Done: steps 1 to 2 (item 1, item 2). Item 3 partial. Left: item 3 failures, item 4, cache bump, section 6 runs, screenshots. Stopped at the 25-tool-call cap.

## Questions
- Item 3: should the two failing pages get `body.v2` (v2 port), or should host.css `.help-tip[data-js] > .help-tip-body` go static below 1024 px? host.css is not in the brief's file list.

## Owner steps left
- Decide the item 3 question above, then run the executor again for item 3, item 4, the cache bump and the screenshots.
