# 0210 report

Status: blocked

## Files changed
- App/app/templates/setup_wizard/property.html (step 1)
- App/app/routes/admin.py (refuse blank time on wizard step 1)
- App/app/templates/setup_wizard/door_lock.html (editable times when a lock is connected)
- App/app/templates/_property_editor.html (missing-times warning)
- App/app/host_i18n.py, App/app/host_vi_i18n.py (strings)
- App/tests/test_times_required_0210.py (new)

## Commands
- `.venv/bin/python -m pytest tests/test_times_required_0210.py tests/test_onboarding_wizard_survival.py tests/test_smart_locks_page.py tests/test_door_code_one_lock_one_property.py -q` : 50 passed
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py tests/test_lock_navigation_browser.py -q -rs` : 73 passed, 0 skipped. No browser test edits were needed.

## Steps
Done: steps 1 to 6 (commits 0210 step 1 to step 6). Step 7 is the step 6 commit plus this report.
Left: design_lint (brief §6.3), 390 px screenshot (§6.4), and §7 check for the lock step rendering with a connected lock.

## Deviations
- Done: steps 1 to 6. Left: design lint and screenshot. Budget reached.
- Test 3 (GET property step shows `required`) was dropped. The step GET redirects to calendar for this fixture (303). The `required` check is now in the 400 re-render of test 1.
- Commit trailers use Claude Opus 5.5 per the prompt, not the brief's default.
- Another commit (cd70f83, "0209: step 0 CI pin") landed on this branch after step 6. Not mine, not touched.
- Tracked PNG files under docs/tasks/0102-evidence show as modified. Not committed.

## Questions
- Confirm the redirect behaviour of GET /setup/property for an apartment that is past that step is intended, or whether the lock step check needs a fresh-apartment fixture.

## Owner steps left
- None before review. Run design_lint and the screenshot in a new session.
