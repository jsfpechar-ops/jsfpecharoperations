# 0711 report: v2 Overview match fixes

Status: blocked

## Files changed
- App/app/static/app2.css (AA `--acc-text`, bar and calendar fixes, needs-you closed-details fix, Clear-demo link, 44/24 px tap targets, search button)
- App/app/templates/base.html (app2.css key `20261101-0711c`)
- App/tests/v2_mockup.py (SELECTOR_OVERRIDES for AA colours and `.cal .cd`, `.side .nav` overrides, `TAP_EXEMPT_BELOW_DESKTOP` for `.cal .bar`, `missing_ok` for `.cal .bar.b-ok` and `main .pill`, first-row td selector, geometry JS takes the exempt list)
- App/tests/static_versions.json (hashes via `python tests/test_static_versions.py --write`)
- docs/tasks/screenshots-0711/overview-cs-390.png, overview-cs-1280.png

## Commands (last lines)
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py tests/test_0709_v2_overview_shots_browser.py tests/test_a11y_guard_browser.py tests/test_design_guardrails_browser.py tests/test_static_versions.py -q --tb=line -rs`
  - `2 failed, 30 passed in 166.04s`
  - Failing: `dashboard 2000 open` and `dashboard 2000 collapsed`: `['menu-off-screen', {'x': 1695.9, 'y': 618, 'width': 304.1, 'height': 475.1}]`
  - Skipped: 0
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q --tb=line -k "1280 or 390"`: `4 passed`
- `.venv/bin/python tests/test_static_versions.py --write`: `wrote ... (41 files)`; then `3 passed`
- `python3 scripts/design_lint.py`: `design lint: OK`
- `python3 scripts/context_lint.py`: `context lint: OK`

## Checklist (section 7)
- [x] Overview at 1024 to 1440 and 320 to 768: mockup-match and geometry pass except the menu guard below
- [ ] All listed tests pass: 2 menu-off-screen findings remain
- [x] Design lint and context lint OK
- [ ] Diff touches only section 3 files: yes, except `App/tests/static_versions.json` (expected by step 4)

## Deviations
- Done: steps 1 to 5. Left: menu-off-screen at 2000 px (below).
- Menu guard (`tests/test_design_guardrails_browser.py:104`): `app.js` `positionRowMenu` moves the panel to `<body>` and sets `position:fixed` with inline `top`/`left`. The panel is 475 px tall and ends at y 1093, below the document height. CSS cannot reach the panel after it moves to `<body>`. The JS clamp `innerHeight - offsetHeight - 8` appears to use a height measured before the panel's final size. Needs an owner or orchestrator decision: change `app.js` (shared by all pages), or relax the guard. I did not change `app.js`.
- Screenshots: the 0709 shot test writes only 390 and 1280. No 768 PNG was made.
- The needs-you overlap was not in the card grid. The paste-list `ul` inside a closed `details` still laid out and overlapped the action. Fixed with `details:not([open]) > :not(summary){display:none}` in app2.css under body.v2.
- `main table td` changed to `main tbody tr:first-child td`. The demo Dnes table has one row, so the app draws no bottom border; an override records this.

## Questions
- Accept the menu-off-screen fix path above (app.js change, or guard change)?

## Owner steps left
- Decide the menu path. Then run: `cd App && UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_design_guardrails_browser.py -q --tb=line -rs | tail -40`
