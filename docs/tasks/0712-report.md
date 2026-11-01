# 0712 report

Status: blocked

## Commits
- 5385734 0712 step 1: JS and template restored to origin/main (`git diff origin/main` on both files is empty)
- b69afc2 0712 step 2: calendar.days14 keys removed (en, cs, vi); test_0521_overview_14_days_browser.py deleted
- 379ba57 0712: CI fixes for the v2 Overview (coordinator request)

## Tests
- test_dashboard_calendar.py + test_dashboard_calendar_browser.py: 13 failed, 35 passed (534 s). Failure: `Locator.get_attribute` timeout waiting for `[data-cal-body]`. Failing test names not captured; not investigated further (brief: fix once, then stop).
- test_dashboard_queue_copy.py: 3 failed, 11 passed. Same 3 fail on HEAD before the CI-fix commit (pre-existing, Overview copy: "All guests reported", "Reported").
- test_welcome_back_0275.py, test_legal_contents.py, test_public_copy_i18n.py: pass.
- ruff on test_welcome_back_0275.py: 6 errors remain after removing `import re` (other errors, e.g. redefinition of `host`); not fixed.
- Brief §6 names no i18n parity file; none found by name. Parity-related tests in the run above passed.
- context_lint: not run.

## Deviations
- CI fix: removing the two `dashboard.section.current` assertions left an empty function `test_current_dashboard_heading_is_available_in_both_languages`; the function was removed too.
- CI fix: `tests/test_dashboard_queue_copy.py` line ~307 still calls `host_i18n.translate("en", "dashboard.section.current")`; it does not fail on the removed key, so it was left.
- Done: steps 1 to 2 and the CI fixes. Left: calendar browser failures (13) need investigation; report step 3 written here, not pushed.

## Owner steps left
- Investigate the 13 `[data-cal-body]` failures in test_dashboard_calendar_browser.py.
- Decide on the 6 remaining ruff errors in test_welcome_back_0275.py.
- Bump static versions after merge (brief 0711).
