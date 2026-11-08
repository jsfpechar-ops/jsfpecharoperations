# 1003 report

Status: review

## Files changed (steps 1 to 7)

- App/app/static/app.js: step 1 (help_tip width 320), step 2 (`initPageHelp`, deviated, see below)
- App/app/static/app2.css: step 3 (card width/padding/radius), step 4 (card and link rules, plus `.page-help-wrap{position:relative}`)
- App/app/templates/base.html: cache keys `app2.css?v=20261107-1202`, `app.js?v=20261107-1202`
- App/tests/static_versions.json: regenerated
- App/tests/test_host_help_browser.py: new `test_1003_help_tip_opens_under_its_button_on_hover_and_focus`
- App/tests/test_0830_airbnb_pages_browser.py: anchoring and 320 px width asserts in `test_0831G_page_help`

## Commands (last 5 lines each)

- `pytest tests/test_host_*.py -k "help or tooltip"`: 12 passed, 233 deselected.
- `UBYHOST_REQUIRE_BROWSER=1 pytest test_host_help_browser, test_0830_airbnb_pages_browser, test_0896_ux_fixes_browser, test_0505_row_menus_help_tips_once_browser -rs`: 126 passed, no skips (after the fixes below; first run failed the page-help anchoring assert).
- `UBYHOST_REQUIRE_BROWSER=1 pytest test_0786_settings_geometry_browser, test_host_geometry -k help -rs`: 23 passed, 27 deselected, no skips.
- `UBYHOST_REQUIRE_BROWSER=1 pytest tests/test_layout_lint_browser.py -rs`: 2 passed, 1 FAILED (see Blocker).
- `python3 scripts/design_lint.py`: OK. `python3 scripts/context_lint.py`: OK.

## Acceptance (section 7)

- [x] Page "?" opens under its dot (above if no room), hover and focus on mouse, click pins, Esc and outside tap close. Verified in screenshots and tests.
- [ ] Field "?" width: `Math.min(320, ...)` (step 1) breaks the layout-lint 16 px gutter rule on 390 px (see Blocker).
- [x] Card: 12 px radius, 1 px `--line` border, `--shadow-2`, 14 px text, 1.45 line height.
- [x] `aria-expanded`, `role="tooltip"`, `aria-controls` unchanged; no-JS details still opens.
- [ ] Layout lint zero findings: not met.

## Screenshots

- `/tmp/shots/1003/help-tip-1280.png` (page "?" on /apartments, hover, desktop 1280): card sits 8 px under the "?", 320 px wide, numbered list, "More in the guide →" in accent red. Copied to `/mnt/project-files/ux-shots/help-tip-1280.png`.
- `/tmp/shots/1003/help-tip-390.png` (tapped, 390 px): card sits under the "?", right edge inside the viewport with 8 px margin, list readable.
- `/tmp/shots/1003/field-help-1280.png` (field "?" on hover, 1280).

## Deviations

1. Step 2: the page "?" box is `position:absolute` inside `.page-help-wrap` (top calc(100%+8px), flips above when needed), not `position:fixed`. Fixed placement drifted 10 to 150 px in tests after scroll or animation; the wrap is the containing block, so the box moves with its "?". The brief's `place()` origin logic was dropped.
2. Cache keys: `20261107-1202`, not `-1201`. The static writer refused `-1201` because app.js and app2.css changed after that key was set.
3. Step 1 uses 320 px on all phones, as written. Brief §7 says "at most 320 px".
4. Commits carry `Co-Authored-By: Claude Sonnet 5.5` (the message you gave) while the harness reminder says Haiku 5.5. Please pick one.

## Blocker (owner or orchestrator decision)

`test_opened_help_stays_inside_the_viewport` fails at 390 px: every `.help-tip.is-open > .help-tip-body` is 320 px wide, and the lint requires at least 356 px (viewport minus 32). The 360 px cap that step 1 changed made the box pass the lint. Options: (a) restore `Math.min(360, vw - 2*margin)` for phones, which keeps the lint green and contradicts §7; (b) keep 320 and change the lint rule (owner decision). Not changed; the lint was not silenced.

## Fix (owner decision: keep the lint rule, fix the app)

- Field "?" card (`place()` in App/app/static/app.js): below 600 px the width is `min(360, vw - 32)`, so 390 px gives 358 px (lint needs 356). 600 px and up keep `min(320, vw - 32)`. Inside the viewport via the existing clamp.
- App/app/static/app2.css: appended `@media (max-width:599px)` rule for `body.v2 .help-tip .help-tip-body` with the same width.
- Deviation: the owner's `calc(100vw - 24px)` gives 296 px at 320 px wide, which breaks the 16 px gutter lint at 320. `vw - 32` keeps the gutter at every width and passes 356 px at 390.
- Cache keys bumped to `20261107-1203` in base.html; `tests/static_versions.json` regenerated.
- Layout lint: `UBYHOST_REQUIRE_BROWSER=1 pytest tests/test_layout_lint_browser.py -q`: 4 passed, 0 skipped.
- Acceptance: layout lint zero findings is now met.

## Owner steps left

- Commit is local only; no push, no PR.
