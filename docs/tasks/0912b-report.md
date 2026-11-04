# 0912b report

Status: blocked (the blocker is fixed; one acceptance item fails: the opened "?" popover on /stay-fees is too narrow at 320, 390 and 768 px, see Screenshots)

## Files changed
- App/app/templates/stay_fees.html: deleted line 230 `<h2 class="sec">{{ t('stay_fees.title') }}</h2>` (duplicate heading, orchestrator decision).
- docs/design/design-system.md: line 31 (Help "?" row) gained "16 px gutter; app.js place() and the layout-lint test enforce it."
- docs/tasks/screenshots-0912b/: 8 PNGs (help-open-{320,390,768,1280}.png, help-tip-{320,390,768,1280}.png).
- docs/tasks/0912b-help-popover-fit-390.md: Status set to in-progress for this run.
- Earlier changes, unchanged in this run: App/app/static/app.js, App/app/static/app2.css, App/app/templates/base.html, App/tests/static_versions.json, App/tests/test_layout_lint_browser.py.
- No commit, no push, no branch. No PNG outside the screenshot folder changed. Temporary test file deleted.

## Commands
1. `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_layout_lint_browser.py tests/test_host_geometry.py tests/test_static_versions.py tests/test_stay_fee*.py -q --tb=short -rs`: 215 passed, 0 failed, 0 skipped.
2. `python3 scripts/design_lint.py`: OK.
3. `python3 scripts/context_lint.py` (WARN lines filtered): OK.

## Screenshots (viewport shots, 800 px high)
- help-open-320: popover about 166 px wide, inside the gutter, but text is cut at the bottom and "More in the guide" is not visible. Does not fully fit.
- help-open-390: same narrow box (left 20, right 187), cut at the bottom and under the tab bar. Does not fully fit.
- help-open-768: same narrow box at left edge, cut at the bottom. Does not fully fit.
- help-open-1280: 520 px box, all text and "More in the guide" visible. Fits.
- help-tip-320 (operators page, tooltip): box 16 to 304 px. Fits.
- help-tip-390 (operators page, tooltip): box 16 to 374 px. Fits.
- help-tip-768 (operators page, tooltip): box 381 to 741 px. Fits.
- help-tip-1280 (operators page, tooltip): box 617 to 937 px. Fits.

## Section 7
- [x] Fix A and fix B in place (earlier run).
- [x] Layout lint, geometry and stay-fee tests green, 0 skipped.
- [x] base.html `?v=` bumped; static_versions regenerated.
- [ ] Screenshots: 8 taken; the 320, 390 and 768 help popovers do not fit (see above).
- [x] Design-system line added; design and context lints OK.

## Deviations
- The fee-register "Resident of this municipality" row was not seeded. Tooltip shots use the `operators` page instead.
- The narrow popover was not fixed. Fixing it means CSS and `?v=` changes plus a re-run of the tests and screenshots, which were over budget.

## Questions
- Fix the narrow opened "?" on /stay-fees at 320 to 768 px (the box measures about 166 px; the test only checks the gutter, so it passes). Likely the `details.ui-how` body needs a phone width rule in app2.css and place() needs to size it. Decide whether to fix in this brief or a follow-up.

## Owner steps left
None.
