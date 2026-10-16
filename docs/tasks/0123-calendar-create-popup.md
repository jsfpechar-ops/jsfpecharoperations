# 0123: Create stays and cleanings inside either calendar

Status: in-progress  
Depends on: 0123-cleaning-visibility  
Base: d15abfa0879fc4ba412a53f11827f878f12fc35b  
Branch: feature/host-design0123-20261016 | PR #397  
Report: docs/tasks/0123-calendar-create-popup-report.md  
Executor: Luna executor

## 1. Objective

Add Google Calendar-style, light-mode in-page creation popups to Dashboard and Cleaning calendars. A selected date or explicit add action opens a Stay/Cleaning choice and saves without navigating away.

## 2. Context

Owner approved this follow-up after the prominent cleaning-marker work. Dashboard already has an in-page stay dialog and the existing reservations JSON creation contract. Cleaning currently redirects its create action to /cleaning/new. Reuse the stay contract and validations, and the existing cleaning form/save_event validation. Properties remains the only place for check-in/check-out defaults. Keep the existing HTML fallback links and all permissions, CSRF, overlap and conflict rules. Dashboard cleaning markers must use only the existing safe calendar fields; never expose codes, notes, guest identities or tokens.

## 3. Files

Only edit as needed: App/app/templates/_dashboard_calendar.html; App/app/templates/dashboard.html; App/app/templates/cleaning.html; App/app/templates/_cleaning_screen.html; App/app/templates/cleaning_shared.html (read-only/asset markup only); App/app/static/dashboard-calendar.js; App/app/static/dashboard-calendar.css; App/app/static/cleaning.js; App/app/static/cleaning.css; App/app/routes/cleaning.py; App/app/routes/dashboard_calendar.py; App/app/cleaning.py; App/app/host_i18n.py; App/app/cleaning_i18n.py; App/tests/test_cleaning.py; App/tests/test_cleaning_browser.py; App/tests/test_dashboard_calendar.py; App/tests/test_dashboard_calendar_browser.py; docs/tasks/0123-calendar-create-popup.md; docs/tasks/0123-calendar-create-popup-report.md; docs/tasks/0123-cleaning-visibility-report.md; docs/HOST_APP_DESIGN.md; docs/context/status.md; docs/context/decisions.md; docs/context/known-issues.md. Read App/app/static/host.js only if needed to inspect existing refresh hooks; do not edit it without root review. No other files without root review.

## 4. Steps

1. Extend the shared native create dialog with labelled Stay/Cleaning type controls. Dashboard defaults to Stay; Cleaning defaults to Cleaning. Explicit Add stay and Add cleaning actions appear on both host pages. Switching type retains property/date selections and enables only relevant fields. A Cleaning create is exactly one scheduled day, even when the user dragged a date range; it has property, date and optional notes, without hours or door-code fields. Stay keeps property, arrival/departure, guest count, optional label/email and existing overlap consent. Translate new copy in English and Czech.
2. Position the desktop white popup by the selected date, drag endpoint or add action, and clamp it to the viewport. Preserve native dialog keyboard/focus handling, Escape, focus return, outside-close, and protection from accidental duplicate/close while saving. On mobile use a viewport-contained sheet with scrolling and 44px targets. Keep selected date/property on type changes and retain the existing HTML form links when JavaScript is off.
3. Keep Stay creation on the existing /reservations JSON POST and its filing, date, email and overlap guards. Remove Cleaning's redirect path. For Cleaning, enhance the existing POST to return 201 JSON with the created id/url when JSON is requested and localized 422 field errors; preserve normal HTML 303 success and 422 editor fallback. Reuse owner/property checks, CSRF and cleaning.save_event; do not add a new write endpoint or time/code controls.
4. After a successful save, refresh calendar and Cleaning list in place, preserve the chosen property/date, and show localized success/errors. Do not navigate or reload. Dashboard stay creation refreshes bounded server-rendered summary/list regions in the background from same-origin HTML using DOMParser; replace only tagged, escaped regions, never calendar, filters, dialogs or scripts. Existing row actions continue working. If background refresh fails after a committed save, report success and provide a safe refresh affordance; do not invite duplicate submission. Entries outside the visible period use the existing view/date workflow without forced navigation.
5. Add Cleaning events to Dashboard from the canonical cleaning schedule with an opt-in include_private=False path. That path must skip code reads and notes/instruction decryption; whitelist only safe id/kind/property/date/display-window/checkout/arrival/warning/url fields. Preserve owner authorization, archived/demo/date bounds and no-store behavior. Use cleaning-prefixed ids distinct from reservation ids. Dashboard cleaning links go to the existing Cleaning page/date/property anchor; details expose no private cleaner or guest data. Filter cleaning events out of Stay overlap calculations. Preserve the visibility marker style and Cleaning-first calendar lane/booking overflow behavior. Shared readonly calendars cannot create.
6. Keep Cleaning drag only where its existing save handler works. Do not make Dashboard cleaners draggable without an authorized persistence handler. Add Cleaning creation on Dashboard as well as Cleaning, and keep Stay links working when JavaScript is disabled or opened in a new tab.
7. Add meaningful browser/API regressions for both pages: date drag/click/keyboard and explicit actions open the right type; type switches preserve selections and required fields; exactly one correctly owned stay or cleaning is saved; popup save retains the page/calendar and refreshes entries; 422/409/CSRF/foreign/archived failures do not write and retain form input; optional notes and unset times work; no duplicate time/code entry; mobile/desktop, EN/CS, viewport-edge placement, focus, readonly and no-JS paths. Assert Dashboard calendar responses exclude private fields/codes and IDs remain type-safe. Preserve occupied-day Oct 22 drag and booking-fraction/cleaning-marker checks.
8. Bump changed asset cache keys. Run the complete required CI and Chromium browser/geometry jobs with zero skips and screenshots. Keep all existing security, permission, overlap, and privacy assertions.

## 5. Do not touch

No filing/email rules, lock issuance or live lock calls, sharing permissions/policies, guest privacy, legacy time precedence, schema/migrations, dependencies, guest/public/auth surfaces, main, merge or deployment. Do not add integrations with Google.

## 6. Commands

Use repository CI for application/browser checks because the managed execution environment is unavailable. Run the required full suite, browser and geometry jobs with zero skips and screenshot artifacts. Do not bypass environment enforcement or reduce gates.

## 7. Acceptance

Both host calendars have light, viewport-contained Stay/Cleaning creation popups and explicit add buttons. Saves remain in-page, persist one correct record, refresh real calendar/list data and preserve existing validation. Dashboard cleaning markers are prominent and use safe calendar-only data. Property hours remain the sole defaults; shared calendars remain readonly. Required CI is green with zero browser skips and artifacts.

## 8. Stop and ask

Stop only for a genuine out-of-scope file, security/privacy conflict or ambiguous data ownership. Routine implementation choices are authorized. Keep root informed at source checkpoints; do not wait for owner approval.

## 9. Report

Write docs/tasks/0123-calendar-create-popup-report.md with final changes, privacy safeguards, exact tested application SHA, CI run/counts, screenshot artifact links and whether local image pixel review was possible. Keep tested application SHA separate from later documentation-only commits. Preserve unrelated UI0041, PostHog snippet-not-dashboard and K-OPS72 history, and context caps.
