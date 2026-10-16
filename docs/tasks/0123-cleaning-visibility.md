# 0123: Make cleaning calendar markers unmistakable

Status: in-progress
Base: fb43944166869d7c2d226588b8a5eb5bb735f9a9 | Branch: feature/host-design0123-20261016 | PR #397
Report: docs/tasks/0123-cleaning-visibility-report.md

## 1. Objective

Make cleaning the clearest calendar event for cleaners: a full-width, solid, readable day marker that cannot collapse into an hour-width sliver.

## 2. Context

Owner screenshots show faint dashed cleaning slivers. Existing cleaning event timing and booking checkout fractions remain authoritative. A cleaning calendar marker represents its scheduled day, while its actual window stays available in details. This follow-up changes only cleaning marker presentation and remains within the approved host workspace.

## 3. Files

App/app/static/dashboard-calendar.js; App/app/static/dashboard-calendar.css; App/app/static/cleaning.css; App/app/templates/_dashboard_calendar.html; App/app/templates/cleaning.html; App/app/templates/cleaning_shared.html; App/app/templates/cleaning_settings.html; App/tests/test_cleaning_browser.py; App/tests/test_dashboard_calendar_browser.py; App/tests/test_dashboard_calendar.py; docs/tasks/0123-cleaning-visibility.md; docs/tasks/0123-cleaning-visibility-report.md; docs/tasks/0123-calendar-cleaning-fix-report.md; docs/HOST_APP_DESIGN.md; docs/context/status.md; docs/context/decisions.md; docs/context/known-issues.md.

## 4. Steps

1. Give cleaning calendar and Gantt markers a full scheduled-day footprint; reserve matching layout lanes without changing booking fractions or event data.
2. Put cleaning first in calendar event rows, preserve typed booking-first Gantt drag behavior, and keep overflow labels truthful and accessible.
3. Use a solid high-contrast gold marker with a localized Cleaning label and recognizable icon/count at narrow widths.
4. Keep day-dialog cleaning/property labels visible and usable; preserve existing actual timing details, Auto/filter behavior, read-only sharing, and mobile target sizes.
5. Add browser and API coverage for marker geometry, localized labels, full day footprint, actual window data, privacy, and missing-hour fallback.
6. Run the required full and Chromium CI suites with zero skips and screenshots.

## 5. Do not touch

No backend/date/API/schema changes, TTLock/filing/privacy/sharing behavior, dependencies, public/auth/guest surfaces, or main/merge/deploy actions.

## 6. Commands

Executor/CI only: required full suite and browser/geometry jobs with zero skips and screenshot artifacts. Do not bypass the unavailable local environment.

## 7. Acceptance

Cleaning is clearly visible as a solid full-day marker, including for short or unset windows. Booking checkout fractions and actual cleaning-window data remain unchanged. Multiple cleaning events and overflow remain accessible; mobile targets stay at least 44px.

## 8. Stop and ask

Stop only for a real unauthorized file, security, or data-scope conflict. Routine implementation and design choices are authorized.

## 9. Report

Record changed behavior, unchanged timing semantics, exact tested application SHA/run/counts/artifacts, and whether PNG pixels were actually inspectable in docs/tasks/0123-cleaning-visibility-report.md.
