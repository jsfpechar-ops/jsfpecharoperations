# 0123: Create stays and cleanings inside either calendar

Status: in-progress
Depends on: 0123-cleaning-visibility | Branch: feature/host-design0123-20261016 | PR #397
Report: docs/tasks/0123-calendar-create-popup-report.md

## 1. Objective

Date selection and explicit Add actions on Dashboard and Cleaning open one light in-page form with Stay/Cleaning choices; saving does not navigate away.

## 2. Context

Reuse the existing canonical Stay creation contract and Cleaning event save path. Cleaning keeps only property, date, and optional notes; Properties remains the sole hour editor. HTML fallback links and all existing permission, overlap, CSRF, and validation checks remain.

## 3. Files

App/app/templates/_dashboard_calendar.html; App/app/templates/dashboard.html; App/app/templates/cleaning.html; App/app/templates/_cleaning_screen.html; App/app/templates/cleaning_shared.html; App/app/static/dashboard-calendar.js; App/app/static/dashboard-calendar.css; App/app/static/cleaning.js; App/app/static/cleaning.css; App/app/routes/cleaning.py; App/app/routes/dashboard_calendar.py; App/app/cleaning.py; App/app/host_i18n.py; App/app/cleaning_i18n.py; App/tests/test_cleaning.py; App/tests/test_cleaning_browser.py; App/tests/test_dashboard_calendar.py; App/tests/test_dashboard_calendar_browser.py (rich-queue header action assertions only); docs/tasks/0123-calendar-create-popup.md; docs/tasks/0123-calendar-create-popup-report.md; docs/HOST_APP_DESIGN.md; docs/context/status.md; docs/context/decisions.md; docs/context/known-issues.md.

## 4. Steps

1. Add accessible type controls and preserve property/date selection when switching form types.
2. Anchor and clamp the light popup to the selected date; re-clamp after type changes and validation growth.
3. Keep Stay creation on the existing reservations JSON contract and return localized JSON validation/success for Cleaning creation.
4. Refresh Dashboard calendar and bounded server-rendered work regions after successful Stay creation; keep refresh retries separate from POST retries.
5. Add owner-safe cleaning markers to Dashboard without returning notes, instructions, codes, guest identity, or tokens.
6. Preserve shared read-only behavior, HTML fallback links, locale, existing date/filter state, and all save/permission safeguards.
7. Verify create flows, privacy, refresh/menu interactions, viewport geometry, localization, and no-navigation behavior with focused tests and CI. Approved follow-up: in `App/tests/test_host_quiet_dashboard_browser.py`, update only the rich-queue header action assertions around lines 320–333 to include the requested Add cleaning action and expect four controls; preserve all existing viewport, mobile, EN/CS, height, same-row, queue, and menu checks.

## 5. Do not touch

No filing/email/lock issuance rules, permissions, guest privacy, legacy timing precedence, schema, dependencies, main/merge/deploy, or Google integrations.

## 6. Commands

Executor/CI only: required full suite and browser/geometry jobs with zero skips and screenshot artifacts. Do not bypass the unavailable local environment.

## 7. Acceptance

Both host calendars provide Stay/Cleaning popup creation with in-place saves, localized validation, safe refresh behavior, and working explicit navigation links. Dashboard cleaning data contains only an explicit safe field whitelist. All required CI jobs pass with zero skips.

## 8. Stop and ask

Stop only for a genuine unscoped file, security, or data ambiguity. Routine implementation choices are authorized.

## 9. Report

Record the final implementation, privacy safeguards, exact tested SHA/run/counts/artifacts, and PNG inspection limitation in docs/tasks/0123-calendar-create-popup-report.md.
