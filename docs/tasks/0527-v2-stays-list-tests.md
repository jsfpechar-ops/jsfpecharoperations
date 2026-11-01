# 0527: Stays list v2, part 2: shared design test at six widths, old tests, screenshots
Status: todo
Depends on: 0526 | Base commit: task/0526-v2-stays-list head | Branch: task/0527-v2-stays-list-tests
Executor: Haiku 5.5 | Fits one session: 30 tool calls

## 1. Objective
Prove the v2 stays list matches the mockups at every size (owner: "rigorous geometry and UX/UI design tests", "phone, tablet, everything") and bring the old stays tests up to date.

## 2. Context
- Shared test: `App/tests/v2_mockup.py` (`PAGES`) and `App/tests/test_0710_v2_mockup_match_browser.py`. It compares computed styles and box metrics with `docs/design/mockup/ubyhost-redesign-v2.html` (view key) at >= 1024 and with `docs/design/mockup/ubyhost-phone-v1.html` (`phone_view`) at 320 and 390, and checks geometry at 320, 390, 768, 1024, 1280, 1440 (no sideways scroll, nothing escaping a card, no overlapping text, tap targets, one h1, menus on screen). Copy the shape of the `overview` and `menu` entries.
- 0526 report (`docs/tasks/0526-report.md`) lists the old assertions that fail on removed markup.

## 3. Files
`App/tests/v2_mockup.py`, existing stays tests named in the 0526 report and the commands below, `App/app/static/app2.css` and `App/app/templates/reservations.html` only to fix a real mismatch the test finds (copy values from the mockup), base.html key + manifest if CSS changes, screenshots `docs/tasks/screenshots-0527/`, report `docs/tasks/0527-report.md`.

## 4. Steps
1. Add a `PAGES` entry: name `stays`, path `/reservations?range=all`, view `stays`, phone_view `pobyty`; selectors `.head h1`, `.head .btn`, `.head .btn.ghost`, `.chips .chip`, `.chip.on`, `main table th`, `main table td`, `main td small`, `main .pill`; phone_selectors `.tabs`, `.tab.on`, `.top .round`, `.big`, `.chips .chip`, `.chip.on`, `.grp`, `.list .row`, `.row .av`, `.row .t b`, `.row .t small`, `.row .pill`, `.list .link`. Data-dependent ones go to `missing_ok` with a reason. Run the shared test; fix each mismatch in app2.css/template by copying the mockup value (never by loosening the test). Commit `0527 step 1`.
2. Old tests: update only assertions on markup 0526 removed (tab strip, `ui-table`, `row-open`, `stay-col-*` widths, old chip labels, `.stays-view` phone cards) to the new markup, keeping each test's intent (pill + deadline visible on every row, no overflow, tap sizes, archive restore, empty state). Delete a test only if its whole subject is gone, and say so. Commit `0527 step 2`.
3. Screenshots: `/reservations?range=all&lang=cs` at 320, 390, 768, 1024, 1280, 1440, and the mockups' stays view at 1280 and pobyty screen at 390, all into `docs/tasks/screenshots-0527/` (name `app-<w>.png`, `mockup-1280.png`, `mockup-390.png`). Read the 390 and 1280 pairs once each and note differences in the report. Commit `0527 step 3`.

## 5. Do not touch
The shared test file's checks and tolerances, `_shell_v2.html`, other pages' PAGES entries, JS.

## 6. Commands (from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, `UBYHOST_REQUIRE_BROWSER=1`)
`.venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k stays -q --tb=short -rs 2>&1 | tail -30`, then `.venv/bin/python -m pytest tests/test_0523_stays_list.py tests/test_design_stays.py tests/test_archive_stays_on_page.py tests/test_stays_empty_workspace.py tests/test_host_list_layouts_browser.py tests/test_host_list_page_layout_browser.py tests/test_host_wide_geometry_browser.py tests/test_host_filter_panels_browser.py tests/test_0199_phone_geometry_browser.py tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py tests/test_static_versions.py -q --tb=line -rs 2>&1 | tail -30`. Repo root: `python3 scripts/design_lint.py | tail -1; python3 scripts/context_lint.py | tail -1`.

## 7. Acceptance
All pass, 0 skipped.

## 8. Stop and ask
Stop if matching the mockup would hide the police deadline or a filing action, or if a geometry rule fails for a reason in the shared shell (report it; the Overview thread owns the shell).

## 9. Report
`docs/tasks/0527-report.md`: status, test tails, edited/deleted assertions, screenshot paths, remaining visual differences.
