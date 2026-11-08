# 0998 report

Status: review

## Files changed
- App/app/host_i18n.py: "Booked"/"Obsazeno" wording, new key calendar.no_forms (en and cs)
- App/app/templates/_dashboard_calendar.html: labels no_forms and blocked; CSS key 20261107-0998; JS key 20261107-0998
- App/app/static/dashboard-calendar.js: placeholder label to "Booked"; guest line "No guest forms yet" when 0 forms
- App/app/static/dashboard-calendar.css: focus and bottom-padding rules appended
- App/tests/test_host_i18n.py: one assertion (Booked / Obsazeno)
- App/tests/static_versions.json: regenerated with --write

## Commands (last 5 lines)
- test_dashboard_calendar, browser, i18n, em dashes, static versions (`UBYHOST_REQUIRE_BROWSER=1`, `-rs`): `147 passed, 1 warning in 153.44s`, 0 skipped
- test_layout_lint_browser.py + test_design_guardrails_browser.py: `15 passed in 285.09s`, 0 skipped

## Section 7
- [x] Booked/Obsazeno wording and legend "Booked or waiting" (seen on dashboard 1280 shot)
- [ ] Sheet "No guest forms yet": not visually verified
- [ ] Calendar page 390/768/1280 screenshots: not produced (see Deviations)
- [x] Layout lint zero findings, 0 skipped

## Screenshots (observed, dashboard shots only)
- 390: stays and check-in cards readable; bottom tab bar and help button visible; no blue border seen.
- 768: layout clean; calendar card not in view.
- 1280: calendar bars show "Airbnb", "Stay", "Stay · 1"; legend "Booked or waiting" present.

## Not attempted
Pill spill past day edge, shorter pill labels, hiding floating buttons (padding only).

## Deviations
- Anchor for dashboard-calendar.js was at line 666, not 667; text matched verbatim.
- The test required the JS cache key bumped too (`dashboard-calendar.js?v=`), done in the same template.
- The i18n test went in App/tests/test_host_i18n.py (no file referenced the keys before).
- Test run modified docs/tasks/screenshots-0908 PNGs; restored with git checkout, not committed.
- Calendar-page (`?cal_view=calendar`) screenshots and sheet check were not done; lint shots taken were dashboard pages.
- Not pushed; no PR. Commits are local on claude/project-thread-d67hsx.

## Owner steps left
Review and merge through scripts/merge-pr-on-green.sh once a PR is opened; look at the calendar sheet on a phone.
