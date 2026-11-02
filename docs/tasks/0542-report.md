# 0542 report (executor, section 10 addendum)

Status: review

## Files changed (step 5)
- App/app/static/app2.css: one rule `body.v2 .cleaning-page [data-cal-scale]{min-width:44px;min-height:44px}` (tap target, 0542 cleaning 390).
- App/app/templates/base.html: app2.css key 20261101-0542 to 20261101-0542b.
- App/tests/static_versions.json: rewritten with --write.
- App/tests/test_cleaning_browser.py: nav selector `.sidebar-nav a[href="/cleaning"] svg` to `a.nav[href="/cleaning"] svg`; CRUD link name `Add cleaning` to `+ Add cleaning`.

## Failures
- Caused by 0542, fixed: test_cleaning_browser geometry (8 cases, nav selector), test_host_crud_and_drag (link name), design guard tap-target on /cleaning at 390 (Year button 40 px).
- Pre-existing (also fail at 9e9f491): 13 tests in test_dashboard_calendar_browser.py (timeout on [data-cal-body]); test_host_language.py::test_the_setup_steps_a_new_czech_host_reads_are_czech; test_0252_touch_sweep_browser.py::test_every_host_page_on_phone_ipad_and_desktop (phone390 /, ipad1024 /); test_design_guardrails_browser.py::test_every_host_page_passes_the_layout_guard (dashboard menu-off-screen).
- Not caused by 0542 and not fixed: the 16 above. Owner decision needed.

## Commands (last 5 lines)
- Fast set (test_0540, 0541, cleaning, design_cleaning, host_language, static_versions, no_em_dashes): 1 failed, 62 passed (the czech test, pre-existing).
- Browser set (test_cleaning_browser, design_guardrails, 0252 touch sweep, dashboard_calendar, host_language): 16 failed, 99 passed; all 16 pre-existing as listed above. 0 skipped.
- design_lint: `design lint: OK`
- context_lint: `context lint: OK`

## Deviations
- Pre-0542 check ran on worktree of 9e9f491 (removed after).
- Not pushed, no PR (outer instruction: do not push).

## Owner steps left
- Decide on the 16 pre-existing browser failures (dashboard calendar, host language, dashboard layout guard, 0252 touch sweep).
