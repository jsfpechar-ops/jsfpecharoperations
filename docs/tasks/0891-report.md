# 0891 report

Status: blocked

## Files changed
Patch script (sha256 d553970d...c14d, hash matched) applied all 7 files: App/app/host_i18n.py, App/app/host_vi_i18n.py, App/app/templates/_dashboard_calendar.html, App/app/static/dashboard-calendar.js, App/app/static/dashboard-calendar.css, App/tests/test_dashboard_calendar_browser.py, App/tests/test_cleaning_browser.py. Nothing staged or committed.
Also written: docs/tasks/screenshots-0891/ (calendar-390/768/1280 only), and the test run rewrote docs/tasks/screenshots-0814/*.png (17 files changed in git status, outside the brief's list).

## Steps
- Step 1: hash matched.
- Step 2: 7 lines, all `ok` (host_i18n 2, host_vi_i18n 1, template 3, js 14, css 3, calendar test 3, cleaning test 2).
- Step 3: SYNTAX-OK.
- Step 4 (focused -k run): 1 failed, 2 passed, stopped at -x on test_host_i18n.py::test_language_endpoint_sets_cookie_and_rejects_open_redirects. Last lines: `sqlite3.OperationalError: no such table: apartment`.
- Step 5, section 6 command 1 (host_i18n + dashboard_calendar + dashboard_phone): 4 failed, 45 passed, 1 warning, 81 s.
  - test_host_i18n.py::test_language_endpoint_sets_cookie_and_rejects_open_redirects: no such table: apartment
  - test_host_i18n.py::test_a_signed_in_dashboard_keeps_vietnamese: no such table: user_account
  - test_host_i18n.py::test_language_endpoint_accepts_vietnamese: no such table: apartment
  - test_dashboard_calendar_browser.py::test_0891_sticky_head_title_follows_scroll_and_back_to_top (line 1056): `page.wait_for_function("scrollY > 1000")` raises `EvalError: Evaluating a string as JavaScript violates ... 'unsafe-eval' is not an allowed source`. The brief's test passes a string to wait_for_function, which the page CSP blocks. This is a test-authoring defect, not a layout result.
- Flake check (rerun of those 4 tests once): 4 failed in 2.8 s, same errors.
- Section 6 command 2 (cleaning, geometry, touch sweep): not run, because the brief says to stop after a test fails twice.

## Section 7 acceptance
- [x] Step 1 hash, step 2 seven ok lines, step 3 SYNTAX-OK.
- [ ] Both section 6 commands pass with 0 skipped (command 1 failed 4; command 2 not run).
- [ ] 6 shots: only calendar-390, calendar-768 and calendar-1280 exist. The cleaning-* shots were not produced. Not viewed, so no look-check was done.
- [x] Only the 7 section 3 files plus the screenshot dirs changed, nothing staged.

## Deviations
Done: steps 1 to 3 fully, step 4 and step 5 part 1 run (failed). Left: step 5 part 2 (cleaning, geometry, touch sweep), step 6 (look at shots), step 7 finished here.
Status set to blocked in the brief. No PR, no commit.

## Questions / for the orchestrator
1. test_0891_sticky_head_title_follows_scroll_and_back_to_top: the wait_for_function call takes a string, which the CSP blocks. Pass a callable instead, or poll with page.evaluate("window.scrollY") in a loop. Brief says not to fix tests, so I did not.
2. test_host_i18n: "no such table: apartment / user_account" in three tests. The DB is not initialised in these tests when run with this file set. I could not tell whether this is new or pre-existing, because checking the base needs a clean checkout, which I did not do. The patch only adds i18n keys in host_i18n.py and host_vi_i18n.py, so it is unlikely to be the cause, but this is unverified.

## Owner steps left
None. The orchestrator must fix items 1 and 2 above, then rerun section 6 and bump ?v=, per brief section 9.
