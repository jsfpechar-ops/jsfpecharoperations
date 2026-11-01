# 0533 report

Status: review (all green except the known items below)

## Commits (this branch, after 17313da "0533 step 4")
- bdd3856 0533: phone_box_skip for text-dependent sizes (v2_mockup.py, 0710 test call site; properties entry: .card.prop .st.g/.st.r width, .cover .ini width, .card.prop height)
- 6b019f3 0533 step 4b: cover colours as classes, catalog (apartments.html cover c0/c1/c2 classes, app2.css rules, catalog classes, base.html key 20261101-0533w-0718, static_versions.json)
- Screenshots and this report: commit "0533 step 5: screenshots and report"

## Tests (from App/, UBYHOST_REQUIRE_BROWSER=1, PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers)
- Group 1: other files all passed (98 tests). 0710 file after the fix: `3 failed, 30 passed in 43.12s`. Failures: overview-768, properties-768, menu-320 (known).
- Group 2 (without test_0385, deleted): `105 passed in 235.16s`, 0 skipped.
- design_lint: OK. context_lint: OK (warning only: 175 App/ commits since status.md update).
- properties-320 and properties-390 pass in 0710 now.

## Known remaining failures
- overview-768, properties-768 (desktop selectors at 768), menu-320 (.card.me height): not in this brief.

## Screenshots (docs/tasks/screenshots-0533/)
- app-390.png, app-320.png, app-768.png: /apartments?lang=cs (full page)
- mockup-390.png, mockup-320.png: mockup screen nemovitosti (full page, 800 ms wait)

## Diff stat (a6df9df..HEAD, excluding screenshots)
```
 docs/tasks/screenshots-0710/mockup-today-1280.png  | Bin 147302 -> 136402 bytes
 docs/tasks/screenshots-0710/overview-1280.png      | Bin 130406 -> 132775 bytes
 docs/tasks/screenshots-0710/overview-390.png       | Bin 101844 -> 105997 bytes
 docs/tasks/screenshots-0710/overview-768.png       | Bin 143889 -> 139962 bytes
 docs/tasks/screenshots-0718/menu-390.png           | Bin 0 -> 47945 bytes
 docs/tasks/screenshots-0718/overview-390.png       | Bin 0 -> 113101 bytes
 docs/tasks/screenshots-0718/overview-768.png       | Bin 0 -> 127396 bytes
 go/internal/mail/submission_problem.go             | 429 ++++++++++++++++
 go/internal/mail/submission_problem_test.go        |  93 ++++
 go/internal/ubyport/notify.go                      | 330 ++++++++++++
 go/internal/ubyport/notify_test.go                 | 317 ++++++++++++
 go/internal/ubyport/submit.go                      | 316 ++++++++++++
 go/internal/ubyport/submit_test.go                 | 272 ++++++++++
 scripts/design_lint.py                             |   1 +
 105 files changed, 4569 insertions(+), 186 deletions(-)
```

## Deviations
- No guest capacity (".cap", "4 hosté") on the phone card: the app stores no guest count.
- Inactive label not shown on the phone card.
- Test selectors use .card.prop .st.* (not .props-phone .st.*).
- missing_ok for ".prop .in small" kept: the 0710 app fixture renders no address line, so the small is missing in the app. The seed in App/app/demo.py does have an address, so the entry's reason is only true for the test fixture. Owner to decide.
- phone_box_skip added as allowed by the coordinator (width/height only, reasons printed).
- Not done: the 0530 test addition from brief section 3 (phone cards render one a.card.prop per property). Still open.
- Screenshots were taken with a temporary pytest file (deleted), since the 0710 screenshot helper has no phone view support.
- Owner steps left: none; no push (branch is local only).
