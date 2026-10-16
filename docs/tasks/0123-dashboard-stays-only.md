# 0123: Dashboard calendar shows stays only

Status: in-progress
Base: c1ad0582da87baf2119bca36be459ff46e9abdd2
Branch: feature/host-design0123-20261016 | PR #397
Report: docs/tasks/0123-dashboard-stays-only-report.md

## 1. Objective

Dashboard calendar shows stays only in every view, overflow, and details. Cleaning keeps its markers in the Cleaning section. Preserve the popup type choices and Add cleaning action on Dashboard; the owner requested hiding calendar event tags, not removing creation controls.

## 2. Context

Dashboard route currently appends cleaning.schedule(..., include_private=False) to owner-scoped reservation events. Removing that append at the source avoids hidden cleaning counts and lanes across calendar, Gantt, year, overflow, and details. Keep all saved cleaning records, scheduling, Property hours, creation controls, and Cleaning/shared views intact. Baseline application SHA a8a3de98db922c3ec1192e9f2d7e2927eec7cb29 passed all eight CI jobs: 103 calendar and 181 browser tests, zero skips.

## 3. Files

App/app/routes/dashboard_calendar.py (import and appended cleaning block only); App/tests/test_dashboard_calendar.py (existing cleaning serialization test contract); App/tests/test_dashboard_calendar_browser.py (existing Dashboard creation test cleaning-marker assertions and screenshot capture); docs/tasks/0123-dashboard-stays-only.md; docs/tasks/0123-dashboard-stays-only-report.md; docs/HOST_APP_DESIGN.md Cleaning management paragraph only; docs/tasks/0123-calendar-create-popup-report.md (follow-up pointer only); docs/context/status.md, docs/context/decisions.md, docs/context/known-issues.md (existing #397/K-UI01 lines only).

## 4. Steps

1. In dashboard_calendar.py remove the cleaning import and delete only the block in events() that appends cleaning.schedule(..., include_private=False) records. Preserve reservation queries, authorization, serialization fields, cache headers, date/filter checks, and return behavior.
2. Update test_dashboard_calendar_exposes_cleaning_marker_without_private_fields to prove Dashboard excludes cleaning events and prefixed IDs. Seed a cleaning with property hours and private notes; assert the route does not call cleaning.schedule, the cleaning is absent, private data is absent, and real reservation assertions still pass. Preserve fixture cleanup and all existing owner/property/date/access tests.
3. In test_dashboard_calendar_creation_refreshes_cleaning_and_stay_in_place preserve the real Add cleaning POST 201, one saved row, correct property/date/notes, same pathname, and no navigation. Assert absence of cleaning events in Dashboard Calendar and Gantt. Separately open the actual Cleaning page and prove the created cleaning remains visible there. Keep the later Stay creation, bounded refresh, menu/copy/archive-cancel/navigation, and idempotence assertions unchanged. Capture Dashboard-without-cleanings and Cleaning-with-markers screenshots.
4. Run the required test suite, calendar and broad Chromium browser/geometry suites with zero skips and screenshots. Do not broaden tests or remove existing Cleaning visibility/privacy coverage.

## 5. Do not touch

No Cleaning routes/service/private schedule code, shared renderer/CSS/templates/JS, permissions, filing/TTLock/schema/dependencies, Add buttons/type choices, main, merge, or deployment. Do not remove saved cleanings.

## 6. Commands

Executor/CI only. Use the normal required tests, Chromium browser/geometry checks with zero skips, and screenshot artifacts. The managed local environment is unavailable; do not bypass environment enforcement.

## 7. Acceptance

Dashboard API, calendar, Gantt, year, overflow, and details contain stays only. A new Cleaning saves once without navigation and remains visible in Cleaning, not Dashboard. Existing Stay creation, filters, Auto/manual behavior, popup/refresh controls, cleaning markers in Cleaning, and Property timing remain intact. All eight CI jobs pass with zero browser skips.

## 8. Stop and ask

Stop only for a genuine out-of-scope source file, security issue, or privacy/data ambiguity. Routine implementation choices are authorized. Ask root to review any additional-file need before editing it.

## 9. Report

Record exact behavior, tested application SHA/run/counts/artifacts, unchanged workflows, and manual Render staging steps in docs/tasks/0123-dashboard-stays-only-report.md. Keep the tested App SHA distinct from later docs commits. Do not claim local PNG inspection. No merge or deployment.
