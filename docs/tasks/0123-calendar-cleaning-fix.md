# 0123 Calendar and cleaning correction

Status: in-progress
Base/current head: 248020f9bdb9c1a44d0f9dd66a3819484dec0805
Branch: feature/host-design0123-20261016 | PR #397
Executor: Luna executor
Report: docs/tasks/0123-calendar-cleaning-fix-report.md

## 1. Objective

Restore compact, native calendar controls and correct fractional-day booking/cleaning display while keeping the approved flat-white design and all current behavior.

## 2. Context

- Restore native property/month/year selects, icon+label Calendar/Gantt segmented controls, and Month/Week/Year segmented controls. Auto remains in Settings; preserve property-count automatic selection, URL/storage, manual persistence, filters, and all actions.
- A 15–17 stay displays from property check-in on the 15th through checkout on the 17th. Keep real date-only endpoints for availability, conflicts, and creation. Use a visual half-day fallback only for missing/invalid hours; never persist fallback hours.
- Automatic cleaning occupies the same checkout date between property checkout and check-in hours, regardless of a later next arrival. Preserve date overrides and legacy explicit event times; no duplicate time entry.
- Cleaning markers need a reserved visible lane/summary with truthful cleaning overflow and working day dialog. Keep the calendar dense and mobile controls at least 44px.
- Cleanings exclude demo reservations by design. Preserve synthetic/privacy safeguards and find why markers are hidden before changing filtering.
- Keep cleaning chronological groups compact, essential facts readable, existing actions/instructions and optional door-code permissions. Hide the complete code section when no usable code exists; do not show an empty instructions placeholder. Omitted legacy time fields on edit must not clear stored exceptions.
- Invalid or non-increasing property hours do not define a valid same-day cleaning window: show a visible warning and avoid zero/negative-width invisible cleaning. Never invent confirmed times.
- No schema migration, new dependencies, guest-data changes or lock API calls.

## 3. Files

Calendar: `App/app/templates/_dashboard_calendar.html`; `App/app/static/dashboard-calendar.js`; `App/app/static/dashboard-calendar.css`; `App/app/static/host-design0123.css`; `App/app/templates/base.html`; `App/app/routes/dashboard_calendar.py`.
Cleaning: `App/app/cleaning.py`; `App/app/routes/cleaning.py`; `App/app/templates/cleaning.html`; `App/app/templates/_cleaning_screen.html`; `App/app/templates/_cleaning_list.html`; `App/app/templates/cleaning_edit.html`; `App/app/templates/cleaning_settings.html`; `App/app/templates/cleaning_shared.html`; `App/app/static/cleaning.js`; `App/app/static/cleaning.css`; `App/app/cleaning_i18n.py`.
Tests/CI: `App/tests/test_dashboard_calendar.py`; `App/tests/test_dashboard_calendar_browser.py`; `App/tests/test_cleaning.py`; `App/tests/test_cleaning_browser.py`; `App/tests/test_host_geometry.py`; `App/tests/test_host_wide_geometry_browser.py`; `App/tests/test_host_list_layouts_browser.py`; `App/tests/test_host_quiet_dashboard_browser.py`; `.github/workflows/ci.yml` only if focused coverage is not already required.
Docs: this brief and report; `docs/tasks/0123-host-design.md` and report; `docs/HOST_APP_DESIGN.md`; `docs/context/status.md`; `docs/context/decisions.md`; `docs/context/known-issues.md`.

## 4. Steps

1. Restore compact native selectors and segmented calendar controls with existing state, URL, storage, settings and keyboard hooks; align baselines, chevrons and wrapping through the 1024px narrow lane.
2. Trace the read-only calendar API, display lane allocation, cleaning schedule/serialization and templates. Add separate fractional display endpoints from valid property hours, clipped to visible/shared range; never change date-only reservation, conflict, or creation semantics.
3. Reserve a bounded cleaning lane and explicit cleaning overflow summary. Keep cleaning visible when booking density reaches the current lane cap, including multiple properties and mobile.
4. Make automatic cleaning a same-day checkout-to-check-in interval. Preserve explicit legacy event overrides on omitted form fields and retain compatibility without showing duplicate time inputs in the normal flow.
5. Compact cleaning date/property surfaces; conditionally omit the entire optional code section when no usable code is available; remove empty instruction placeholders.
6. Add focused API, unit and browser regressions for 15–17 checkout display, checkout-day cleaning, adjacent same-day stays, clipping/left-edge privacy, overflow, property filters, Auto/manual controls, mobile, and empty-code presentation.
7. Run full CI with required Chromium/geometry suites and screenshots. Finalize report/context after the tested application SHA is green.

## 5. Do not touch

Do not change filing, reservation date semantics, availability/overlap guards, stay creation, owner/privacy scoping, demo safeguards, sharing permissions, TTLock/code storage or issuance, public/guest/auth UI, database schema, dependencies, main, merge or deployment.

## 6. Commands

The managed shell/browser is unavailable. Use repository CI for the full test suite, required Chromium and geometry checks with zero skips, and screenshot artifacts. Do not claim local visual inspection.

## 7. Acceptance

Old compact selects and icon/label segmented controls return with working Auto/manual/property-filter behavior; controls fit EN/CS at 360/390/760/1024/1280 and wide screens with 44px mobile targets. A 15–17 stay reaches the checkout fraction on the 17th; cleaning stays on the 17th between valid property hours even when the next arrival is later. Cleaning remains visible with two or more property rows and honest overflow. Invalid hours are flagged without invented persisted defaults. Optional missing-code sections and empty instruction placeholders disappear. Existing manual exceptions and all actions remain intact. Full CI and required browser/geometry checks pass with zero skips and evidence.

## 8. Stop and ask

Pause for a genuine scope/security/data-precedence conflict or a necessary file outside §3. Routine visual and implementation choices are authorized.

## 9. Report

Use `docs/tasks/0123-calendar-cleaning-fix-report.md`. Record the tested application SHA, CI run and exact test counts, screenshot artifact links, data/display semantics, and the local pixel-review limitation.
