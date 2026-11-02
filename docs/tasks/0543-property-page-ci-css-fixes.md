# 0543: property pages on v2: small layout fixes that CI browser tests found
Status: todo
Depends on: 0542 (this branch) | Branch: claude/project-thread-819gyo
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
CI browser tests found real layout gaps on the v2 property page and list. Fix them in CSS, and point each test at the v2 markup where only its selector is stale.

## 2. Context
Orchestrator decisions (one item per test):
1. `tests/test_0284_states_browser.py`: the aside rows (`aside.preview .pv a.r`) do not change on hover. Give them a hover and focus-visible state on v2, in the 0536/0540 page block of `App/app/static/app2.css`: background `#f6f6f4`, radius 8px, no layout shift. The test selector is already `aside.preview .pv .r`.
2. `tests/test_wp28_geometry.py` line ~136: the calendar remove button area must be `overflow:auto` (it is `visible` on v2, so long feed URLs can overflow). Read what element the test measures and give it `overflow:auto` (or `overflow-x:auto`) on v2 in the page block.
3. `tests/test_wp28_geometry.py` line ~220: the operator signature block border is `groove` (the browser default for `fieldset`) and must be `solid`. On v2 in the page block: `border:1px solid var(--line);border-radius:12px;padding:12px` for that element.
4. `tests/test_0282_signature_dialog_browser.py`: at 390 px the signature canvas is 300 px wide, and the test needs at least 340. Make the canvas fill its container width on v2 (`width:100%` with the height scaled the same way the old host.css did; grep `signature` in `App/app/static/host.css` for the old rule, and copy only what the canvas needs). Do not change the JS that draws on it. If the JS reads canvas width/height attributes, check that drawing still lines up (the test checks this).
5. `tests/test_host_controls_browser.py` line ~211: the v2 list header action is `a.btn` in `.props-head` from 1024 px. Below 1024 px it is hidden by design, and the phone action is `.props-top a.round`. Measure `.props-top a.round` below 1024 and `.props-head a.btn` from 1024 (≥44 px below 1024). Test selector only.
6. `tests/test_0251_tablet_browser.py`: a tap on `a.r[href="#sec-lock"]` or `a.r[href="#sec-police"]` times out at line 107/109. Find why: probably the aside is below the fold at the tablet width, or the link is covered. If covered by something on our page (save bar, Havel bubble), fix the CSS. If it is only off screen, scroll into view first (test change).
7. `tests/test_host_help_browser.py` (2 failing): the `?` help-tip button is hidden on purpose inside property-page `details` on v2 (0536 item 6). For the property page, assert that the hint text is visible under its input. Keep the button checks for pages that still show the button.

## 3. Files
`App/app/static/app2.css` (page block only; key bump in `App/app/templates/base.html`; `--write` the manifest), the seven test files above (section 8). Report: new section "0543" at the end of `docs/tasks/0536-report.md`.

## 4. Steps
1. Items 1 to 4 CSS; key bump, `--write`. Commit.
2. Items 5 to 7. Commit.
3. Run section 6. Commit the report.

## 5. Do not touch
Templates, JS, routes, other pages, shared rules. No new dependency. Do not touch test_host_unsaved_changes, test_property_navigation, test_onboarding_* (another brief owns them).

## 6. Commands (from `App/`)
`export UBYHOST_REQUIRE_BROWSER=1 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, then each of the seven files with `-q --tb=line -rfs -p no:cacheprovider -k "not webkit" 2>&1 | tail -8` (webkit is not installed here; say so), then `tests/test_0534_property_page_v2.py tests/test_static_versions.py tests/test_0710_v2_mockup_match_browser.py -k property`, ruff `--select E9,F63,F7,F82,F401,F841` on app tests tools, design_lint and context_lint from the repo root.

## 7. Acceptance
The seven files pass on chromium with 0 skipped; 0710 `property` still passes at every width.

## 8. Stop and ask
Tests may get a selector change, or a v2 branch that checks the same outcome (list each). Stop if a save/POST test fails, or if a fix needs a template or JS change.

## 9. Report
Section "0543" in `docs/tasks/0536-report.md`. Stage by name, never `git add -A`; never commit `App/.venv`. Do not push. Hand back with SubagentHandback; never post to the user.
