# 0539: property page: two-column fields on the computer, remove the old tab JavaScript
Status: todo
Depends on: 0536 (this branch) | Branch: claude/project-thread-819gyo
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
`docs/tasks/screenshots-0536/app-1280.png` shows every field of "Základní údaje" full width, one under another. The mockup (`mockup-1280.png`) puts fields two to a row. Make the field grids work on v2 from 1024 px. Also delete the JavaScript for the removed property tabs, in this PR (agreed with the JS thread).

## 2. Context
- Cause: the fields sit inside `.grid.two` (`_property_identity_fields.html`, arrival/departure in `_property_editor.html` line ~71, lock times line ~209) and `.grid.property-address-grid` (`_property_address_fields.html`). `.grid` has no style on v2 (host.css does not load there). The 0536 rule in app2.css (`grep -n "0536 items 1-7"`) makes `.property-section` a 2-column grid but sends every `.grid` to full width.
- Fix in the 0536 block, from 1024 px, scoped to `body.v2 .property-section`:
  - `.grid` becomes `display:grid;grid-template-columns:1fr 1fr;gap:0 12px`.
  - Its `.field` children have no extra margins beyond the shared 12 px bottom gap.
  - A `.field` holding a textarea, or one that is the only child of its grid, spans `1/-1`.
  - Remove inline `max-width` limits on v2 by a CSS override (`body.v2 .property-section .field[style*="max-width"]{max-width:none}`), so selects line up with the inputs.
  - Below 1024 px everything stays one column, as now.
- Dead JS: in `App/app/static/app.js`, `initPropertyViews` (line ~2018) and `initInlineTiming` (line ~588), with their calls at ~2343/2346. Before deleting, grep each data attribute or selector they read across `App/app/templates`. Delete a function only if nothing renders its markup any more. If something still renders it, stop and report which template does. Bump the app.js `?v=` key in base.html and run `--write`.

## 3. Files
`App/app/static/app2.css` (0536 block only), `App/app/static/app.js` (the two functions and their calls), `App/app/templates/base.html` (keys), `App/tests/static_versions.json` (`--write`). Tests that call the removed functions by name, if any (section 8). Screenshot `docs/tasks/screenshots-0539/app-1280.png` (full page, `/apartments/<first id>?lang=cs`). Use the temp-test method: copy the imports from `tests/test_0710_v2_mockup_match_browser.py` (`_open_app`, `_path`, `PAGES` from `tests.v2_mockup`, fixtures from `tests.test_host_quiet_dashboard_browser`), and delete the temp file afterwards. Report: section "0539" in `docs/tasks/0534-report.md`.

## 4. Steps
1. CSS, key bump, `--write`. Commit.
2. Dead JS, key bump, `--write`. Commit.
3. Section 6, screenshot. Commit.

## 5. Do not touch
Templates, routes, field names, other pages, shared rules, other JS functions. No new dependency.

## 6. Commands (from `App/`)
`export UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, then `.venv/bin/python -m pytest tests/test_0534_property_page_v2.py tests/test_0531_property_page.py tests/test_property_hub.py tests/test_static_versions.py tests/test_0710_v2_mockup_match_browser.py tests/test_0503_page_inits_once_browser.py -q --tb=short -rfs -p no:cacheprovider 2>&1 | tail -30`, then `grep -ln "initPropertyViews\|initInlineTiming" tests/*.py` and run those, ruff `--select E9,F63,F7,F82,F401,F841` on app tests tools, design_lint and context_lint from the repo root.

## 7. Acceptance
The screenshot shows Název ubytování next to the operator select (or the identity grid in two columns), Čas příjezdu next to Čas odjezdu, and the address fields two to a row. Tests pass with 0 skipped (known shared failures listed: 0710 overview-320/390). No horizontal scroll at 1024.

## 8. Stop and ask
A test that only checks the removed functions exist may be deleted (list it). Stop if a test on another page fails, or if a removed function's markup still renders.

## 9. Report
Section "0539" in `docs/tasks/0534-report.md`. Stage by name, never `git add -A`; never commit `App/.venv`. Do not push.
