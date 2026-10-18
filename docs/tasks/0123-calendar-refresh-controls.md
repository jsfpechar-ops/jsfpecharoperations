# 0123: Preserve host controls after in-page calendar creation

Status: done
Base: 6c0bc56b08c49d755a93e18ac1c2b2d72b7e5e33 | Branch: feature/host-design0123-20261016 | PR #397
Report: docs/tasks/0123-calendar-refresh-controls-report.md

## 1. Objective

After Dashboard's partial refresh, imported host controls work exactly like the original controls: row menus, copy, row navigation, confirmation dialogs, and banner dismissal.

## 2. Context

CI found that the actual row-menu panel did not open after replacing Dashboard work HTML. app.js initializers bind existing nodes at DOMContentLoaded. Copy, clickable rows, confirmation forms/buttons, and dismiss banners have the same node-bound pattern. Reuse those implementations without replaying DOMContentLoaded, duplicating global handlers, changing the five-row Dashboard cap, or changing queue/filing behavior.

## 3. Files

App/app/static/app.js (only the scoped node-binding work); App/app/templates/base.html (app.js asset cache tag only); App/app/static/dashboard-calendar.js (post-replacement hook only); App/app/templates/_dashboard_calendar.html (calendar JS cache tag only); App/tests/test_dashboard_calendar_browser.py; docs/tasks/0123-calendar-refresh-controls.md; docs/tasks/0123-calendar-refresh-controls-report.md; docs/tasks/0123-calendar-create-popup.md; docs/tasks/0123-cleaning-visibility.md; docs/HOST_APP_DESIGN.md 0123 section; docs/context/status.md; docs/context/decisions.md; docs/context/known-issues.md.

## 4. Steps

1. Dispatch one scoped content-updated event after replacing the connected Dashboard work region. Pass the imported region as detail.root. Do not replace the calendar, filters, header, or dialogs.
2. Factor a shared node-binding helper inside the existing app.js initializers. Scan initial document nodes once and listen for the scoped update to visit only its connected root. Use a WeakSet or equivalent to make each node idempotent.
3. Apply the helper only to the existing copy, row-menu, clickable-row, confirmation form/button, and dismiss-banner initializers. Keep each callback body, closure state, menu portal/keyboard behavior, copy fallback, confirmation state, focus behavior, and all global/shell/dialog registrations intact. Do not reinitialize the full app or add a global MutationObserver.
4. Verify imported archive confirmation opens and cancellation performs no POST; copy succeeds or shows its existing fallback; menu and keyboard row navigation work; repeated updates do not double bind; native links and no-JS routes remain intact.
5. Keep Dashboard's intentional five-row cap and queue ranking. The retry coverage compares visible IDs and stable row-copy text from fresh canonical HTML with the rendered region, verifies a synthetic sentinel refresh, exact saved Stay DB values, and one create POST. Do not require a row excluded by the cap.
6. Run all eight required CI jobs with zero calendar/browser skips and screenshot artifacts. Final reports and context changes stay in a docs-only commit after the green run.

## 5. Do not touch

No filing, queue ranking/limits, schema, permissions, CSRF/auth policy, dependencies, public/guest/auth design, lock/time rules, main, merge, or deploy. Do not modify host.js, admin.py, or reporting.py.

## 6. Commands

Executor/CI only. Complete the full required suite, calendar review, broad Chromium geometry/browser checks with zero skips, and screenshots. No local environment-policy bypass.

## 7. Acceptance

After real in-page creation and retry, imported menu, copy, confirmation, navigation, and banner controls behave as expected; repeated refresh is idempotent. The one saved record cannot be duplicated by a failed refresh. All eight CI jobs pass.

## 8. Stop and ask

Stop only for a genuine unscoped-file, security, or data-ownership conflict. The authorized node-binding and test work needs no further approval.

## 9. Report

Record the actual fix, exact tested application SHA, CI run/counts/artifacts, and the fact that screenshots were neither downloaded nor inspected locally. Final docs are separate from the tested Render hand-off.
