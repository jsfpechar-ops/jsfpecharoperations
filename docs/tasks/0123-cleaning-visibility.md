# 0123: Make cleaning calendar markers unmistakable

Status: in-progress  
Base: fb43944166869d7c2d226588b8a5eb5bb735f9a9  
Branch: feature/host-design0123-20261016 | PR #397  
Report: docs/tasks/0123-cleaning-visibility-report.md  
Executor: Luna executor

## 1. Objective

Make cleaning the clearest calendar event for cleaners: a full-width, solid, readable day marker that cannot collapse into an hour-width sliver.

## 2. Context

Owner screenshot on application SHA 807e881 shows barely visible dashed cleaning slivers. The actual event/display window remains correct; a cleaning marker means “scheduled on this day,” not a literal duration bar. This changes only cleaning-marker presentation from the preceding 0123 calendar/cleaning work. Property hours, optional codes, compact list, permissions and booking checkout fractions remain authoritative.

## 3. Files

Production: `App/app/static/dashboard-calendar.js`; `App/app/static/dashboard-calendar.css`; `App/app/static/cleaning.css`; `App/app/templates/_dashboard_calendar.html`. Cache tags only if needed: `App/app/templates/cleaning.html`, `App/app/templates/cleaning_shared.html`, `App/app/templates/cleaning_settings.html`.

Tests: `App/tests/test_cleaning_browser.py`; `App/tests/test_dashboard_calendar_browser.py`.

Docs: this brief and `docs/tasks/0123-cleaning-visibility-report.md`; `docs/tasks/0123-calendar-cleaning-fix-report.md` (follow-up pointer only); `docs/HOST_APP_DESIGN.md`; `docs/context/status.md`; `docs/context/decisions.md`; `docs/context/known-issues.md`.

## 4. Steps

1. Render cleaning as a full-day visual marker in Calendar and Gantt. Preserve actual event times/data; only marker footprint and lane layout change. Keep fractional booking endpoints and date-only overlap logic unchanged. Short or unknown cleaning windows still receive the same prominent day marker. Cleaning layout footprints cover the scheduled date so two short cleaning windows on one day cannot share or overlay a lane; actual event timing remains separate.
2. In month/week Cleaning mode, put visible cleanings in the first event lane and bookings below as context. Keep one visible cleaning lane, truthful cleaning-specific overflow, and the existing booking budget. Gantt retains its distinct typed cleaning band and occupied-date drag hit testing. Keep desktop rows compact (28px cleaning, 22px booking, 18px summary) within current week/calendar bounds. Mobile cleaning targets remain at least 44px. Do not duplicate a day summary for a single visible cleaning; keep overflow summaries for hidden jobs.
3. Replace faint dashed styling with a solid high-contrast amber fill, dark text/border and a prominent localized Cleaning/Úklid label. Use a recognizable cleaning SVG when narrow cells cannot fit the full text; keep the accessible localized name and property. Full calendar markers use the day width minus small gutters. Keep a solid marker in the legend. No hover dependency or letter initials.
4. Keep cleaning overflow visible and identifiable after booking counts; it opens the existing day dialog. Actual time windows and unavailable-hour warnings remain in existing details.
5. Preserve Auto/property-count behavior, filters, segmented controls, read-only sharing, optional codes, keyboard access, draggable cleaning, and the occupied Oct 22 drag regression. Bump cache versions for changed assets.
6. Add focused real-browser checks in English and Czech at mobile and desktop widths for full-day markers with one-hour/missing-hour windows, localized desktop labels, solid contrast, first-lane ordering, multiple same-day cleanings, overflow, mobile hit targets, dialog access, Gantt, shared view and screenshots. Replace only the cleaning fractional-bar geometry expectation with the explicit day-marker contract; retain booking-fraction and actual cleaning-window assertions.
7. Run required CI. After all jobs pass, finalize the report and context docs.

## 5. Do not touch

No backend, date/API/schema, TTLock, filing, privacy, sharing behavior, dependencies, public/auth/guest surfaces, or compact Cleaning cards. No main push, merge, or deployment.

## 6. Commands

Use repository CI for the full suite and required browser/geometry jobs with zero skips and screenshots. The managed environment has no shell/browser; do not bypass that limitation.

## 7. Acceptance

Cleaning appears as an unmistakable solid amber day marker with localized labels; a one-hour or fallback window never creates a sliver. Booking checkout fractions and real cleaning time windows remain unchanged. Multiple cleanings/counts stay accessible, mobile targets remain at least 44px, the occupied-day drag test passes, and all required CI jobs pass with zero skips and screenshot artifacts.

## 8. Stop and ask

Pause only for a genuine unauthorized file, security, or data-scope conflict. Routine presentation and implementation choices are authorized.

## 9. Report

Write `docs/tasks/0123-cleaning-visibility-report.md` with changes, unchanged timing semantics, tested application SHA, CI run/counts, screenshot artifact links, and whether local pixel inspection was possible.
