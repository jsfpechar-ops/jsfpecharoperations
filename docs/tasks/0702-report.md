# 0702 report

Status: review

Push and PR: not done. The executor brief asks for one PR, but this run was told not to push. The owner or orchestrator opens it from branch task/0702-overview-calendar-card.

## Commits
- 0702 step 1 (c93cc6a): is-fixed-days toggle line in syncControls(); node --check OK
- 0702 step 2 (cbcf0d9): CSS block at end of dashboard-calendar.css; design_lint OK
- 0702 step 3 (ef3dfec): version key 20261101-0702 for CSS and JS, static_versions.json --write; 3 passed
- 0702 step 4 (4ba569f): test_0702_overview_calendar_card_browser.py, specificity fix, CSS key bumped to 20261101-0702b, manifest rewritten
- 0702 step 5: screenshot test and screenshot, this report

## Tests (from App/, PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers)
pytest tests/test_0702_overview_calendar_card_browser.py tests/test_0521_overview_14_days_browser.py tests/test_dashboard_calendar_browser.py tests/test_dashboard_calendar.py tests/test_dashboard_phone_browser.py tests/test_cleaning_browser.py tests/test_static_versions.py -q --tb=short -x -rs
  86 passed in 106.20s, 0 skipped
design_lint.py: design lint: OK
context_lint.py: context lint: OK

## Diff stat (the five 0702 commits, HEAD~5 to HEAD)
App/app/static/dashboard-calendar.css              |  33 ++
 App/app/static/dashboard-calendar.js               |   1 +
 App/app/templates/_dashboard_calendar.html         |   4 +-
 App/tests/static_versions.json                     |   8 +-
 .../test_0702_overview_calendar_card_browser.py    | 116 +++++
 docs/tasks/0702-report.md                          | 470 +++++++++++++++++++++
 .../overview-0702-cs-1280-calendar.png             | Bin 0 -> 31352 bytes
 7 files changed, 626 insertions(+), 6 deletions(-)

## Screenshots
- docs/tasks/screenshots-0702/overview-0702-cs-1280-calendar.png (/?lang=cs, 1280 px, calendar card). The 390 px shot was not required by the brief.

## Deviations
1. Colours: design_lint S1 forbids raw hex, so tokens were used. #fff gives --surface; #fdece8 gives --coral-50 (#fbf0ee); coral text gives --coral-600; #ebebe7 gives --sand-200 (#ececea); ink-3 gives --ink-3; done gives --green-bg and --green; action and ready give --amber-bg and --amber; overdue gives --red-bg (#fcebea) and --red; neutral gives --sand-200 and --ink-500 (not #efefeb and #55554f).
2. The heading reads "Přehled pobytů" (the existing calendar heading), not "Kalendář", as the brief allows.
3. The white card is .cal-gantt-scroll. In 14-day mode the root loses its own border and background, so the heading sits above one card.
4. The toolbar row is a grid on the root: heading left, view switch in the heading, arrows on the right. The period title, property filter, settings button and scale/month/year selects are hidden in 14-day mode. The scale/month/year selects were already hidden by JS in gantt view.
5. The settings button needed a higher-specificity selector, because `.host-workspace .dashboard-calendar .. .btn` display outranked the first rule.
6. The CSS key is 20261101-0702b, not 20261101-0702, because step 4 changed the CSS after step 3 set the key. The JS key is 20261101-0702.
7. The done tone cannot be produced from fixtures (it needs finished reports), so the test adds the is-done class to the first bar and checks the computed background rgb(230, 245, 236) and radius >= 14 px.
8. The screenshot shows only neutral bars. Several tones are not visible in it, so the "several tones" part of step 5 is not met.
9. Commit messages end with Co-Authored-By Claude Opus 5.5, as the owner's instruction asked, not Haiku.

## Questions
- Should the done and overdue tones be checked with real finished reports or a seeded fixture? The current test covers the CSS, not the data.

## Owner steps left
- Open the PR from task/0702-overview-calendar-card and merge with scripts/merge-pr-on-green.sh. Deploy is manual.
