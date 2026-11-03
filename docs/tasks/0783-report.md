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

## 0784

Status: blocked. Done: rows 1, 2, 3, 4, 6, 7 and the cache key, catalog check and screenshots. Left: rows 5 and 8 (stop rules, below). Not pushed; no PR opened.

Commits: aa90dcd (row 1), 5b4f1ed (row 2), c821924 (row 3), 39b7c94 (row 6), 54bff62 (row 7), 22d6906 (cache key).

Counts (last run, `tests/` files from §4 plus 0705 and static versions):
- §4 first command: 176 passed, 3 failed, 0 skipped (before the fixes: 11 failed, 168 passed).
- §4 0710 command (`-k "settings or entities or privacy_requests or archive"`): 24 passed, 0 skipped.
- `scripts/design_lint.py`: OK, no catalog change needed.
- `scripts/context_lint.py`: FAIL on `docs/tasks/0784-settings-area-v2-old-shell-tests.md`: missing `## 7. Acceptance`, `## 8. Stop and ask`, `## 9. Report` (the brief numbers them 5, 6, 7). Not edited, the brief is out of scope.
- `test_static_versions.py --write`: 41 files; `app2.css` key `20261102-0783a`.
- Screenshots: `-k screenshots` 1 passed. Files in `docs/tasks/screenshots-0710/` (settings, entities, privacy_requests, archive at 390 and 1280). PNGs not committed.

What each row needed:
1. test_0705: `/settings` is v2 now; the non-v2 check uses `/invoices` (no `set v2`). Passes.
2. test_alert_stack: `/settings` rendered no alert stack. Added `{% include "_host_alerts.html" %}` at the top of the settings body (as `reservations.html` does). The test now checks the stack is inside `main` (ancestor), not a direct child. Deviation: I dropped the "stack before feedback region" order check, because v2 `/` puts the stack in the page body after the feedback region. Owner may want to confirm.
3. test_design_properties: `/entities` renders no tab strip (`entities.html` empties the `tabs` block). Asserted `body.v2` and `aside.side#app-sidebar` instead of `data-sub-tabs`. Deviation from the brief's "tab strip markup".
4. test_design_settings archive chips: passes unchanged.
5. test_design_shell (both tests): STOPPED, not changed. The v2 sidebar (`_shell_v2.html`) has inline SVG icons with no `data-icon` (lucide) attributes. It also has no `/privacy-requests` or `/settings/archived` links, which the first test lists. Brief §8 says stop.
6. test_operator_naming: restored `<p class="sub">{{ t('entities.lede') }}</p>` in the v2 head of `entities.html`. Test unchanged; both tests pass.
7. test_pwa: dropped only `href="#settings-group-phone"`. Passes.
8. test_signed_in_chrome support line: STOPPED, not changed. The v2 footer (`_shell_v2.html`, support nav link with mailto, then the account block) has no `host-rail-bottom`, no `host-account` disclosure and no legal link row. Brief §8 says stop.

Owner steps left: decide rows 5 and 8 (for example, add the missing hrefs and lucide icons to the v2 sidebar, or accept a changed assertion). Run `context_lint` after fixing the 0784 brief's section numbers. The tracked PNGs under `docs/tasks/screenshots-0710/` were regenerated in the working tree and are not committed; restore or keep them as the owner prefers.
