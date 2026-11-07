# 1001 report

Status: review

## Files changed (local commits, not pushed, no PR)

- App/app/routes/admin.py: placeholder pill shows platform name, `· N`, or empty with title (step 1)
- App/app/templates/dashboard.html: legend line removed (step 2)
- App/app/static/dashboard-calendar.js: placeholder never shown in sheet (step 3)
- App/app/templates/_dashboard_calendar.html: `blocked` label removed, js key 20261107-1001 (step 4)
- App/app/host_i18n.py: 8 keys removed, en and cs (step 5)
- App/tests/test_host_i18n.py: 2 asserts removed, emptied test function removed (step 6)
- App/app/static/app2.css: copy-link always visible, legend rules removed, calm focus rules (steps 7 to 9)
- App/app/templates/base.html: app2.css key 20261107-1011 (step 10)
- App/app/templates/reservation_detail.html: guest name links to guest page (step 11)
- App/tests/static_versions.json: regenerated with `--write`

## Commands (last 5 lines)

- Mapped pytest, UBYHOST_REQUIRE_BROWSER=1: `162 passed, 1 warning in 303.33s`, no skips.
- Layout lint: `4 passed in 235.96s`, zero findings, no skips.
- `python3 scripts/context_lint.py`: see the commit output below.

## Section 7

- [x] Pill copy removed; tests pass (visual check of pills not done, see below).
- [ ] Copy link visible at 1280 without hover: NOT verified. The properties shot shows no copy-link button; the test targets /apartments.
- [ ] No heavy outline on mouse use: NOT verified visually. Covered by the focus CSS and a passing controls test.
- [x] Guest name is a link to the same URL as "Edit details"; menu markup unchanged.
- [x] Layout lint zero findings, 0 skipped.
- [ ] Design-system checklist: not ticked (no PR opened).

## Screenshots reviewed

- properties-1280: list rows, no copy-link button visible, no focus ring visible.
- dashboard-390: top section fine, no legend line visible in crop.
- stay-detail-390: guest name shown in the guest row, cut off by the bottom nav in the shot.
- Not opened: 768 and 1280 for dashboard, calendar and stay detail; 390 for properties.

## Deviations

- base.html key is 1011, not 1010: app2.css changed again (row focus fix).
- Added `.clickable-row:focus-visible` ring. Brief rules alone failed test_host_controls_browser.py:226 (row.focus() must show an outline).
- Legend comment `/* 0993 */` kept: a `.cd small` rule still sits under it.
- Done: steps 1 to 11. Left: owner review, PR and merge, check copy-link at 1280 on /apartments.

## Owner steps left

- Review the screenshots, then open the PR and merge via `scripts/merge-pr-on-green.sh`.

## CI fixes

- design lint: added `stay-noname`, `stay-noname-action`, `havel-chip-ico`, `havel-chip-text`, `havel-close` (and `guest-name-link`, see below) to `docs/design/catalog.json` with a `class_notes` line each. `python3 scripts/design_lint.py` prints `design lint: OK`.
- `App/app/static/app2.css`: `.cd small` font-size 10px to 12px (layout-lint text 10px, partB-overview 1920 px, `7.11.` day hint).
- `App/app/static/app2.css`: `.ov-cal-more` top margin 0 to 16px, so "Full calendar" is 16px below the paragraph above (partB-overview at all widths).
- `App/app/templates/reservation_detail.html` + `app2.css`: the guest name link in the stay guests table got class `guest-name-link` (`inline-block`, min-height 24px). It was 19px tall (tap target min 24, partD-stay-detail at 1024 to 1920 px). Catalog entry added.
- Cache key: `base.html` app2.css `?v=20261107-1102`; `tests/static_versions.json` regenerated.
- Browser tests: `test_0830_airbnb_pages_browser.py` partB-overview and partD-stay-detail, 14 of 14 pass after the fixes. The other 92 tests in the three named files passed before the fixes.

a11y fix: Copy link button (tbody .btn.sm.ghost.copy-btn) was opacity 0 until row hover, so keyboard focus was invisible. Added `body.v2 tbody tr .btn.sm.ghost.copy-btn:focus-visible` (opacity 1, 2px #d0452d outline, offset 2px) in app2.css; cache key bumped to 20261107-1103. Row focus rule from 1001 untouched.


Hover-only buttons removed: app2.css line 80 (`tbody tr .btn.sm.ghost` opacity 0 and its `tr:hover` reveal) deleted, so Copy link is always visible. Line 1054 (`copy-btn:focus-visible` opacity override) deleted; the standard ring at line 191 still gives the 2px accent ring. The media-query hover rule at ~311 did not exist (only its 1001 comment remained, left in place). Other row-hover reveals not changed: components.css:62 (`tbody tr:hover .row-actions>*` opacity 1, row-actions only). Cache key 20261107-2238; static_versions.json regenerated. Tests: a11y_guard, host_property_controls, layout_lint, host_geometry: 20 passed, 0 skipped (layout_lint re-run alone for fresh shots; test_calendar_platform_controls not needed). Screenshots /tmp/shots/layout-lint/properties-1280.png shows Copy link visible on both rows; stays-1280.png no regression.
