# 0368 report

Status: blocked

Deviations: Done: steps 1 to 5. Left: step 6 (§6 does not pass, §7 not met). Stopped under §8: the tablet test fails on the base commit too.

## Files changed
- App/tests/test_pwa_browser.py
- App/tests/test_0201_tabbar_safe_area_browser.py
- App/tests/test_dashboard_rows_browser.py
- App/tests/test_stay_fee_pay_steps_browser.py
- App/tests/test_0251_tablet_browser.py
- docs/tasks/0368-report.md

## Commands (last lines)
1. §6 pytest, 5 files, `-rs`: `1 failed, 19 passed in 46.03s`, 0 skipped. Failure: `test_0251_tablet_browser.py:128` (`_wait_sidebar(page, False)`), `Page.wait_for_function: Timeout 5000ms exceeded`.
2. `ls /tmp/0368-shots | tail -5`: `0201-tabbar`, `0251-menu-open-1180.png`, `0251-overview-1180.png`, `pwa-0203`.
3. Base-commit 0251 test run alone (temp copy, removed): `E AssertionError: 1180` / `assert 240 < 100`, `1 failed`.
4. `grep -rn "/mnt/project-files" App/tests --include=*.py | tail -5`: 2 lines remain, both outside the brief's file list (see Questions).

## §7 Acceptance
- [ ] §6 passes, 0 skipped. Screenshots land under /tmp/0368-shots: yes.
- [ ] No /mnt/project-files left in App/tests/*.py: 2 files remain.
- [x] No assertion changed.

## Questions
1. The brief assumes the 0251 failure is a timing race. It is not: the unchanged test fails locally at the same point (`240 < 100`, width 1180) after a 5 s wait. The second toggle tap does not collapse `#app-sidebar` below 100 px. This is an app behaviour question (App/app/ is out of scope), or the test expectation is wrong. Owner decision needed.
2. Two files still hard-code `/mnt/project-files`: `App/tests/test_0199_phone_geometry_browser.py:9` and `App/tests/test_push_settings_browser.py:26`. The brief says no other file may change. Include them or leave them for a new brief?

## Owner steps left
None until question 1 is decided. Not pushed, merged or PR opened.
