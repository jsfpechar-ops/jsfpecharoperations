# 0033 report

Status: review

## 1. Files changed

```
 docs/tasks/0033-posthog-public.md           |  73 +++++++
 App/app/analytics.py                        | rewritten
 App/app/config.py                          | PostHOG_* replaces UMAMI_*
 App/app/main.py                             | comments
 App/app/templating.py                       | analytics_tag
 App/app/templates/_posthog.html            | new
 App/app/static/analytics-optout.js          | new
 App/tests/test_umami_guard.py              | PostHog assertions
 (+ template include / data-analytics-event updates)
```

## 2. Commands

- `.venv/bin/python -m pytest tests/test_umami_guard.py tests/test_signup.py tests/test_no_tracking.py -q` → `106 passed`
- `.venv/bin/python -m pytest tests -q` → `2976 passed, 1 failed` before 0034 (`test_cookie_inventory` until inventory row renamed)

## 3. Acceptance

- [x] Umami tag replaced with cookieless PostHog on public pages; CSP from config.
- [x] Auth, guest, app pages stay on strict CSP without `posthog.init`.
- [x] Opt-out uses `ubyhost.analytics.disabled`.
- [x] Screenshots: `docs/tasks/0033-screenshots/` (`landing`, `privacy` at 360, 390, 1280 px) with test key set.

## 4. Deviations

- Full suite after 0033 alone: one failure in `test_cookie_inventory` until 0034 updates the inventory row (expected split across briefs).

## 5. Questions

None.

## 6. Owner steps left

None for this brief.
