# 0174: calendar chips never say CLOSED or other status words

Status: todo
Depends on: none | Branch: claude/project-thread-5hw8cf
Executor: Haiku 5.5 | Fits one session

## 1. Objective

The owner's production dashboard calendar shows chips like `CLOSED - Not available · Vivus Apartment with Balcony & Garage · 2`. These words come from the calendar feed's SUMMARY (Booking.com says "CLOSED - Not available" for real bookings and manual closures alike, Airbnb says "Reserved" or "Airbnb (Not available)"). Owner decision: every such chip means "occupied", so the chip shows only the property name (plus the guest count suffix it already has), never the feed's status words.

## 2. Context

The chip label is built in JavaScript: `labelFor(event)` in `App/app/static/dashboard-calendar.js` (about lines 196-205). Its `generic` regex only drops reserved, booked, reservation, rezervováno and rezervace. The detail dialog also reads `event.label` (about line 556): leave the dialog as it is. The existing browser test `App/tests/test_dashboard_calendar_browser.py` already seeds stays with `summary="Reserved"` / `"! Reserved"` (line 33) and asserts none shows as text (line 125).

## 3. Files

`App/app/static/dashboard-calendar.js`, `App/tests/test_dashboard_calendar_browser.py`, `App/app/templates/*.html` that reference `dashboard-calendar.js?v=` (new key), `App/tests/static_versions.json`, `docs/tasks/0174-*`.

## 4. Steps

1. In `labelFor`, extend the `generic` regex to also match, case-insensitively, optionally preceded by `!` or `⚠` and spaces: `closed - not available`, `closed – not available`, `closed`, `not available`, `blocked`, `airbnb (not available)`, `unavailable`, plus the existing words. Keep everything else.
2. In `test_dashboard_calendar_browser.py` extend the seeding near line 33 so that some stays use `summary="CLOSED - Not available"`, `"Airbnb (Not available)"` and `"Blocked"` (keep the existing ones), and extend the assertion near line 125 so none of `CLOSED`, `Not available`, `Blocked` appears in `.cal-week-events` or the month chips. Read the surrounding test first; change only what the new words need.
3. Bump the `dashboard-calendar.js` key: `grep -rn "dashboard-calendar.js?v=" App/app/templates | cut -c1-150`, give every reference the same new key ending `-0174`, then from `App/`: `.venv/bin/python tests/test_static_versions.py --write && .venv/bin/python -m pytest tests/test_static_versions.py -q 2>&1 | tail -3`.
4. From `App/` run (foreground, timeout 600000, `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium`): `.venv/bin/python -m pytest tests/test_dashboard_calendar_browser.py -q -rs 2>&1 | tail -6`. Then from the repo root `git checkout -- docs/tasks/0102-evidence && git clean -fdq docs/tasks/0102-evidence` (skip if refused). Expected: all passed, 0 skipped.
5. Commit: `git add App/app App/tests docs/tasks/0174-* && git commit` with message "0174: calendar chips show the property, not feed status words" and the two trailers given by the orchestrator.

## 5. Do not touch

Sync, stored summaries, templates other than what the label needs; hard rules 1, 3, 8.

## 6. Commands

As in each step.

## 7. Acceptance

- [ ] No chip label contains CLOSED, Reserved, Not available or Blocked; new tests pass.

## 8. Stop and ask

The chip label is built in more than one place and the fix would need a design decision.

## 9. Report

`docs/tasks/0174-report.md`, short; `Status: review`.
