# 0270 report: wizard steps in story order

Status: review
Branch: claude/project-thread-4b2e7k (not pushed, no PR opened)

## Files changed
- App/app/property_setup.py (STEPS reordered, comment added)
- App/tests/wizard_walk.py (new helper, walk_to / current_step)
- App/tests/test_onboarding_wizard_survival.py (3 tests follow new order)
- App/tests/test_onboarding_wizard_browser.py (test-client tests only; Playwright not run)

## Commands (last lines)
1. `.venv/bin/python -m pytest tests/test_onboarding_wizard_survival.py -q --tb=short` : `24 passed, 1 warning in 4.14s`
2. `.venv/bin/python -m pytest tests/test_onboarding_wizard_browser.py -q --tb=short -rs -k "back_from_later or police_waiting_can_finish or done_count_includes or back_skips or try_it_open_skip or finished_applicable or waiting_hide_show or no_js_calendar_skip or guests_registered or legacy_unfinished or create_lands"` : `11 passed, 59 deselected, 1 warning in 3.65s`
3. Brief §6 first command (7 files) : `94 passed, 1 skipped, 1 warning in 10.78s`

## Acceptance (§7)
- [x] STEPS in new order
- [x] Both command lines pass
- [x] No test deleted

## Deviations
- Survival test (c): the replacement assertion `target == .../stay_fee` failed for the deferred-police cases, because the server skips stay_fee when it does not apply and redirects to the next applicable step. Changed to: if deferred, target is a wizard step other than police; else target is police. Fixed once.
- Browser test (b): `page = client.get(saved.headers["location"])` now lands on stay_fee, so it was changed to `client.get(f"{base}/done")` to keep the is-waiting check. Fixed once.
- Browser test (f): the brief's text did not name the `stay_fee` and `door_lock` skip lines in test (c); test (c) uses the brief's replacement as written, so the lock-dependent loop was removed from that test.
- Browser test (g): the 4 deleted lines were removed as written; the walk_to line replaced the calendar and guest_link posts.

## Questions
- The one skip in the §6 run is `tests/test_fee_setup_compatibility.py:381` ("Chromium is required for the fee editor browser check"). This file is not changed by this brief and the skip comes from the environment (no Chromium here). Not caused by 0270; CI should run it.
- Brief §6 lists the test file with the Playwright tests excluded; those are expected to fail until 0271 lands.

## Owner steps left
- None for this brief. Review the PR when opened by the owner (no PR opened by this session).
