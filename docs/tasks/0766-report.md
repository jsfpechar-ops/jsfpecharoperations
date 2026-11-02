# 0766 report

Status: review
Executor: Haiku 5.5. No commit, no push, no PR (the owner's instruction for this run overrides the brief's commit and PR steps).

## Changed files
- App/app/templating.py: "vi" added to `_PASS_MONTHS` and `_PASS_WEEKDAYS`; new `stay_range` filter (registered next to `pass_date`). Step 1 done first.
- App/app/templates/reservations.html: phone stay card. Named card: b = name, small = dates · internal name. Unnamed: b = dates, small = internal name. `.sav` shows the check-in day when unnamed. Desktop table untouched.
- App/app/static/app2.css: `.host-stay-detail{padding-bottom:180px}` moved out of the phone base rule. New phone rules hide `.stay-head-cta` when it has no form or a.btn, and add the padding only when it has one. `.actbar` is not used in any template, py or js, so it was left alone.
- App/tests/v2_mockup.py: `stays:.stay .in b` and `small` width overrides changed to the new measured sizes, under `# text-dependent (0766)`.
- New: App/tests/test_0766_stay_range.py, App/tests/test_0766_phone_stays_browser.py.
- Screenshots: docs/tasks/screenshots-0766/before-stays-390.png, before-stay-390.png, after-stays-390.png, after-stay-390.png.

## Commands (last lines)
- `.venv/bin/python -m pytest tests/test_0766_stay_range.py -q --tb=short` → `6 passed in 0.25s`
- `.venv/bin/python -m pytest tests/test_0766_phone_stays_browser.py -q --tb=short -rs` → `3 passed in 6.72s`
- `.venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q --tb=short -rs -k "stays or stay"` → `24 passed, 58 deselected in 46.01s` (first run failed 2 width checks; fixed by the override change)
- `.venv/bin/python -m pytest tests/test_host_stay_actions_browser.py tests/test_host_stay_detail_layout_browser.py tests/test_invoice_stay_browser.py tests/test_stay_fee_pay_steps_browser.py tests/test_0766_phone_stays_browser.py -q --tb=short -rs` → `8 passed in 60.57s (0:01:00)`

## §7 checklist
- [x] Step 0 before screenshots. [x] Step 1 stay_range + vi + unit test. [x] Step 2 card. [x] Step 3 CSS. [x] Step 4 tests. [x] Step 5 after screenshots. [ ] Commit and PR (not done, by instruction).

## Deviations
- App/.venv did not exist. Created it, installed requirements.txt and requirements-dev.txt, and pip-installed playwright (not in the requirements files).
- Playwright's bundled Chromium was missing. Ran with `UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome` and `UBYHOST_REQUIRE_BROWSER=1`.
- The after-stays screenshot shows the app's "Add a second way in?" security prompt at the bottom. It comes from the test session, not the stays page.
- The other executor's files (dashboard.html, tests/_tmp_0765_shots_test.py, docs/tasks/screenshots-0765/) were not touched.

## Questions
None.

## Owner steps left
Review the diff, then commit on `claude/project-thread-19vzly` and open the PR. Merge only with `scripts/merge-pr-on-green.sh`.
