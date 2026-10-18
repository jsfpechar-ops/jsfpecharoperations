# 0123: Make cleaning calendar markers unmistakable

Status: done
Base: fb43944166869d7c2d226588b8a5eb5bb735f9a9 | Branch: feature/host-design0123-20261016 | PR #397
Report: docs/tasks/0123-cleaning-visibility-report.md

## 1. Objective

Make cleaning the clearest calendar event for cleaners: a full-width, solid, readable marker for its scheduled day that cannot collapse into an hour-width sliver.

## 2. Context

Owner screenshots showed faint dashed cleaning slivers. The marker communicates the scheduled cleaning day, not a literal duration bar. Actual property-hour windows remain available in details and are not stretched. Booking bars retain fractional check-in/checkout geometry. This follow-up supersedes only cleaning-marker presentation from the calendar/cleaning correction; property-hour authority, optional-code behavior, compact lists, permissions, and data remain in force.

## 3. Files

App/app/static/dashboard-calendar.js; App/app/static/dashboard-calendar.css; App/app/static/cleaning.css; App/app/templates/_dashboard_calendar.html; App/app/templates/cleaning.html; App/app/templates/cleaning_shared.html; App/app/templates/cleaning_settings.html; App/tests/test_cleaning_browser.py; App/tests/test_dashboard_calendar_browser.py; App/tests/test_dashboard_calendar.py; docs/tasks/0123-cleaning-visibility.md; docs/tasks/0123-cleaning-visibility-report.md; docs/tasks/0123-calendar-cleaning-fix-report.md; docs/HOST_APP_DESIGN.md; docs/context/status.md; docs/context/decisions.md; docs/context/known-issues.md.

## 4. Steps

1. Give each cleaning a full scheduled-day visual footprint in calendar and Gantt. Reserve lanes using that same footprint so separate jobs on one day do not overlay. Change layout only; preserve event data and actual timing.
2. In month/week views, put visible cleanings in the first event lane, with at most one visible cleaning and the existing booking budget below. Keep cleaning overflow separately identified and actionable. In typed Gantt, preserve booking-first rows, the distinct cleaning band, and the occupied-date drag target. Fit the compact week row and existing calendar-height limits.
3. Render a solid high-contrast warm-gold marker with localized Cleaning/Úklid text and a recognizable cleaning SVG/icon. Keep full-width marker geometry even for short or unknown-hour windows. At narrow widths, show a recognizable icon and truthful additional-cleaning count with a full accessible name; never make the marker claim a wider actual time window.
4. Keep cleaning-first overflow visible after booking overflow, unclipped, and connected to the existing day dialog. The dialog retains the real time window or unset warning, property name, and existing actions.
5. Preserve fractional booking endpoints, cleaning schedule dates and details, Auto/property filtering, read-only sharing, keyboard/focus behavior, mobile 44px targets, and existing creation/drag behavior. Keep shared-view assets and styles correct.
6. Add real-browser checks for full scheduled-day footprint, first-lane order, labels/contrast, same-day jobs, overflow, mobile activation, and actual-window data. Keep booking fraction and occupied-day drag checks. Capture host/shared, desktop, and mobile evidence.
7. Run all required CI jobs with zero calendar/browser skips and attach screenshots.

## 5. Do not touch

No backend/date/API/schema changes, TTLock/filing/privacy/sharing behavior, dependencies, public/auth/guest surfaces, main push, merge, or deployment.

## 6. Commands

Executor/CI only: run the required full suite, browser and geometry checks with zero skips and screenshot artifacts. The local managed environment is unavailable; do not bypass environment controls.

## 7. Acceptance

Cleaning appears as an unmistakable solid scheduled-day marker, including for short or unset windows. Actual cleaning timing and booking checkout fractions remain correct. Cleaning-first month/week lanes, the distinct Gantt cleaning band, truthful overflow, readable property details, and mobile targets remain usable. CI passes with zero skips and screenshots.

## 8. Stop and ask

Stop only for a genuinely unauthorized file, security concern, or data-scope conflict. Routine presentation and implementation choices are authorized.

## 9. Report

Record marker and lane behavior, unchanged timing semantics, exact tested application SHA/run/counts/artifacts, and whether PNGs were actually inspected in docs/tasks/0123-cleaning-visibility-report.md.
