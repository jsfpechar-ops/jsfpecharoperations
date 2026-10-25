# 0391 report: the wizard's lock step can add a second lock

Status: review

## Files changed

- App/app/templates/_smart_lock_share.html (new): the TTLock sharing steps macro, used by the Door lock tab and the wizard.
- App/app/templates/_smart_locks_panel.html: imports the macro.
- App/app/templates/setup_wizard/door_lock.html: no-free-lock branch (why + taken locks + sharing steps, Check connection primary), "Add another lock" fold-out, taken locks disabled with "in use by", refused saves keep times and switch.
- App/app/routes/admin.py: `free_lock_count`; lock-step refusals (taken lock, bad or missing hours) stay on the lock step instead of jumping to step 1.
- App/app/host_i18n.py, App/app/host_vi_i18n.py: `wizard.door_lock.all_taken` (en, cs, vi).
- App/tests/test_wizard_second_lock_0391.py (new, 5 tests); App/tests/test_onboarding_wizard_survival.py: one assertion follows the stay-on-lock-step behaviour.

## Commands

- 0391 + lock/door/ttlock/survival tests: 201 + 56 passed.
- Browser (chromium, `UBYHOST_REQUIRE_BROWSER=1`): test_lock_navigation, test_onboarding_wizard, test_door_code_window, test_property_navigation: 93 passed, 0 skipped. WebKit variants deselected here (no WebKit binary in this container); CI runs them.
- No horizontal overflow at 390 or 1280, EN and CS.

## Screenshots

`screenshots-0391/`: before (`before-wizard-*`), after with no free lock (`after-1-*`), after the new lock is shared (`after-2-*`), EN and CS at 390 and 1280.

## Deviations

Executor hit the tool cap after step 6; a second session did step 7. The survival test change (step 8) was a reviewer decision.

## Owner steps

Review and merge the PR; deploy. No CSS or JS changed, so no `?v=` bump.
