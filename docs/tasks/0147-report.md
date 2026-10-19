# 0147 report (0147-cont-2)

Status: blocked

## Files changed
- App/app/static/dashboard-calendar.js (step 1: phone pointerup opens day, suppresses follow-up click)
- App/app/templates/_dashboard_calendar.html (script version 0147b to 0147c)

## Commands
- `node --check App/app/static/dashboard-calendar.js`: no output, exit 0.
- Step 2 browser run (`pytest tests/test_dashboard_phone_browser.py tests/test_dashboard_calendar_browser.py tests/test_host_quiet_dashboard_browser.py -q --tb=line -rs`): `1 failed, 13 passed in 82.76s`.
- Re-run of `tests/test_dashboard_phone_browser.py` alone: `1 failed, 1 warning in 2.59s`.

Failing assertion (verbatim, same both runs):
```
tests/test_dashboard_phone_browser.py:49: in test_phone_dashboard_compact
E   AssertionError: [data-cal-scales]
E   assert 0 >= 1
E    +  where 0 = visible_count(<Page url='http://127.0.0.1:35681/?lang=en&cal_date=2026-10-01&cal_view=auto&cal_scale=month'>, '[data-cal-scales]')
```
Line 49 is the 1280 (desktop) branch: `assert visible_count(page, selector) >= 1, selector` for HIDDEN_ON_PHONE.

## Analysis
- `dashboard-calendar.js:181` sets `[data-cal-scales]` hidden when `currentView === "gantt"`. The page opened at 1280 with `cal_view=auto` and `cal_scale=month`, so the scale segment is hidden and the test expects it visible.
- The change in step 1 only touches the `phoneDots()` branch, so this is not caused by it. Not verified against the pre-change commit.
- Fixing needs an owner decision (change the test expectation or the view behaviour). Not changed here: the brief forbids weakening tests.

## Deviations
Done: steps 1 to 1 (step 2 ran and failed twice). Left: step 2 (pass), step 3 (screenshots, evidence, ruff, report).

## Questions
1. Should `[data-cal-scales]` be visible in the gantt view at 1280, or should test line 49 skip it for gantt?

## Owner steps left
- Decide the question above, then re-run 0147-cont-2 steps 2 and 3.
