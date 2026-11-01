# 0713: shell-wide v2 fixes every page needs (row menu, hover, rail, banners)
Status: todo
Depends on: 0711, 0712 | Base commit: claude/project-thread-50hyv5 (cb3671c) | Branch: task/0713-v2-shell-fixes
Executor: Haiku 5.5 | Fits one session: 30 tool calls

## 1. Objective
Fix the problems that hit every page on the v2 shell, so the page threads (Ubytování, stays, cleaning, stay fee) don't each patch them. All fixes go in `App/app/static/app2.css` (scoped under `body.v2`) or in the tests named below. Overview (`/`) is the test page.

## 2. Context and decisions (orchestrator, 2026-11-01)
- Row menu (`row_menu_begin`/`row_menu_end` in `App/app/templates/_components.html`; JS `positionRowMenu` in `App/app/static/app.js` ~line 437 moves the panel to `<body>` and sets `position:fixed`):
  - At 2000 px the design guardrail reports `menu-off-screen` with a 475 px tall panel. Likely cause: `body.v2 .row-menu-item{display:block}` overrides the `hidden` attribute, so hidden items show. Add `body.v2 .row-menu-item[hidden]{display:none}` and check the panel height drops.
  - Below 1024 px `app.js` leaves placement to CSS ("bottom sheet of host2.css"), but v2 pages do not load host2.css. Add a v2 bottom sheet in app2.css: `@media (max-width:1023px){ body.v2 .ui-menu-panel.is-open{position:fixed;left:8px;right:8px;bottom:8px;top:auto;min-width:0} }` and items at least 44 px tall there. Check the panel's class names first (`grep -n "ui-menu-panel\|row-menu-panel" App/app/templates/_components.html`).
  - The row-menu trigger sits past the table's right edge at 360 px and also at 768 px and above on a table page. Find why with one `page.evaluate` (trigger rect vs its `td`, `table`, `.card` rects, and the td's computed width/padding). Fix in app2.css so the trigger stays inside the card at every width (e.g. last column `width:1%; white-space:nowrap; padding-right:8px`, trigger `margin:0`).
  - Do NOT change `app.js` (owned by another thread). If a fix truly needs JS, stop and report.
- `App/tests/test_host_ux_acceptance.py::test_page_families_through_rail_cards_search_and_back` clicks `.sidebar-nav a[href=...]`. Make the test find the rail link in either shell: selector `.sidebar-nav a[href="X"], .side-nav a[href="X"]`. Check `_shell_v2.html` for the nav container class and use it.
- `test_0284_states_browser::test_hover_changes_every_clickable_thing`: every clickable thing in v2 must visibly change on hover. Run it on `/`, read which elements fail, add `:hover` rules in app2.css (e.g. `.btn:hover` slightly darker coral `#b83d28`, `.btn.ghost:hover` `#e6e6e1`, quiet links underline, `.nav:hover` already exists, table rows already have one, row-menu trigger background `var(--side2)`).
- `test_onboarding_wizard_browser::test_phone_guest_sharing_and_clear_setup_actions`: `.onboarding-banner-setup-link` has no v2 style (transparent). Style it in app2.css like `.btn` (coral pill, white text, 44 px tall below 1024).
- `test_0385_phone_card_open_browser::test_phone_card_open_has_its_own_line`: run it on `/`, read the assertion, and fix in app2.css if it is a v2 styling gap; if it asserts old markup that v2 removed on purpose, point it at a non-v2 page (`/reservations`) and say so in the report.
- After the fixes, `tests/test_0710_v2_mockup_match_browser.py` must still pass.
- `base.html`: bump only the `app2.css` key to `20261101-0713`, then from App/: `.venv/bin/python tests/test_static_versions.py --write | tail -1`.

## 3. Files
`App/app/static/app2.css`, `App/app/templates/base.html` (key only), `App/tests/static_versions.json`, `App/tests/test_host_ux_acceptance.py`, `App/tests/test_0385_phone_card_open_browser.py` (only if section 2 says so), report `docs/tasks/0713-report.md`.

## 4. Steps
1. Row menu fixes. Run the guardrail test. Commit `0713 step 1: v2 row menu`.
2. Rail selector, hover, onboarding banner link, 0385. Commit after each two.
3. Key bump + manifest. Run section 6. Commit the report.

## 5. Do not touch
`App/app/static/app.js`, `dashboard.html`, other stylesheets, routes, `v2_mockup.py`.

## 6. Commands (from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_design_guardrails_browser.py tests/test_host_ux_acceptance.py tests/test_0284_states_browser.py tests/test_onboarding_wizard_browser.py tests/test_0385_phone_card_open_browser.py tests/test_0710_v2_mockup_match_browser.py tests/test_static_versions.py -q --tb=line -rs 2>&1 | tail -40` (0 skipped). Repo root: `python3 scripts/design_lint.py | tail -1; python3 scripts/context_lint.py | tail -1`.

## 7. Acceptance
All listed tests pass, 0 skipped. Lints OK. `git diff --stat cb3671c` shows only section 3 files.

## 8. Stop and ask
Stop if a fix needs `app.js`, or if a listed test also fails on `origin/main` (then it is not ours; note it).

## 9. Report
`docs/tasks/0713-report.md`: status, test tails, cause and fix per item, deviations.
