# 0174 report

Status: blocked

## Files changed

None. Report only.

## Finding (stop condition, brief section 8 and 3)

- The calendar chip label is built in one place, but it is JavaScript, not Python: `labelFor(event)` in `App/app/static/dashboard-calendar.js` (around lines 196-205). The server only passes the raw `summary` as `label` (`App/app/routes/dashboard_calendar.py`, `events()`, line 97). `label` is also used by the detail dialog (`dashboard-calendar.js` line 556).
- The JS generic filter (line 200) only drops `reserved|booked|reservation` (and Czech equivalents). It does not drop `CLOSED - Not available`, `Blocked`, `Not available` or `Airbnb (Not available)`. That is the bug.
- The brief's step 2 (`chip_label(summary, property_name)` in Python, tested with pytest) does not match where the code lives. The IIFE in `dashboard-calendar.js` exports nothing, so a pytest test cannot call it without a node harness.

## Options for the owner or orchestrator to choose

1. JS fix: extend the regex in `labelFor` and add a node-based test (`node` is at `/opt/node22/bin/node`). Needs a test-harness decision.
2. Server fix: add a `chip_label` helper in `dashboard_calendar.py` and send it as a new JSON field (for example `chipLabel`). The JS chip uses that field. This changes the JSON contract.

Executor will not guess. Waiting for a brief update.

## Commands

None run. No tests run.

## Deviations

Done: steps 1 (locate builder) only. Left: steps 2 to 5.

## Questions

Which option (1 or 2) should the 0174 brief use?

## Owner steps left

None until the brief is updated.
