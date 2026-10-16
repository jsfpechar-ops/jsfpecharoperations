# 0123: Create stays and cleanings inside either calendar

Status: done
Depends on: 0123-cleaning-visibility | Branch: feature/host-design0123-20261016 | PR #397
Report: docs/tasks/0123-calendar-create-popup-report.md

## 1. Objective

Dragging or selecting a date on Dashboard or Cleaning opens one light in-page popup with Stay/Cleaning choices. Saving creates the record without navigating away. Both host pages have explicit Add stay and Add cleaning actions.

## 2. Context

Dashboard already had a Stay dialog and the canonical reservations JSON create contract; Cleaning creation redirected to /cleaning/new. Reuse those existing paths. A Stay keeps its property, arrival/departure, guest count, optional safe manual label/email, and overlap consent. A Cleaning has one property, one scheduled day, optional notes, and no duplicate hour or door-code fields. Properties remains the sole property-hour editor. Preserve normal HTML fallback links/forms when JavaScript is unavailable.

## 3. Files

App/app/templates/_dashboard_calendar.html; App/app/templates/dashboard.html; App/app/templates/cleaning.html; App/app/templates/_cleaning_screen.html; App/app/templates/cleaning_shared.html (read-only/asset behavior only); App/app/static/dashboard-calendar.js; App/app/static/dashboard-calendar.css; App/app/static/cleaning.js; App/app/static/cleaning.css; App/app/routes/cleaning.py; App/app/routes/dashboard_calendar.py; App/app/cleaning.py; App/app/host_i18n.py; App/app/cleaning_i18n.py; App/tests/test_cleaning.py; App/tests/test_cleaning_browser.py; App/tests/test_dashboard_calendar.py; App/tests/test_dashboard_calendar_browser.py; App/tests/test_host_quiet_dashboard_browser.py (only rich-queue header action assertions around lines 320–333); docs/tasks/0123-calendar-create-popup.md; docs/tasks/0123-calendar-create-popup-report.md; docs/tasks/0123-calendar-refresh-controls.md; docs/tasks/0123-calendar-refresh-controls-report.md; docs/tasks/0123-cleaning-visibility.md; docs/tasks/0123-cleaning-visibility-report.md; docs/HOST_APP_DESIGN.md; docs/context/status.md; docs/context/decisions.md; docs/context/known-issues.md.

## 4. Steps

1. Extend the shared native create dialog with accessible Stay/Cleaning type choices. Default to Stay on Dashboard and Cleaning on Cleaning. Explicit Add buttons choose the corresponding type. Switching types retains property and selected dates, toggles the relevant fields and required state, and never creates multiple cleaning jobs from a dragged range. Switching back to Stay retains its date range.
2. Anchor the light popup to the selected cell or drag endpoint. Clamp it within viewport edges, recalculate position after type changes and validation growth, and clear desktop coordinates on mobile. Preserve dialog focus, Escape, focus return, close behavior, save-in-flight protection, 44px mobile controls, and EN/CS copy.
3. Keep Stay creation on the canonical reservations JSON endpoint and preserve its validation, overlap consent, CSRF, permissions, and date semantics. Make the existing Cleaning save route return localized JSON success with created id/url and localized 422 errors only when JSON is requested; normal HTML success and error fallbacks remain unchanged.
4. After a successful create, refresh the relevant calendar in place, retain the selected property/date where possible, and show localized success/errors. Keep post-save refresh separate from record creation: refresh failure offers a retry that performs GETs only and never invites another create POST. Do not navigate automatically; provide explicit Open/View links.
5. Refresh the Dashboard's bounded server-rendered work region after a Stay create without replacing calendar, filters, header, or dialogs. Use same-origin HTML and replace only the tagged escaped server regions. If refresh fails after commit, report the saved record and offer refresh-only retry rather than showing a failed save or risking a duplicate.
6. Include owner-authorized Cleaning markers in Dashboard data. Add an optional private-data-free schedule path and serialize only the explicit safe whitelist: id/type, property, date, display window, checkout/arrival context, warnings, and URL. Never serialize codes, notes/instructions, guest identity, or tokens. Preserve owner/property/archived/demo/date bounds and no-store behavior. No live lock calls.
7. Let both calendars render mixed events by kind. Stay overlap checks ignore Cleaning events. Dashboard cleaning details remain basic and provide explicit View cleaning navigation; private details/codes remain on the Cleaning page. Read-only shared calendars cannot create. Keep filters, Auto/manual preferences, HTML fallbacks, locale, and all existing forms/actions.
8. Preserve the creation controls after Dashboard HTML replacement. Dispatch one scoped content-updated event; existing idempotent app.js initializers bind imported copy, menu, row, confirmation, and banner nodes without replaying global handlers. Refresh retries remain GET-only.
9. Verify both-page drag/click/keyboard selection and explicit buttons, type switching, exact one-record saves, validation/CSRF/permissions, same-page state, visible refresh, dashboard whitelist privacy, refreshed menu/copy/confirmation/navigation, mobile/desktop viewport clamping, EN/CS, read-only behavior, no-JS fallbacks, fractional bookings, cleaning markers, occupied-date drag, zero browser skips, and screenshot capture.
10. Approved narrow follow-up: in App/tests/test_host_quiet_dashboard_browser.py, change only the rich-queue header action assertions around lines 320–333 to assert the Add cleaning link and four controls. Preserve all existing viewport, mobile, EN/CS, button height/alignment, same-row, queue, and menu assertions.

## 5. Do not touch

No filing/email behavior, TTLock issuance, permissions, guest privacy, legacy time precedence, schema, dependencies, public/auth/guest forms, main, merge, or deploy. Do not add Google integrations.

## 6. Commands

Executor/CI only. Run full required tests, browser and geometry suites with zero skips and screenshot artifacts. The managed local environment is unavailable; do not bypass its controls.

## 7. Acceptance

Both host calendars open an in-page Stay/Cleaning popup, preserve existing creation safeguards, and save in place. Dashboard receives only whitelisted Cleaning data. Refresh updates are safe and imported host actions work without duplicate bindings. All eight CI jobs pass with zero calendar/browser skips.

## 8. Stop and ask

Stop only for a genuinely unscoped file, security issue, or data-ownership ambiguity. The scoped implementation and test follow-up are authorized.

## 9. Report

Write docs/tasks/0123-calendar-create-popup-report.md with the actual behavior, privacy safeguards, tested code/test SHA and CI evidence, screenshot links, and PNG inspection limitation. The tested application SHA is the Render hand-off. Any later report/context commit is docs-only; do not merge or deploy.
