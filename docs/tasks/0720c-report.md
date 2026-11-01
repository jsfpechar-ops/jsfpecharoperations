# 0720c report: groups B and C (executor, partial)

Status: blocked (25-call cap). Not pushed. Branch task/0720c-old-shell-tests.

## Commits
- step 3a: navigation prefetch test uses v2 `#app-sidebar` link
- step 3b: onboarding follow-up test uses v2 `#needs-action`; collapsed sidebar case on /settings
- step 3c: 0705 shell test: old-shell check on /settings, base.html key regex, v2 accent token value

## Per file
1. test_navigation_prefetch_browser.py: group B. Sidebar click now `#app-sidebar a[href="/reservations"]`. Pass: `1 passed in 2.98s`.
2. test_onboarding_followup_browser.py: group B and C. `.needs-you` to `#needs-action`. The collapsed-sidebar block (width 1440) now goes to /settings first, with a comment. Pass: `16 passed in 82.57s`.
3. test_0705_v2_shell_browser.py: group B. Non-v2 check now on /settings. The app2.css key is read from base.html with a regex, not the hard-coded 0705 key. The accent check is now `--acc:#d0452d`, because app2.css no longer has `--coral-600`; this is a value check, not a loosened one. Pass: `3 passed in 1.81s`.
4. test_dashboard_phone_browser.py: LEFT. Group A found (not changed). On `/` at 390 px the v2 dashboard renders a `.notification-stack` with a PIN bubble. `_host_alerts.html` is included at dashboard.html:77 with `alerts_expanded`, and 0717 keeps the stack for non-needs-you alerts. The 0241 test expects the PIN alert once, in "What needs you", and no stack. Owner or group A decides whether the PIN alert should be hidden from the stack on v2. Test left as it was.
5. test_host_quiet_dashboard_browser.py: LEFT, in progress. Fails at line 293, `[data-calendar]` count 0 on `/?lang=en`. `_dashboard_calendar.html` is only included when `cal_view` is set (dashboard.html:110). Line ~296 also uses `.needs-you-item`, which v2 names `.card.need`. Needs a decision: group B point-to-v2, or group A if the calendar should show on the default Overview. Not changed.
6. test_design_shell_browser.py: NOT STARTED.
7. test_door_code_window_browser.py: NOT STARTED.
8. test_host_wide_geometry_browser.py: NOT STARTED.

## Notes
- Test runs regenerate tracked PNGs under docs/tasks/0102-evidence. They were restored with `git checkout`; never commit them.
- Ruff and the design/context lint were not run (cap reached).

## Left to do
1. test_host_quiet_dashboard_browser.py: decide calendar and `.needs-you-item` (see 5), then the rest of the file.
2. test_design_shell_browser.py, test_door_code_window_browser.py, test_host_wide_geometry_browser.py (use `getComputedStyle(null)` as the selector hint).
3. test_dashboard_phone_browser.py: group A decision (see 4).
4. Ruff: `.venv/bin/python -m ruff check app tests tools --select E9,F63,F7,F82,F401,F841 | tail -3`.

## Group A findings
- Duplicate PIN alert on v2 phone dashboard (see 4).
- Possible missing calendar on v2 default Overview (see 5), pending decision.
