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

## Session 2 (cap reached at 25 calls, not pushed)

Commits: 75f54e2 (step 3d, partial).

- 4. test_dashboard_phone_browser.py: unchanged. Duplicate PIN alert is fixed by 0721 (orchestrator decision).
- 5. test_host_quiet_dashboard_browser.py: PARTIAL, still failing. Changed to v2: calendar check is `.card.cal` (the v2 server-rendered grid); `.needs-you` to `#needs-action`; `.needs-you-item` to `.card.need`; `.needs-you-copy` to `.h`; `.needs-you-icon` to `.ic`; `.needs-you-list` to `.todo`; `.ui-btn` to `.btn`; `.ui-ph` to `.ov-top`; stray-row check now excludes `.ov-table` (today table). Remaining failure: `cardBorder` on `#needs-action` expects a 1 px solid frame at widths under 768. v2 has no frame on the lane. GROUP A: needs a decision. Tolerances unchanged.
- 6. test_design_shell_browser.py: 13 passed, 2 failed. `test_more_preserves_each_page_kind_and_sheet_links_work[/?lang=en-390]` and `[/?lang=en-820]`: `[data-sheet-open="more-sheet"]` is not on v2 `/` (v2 `.tabs` has a Menu link to /menu, no sheet). GROUP A/B decision: either the sheet is missing on v2, or the sheet part should point at /settings (old shell). Not changed.
- 7. test_door_code_window_browser.py: 8 chromium passed (`-k "not webkit"`). 6 webkit cases fail locally: WebKit binary not installed (`/opt/pw-browsers/webkit-2359`). Same as 0201; CI has WebKit. No change.
- 8. test_host_wide_geometry_browser.py: 3 passed, 7 failed. Failures are `getComputedStyle(null)` / null clicks on `main.wrap.with-sidebar`, `.notification-stack` and rail toggles, which v2 `/` does not render. These are group B/C rail cases (point at /settings). NOT STARTED in session 2 (cap). Not changed.

Ruff (App/app App/tests App/tools, E9,F63,F7,F82,F401,F841):
```
All checks passed!
```

Status: blocked. Left: file 5 lane frame (group A), file 6 more-sheet (decision), file 8 (apply B/C rail rule). Files 7 done locally except WebKit.
