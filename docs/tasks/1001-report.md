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
