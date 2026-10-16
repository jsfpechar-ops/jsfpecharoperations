# 0123: Preserve host controls after in-page calendar creation
Status: in-progress
Base: 6c0bc56b08c49d755a93e18ac1c2b2d72b7e5e33 | Branch: feature/host-design0123-20261016 | PR #397
Report: docs/tasks/0123-calendar-refresh-controls-report.md

## 1. Objective
After Dashboard partial refresh, all imported existing host controls work as before: row menus, copy, row navigation, confirmation dialogs and banner dismissal.

## 2. Context
CI 38949363311 confirms a real source failure: actual .row-menu-panel never opens after replacing Dashboard work HTML. app.js initRowMenus (455–535) binds existing triggers only at DOMContentLoaded (2206+). initCopy (352–381), initClickableRows (731–755), confirmation forms (1371–1391), and dismiss banners (892–899) have the same node-bound pattern. Reuse these implementations; never replay DOMContentLoaded or duplicate global handlers. Dashboard intentionally caps display at five rows (admin.py 388–442 / reporting.py 570–618); no queue or filing changes.

## 3. Files
Create docs/tasks/0123-calendar-refresh-controls.md before editing App. Allowed: App/app/static/app.js (only listed initializer binding/hook work); App/app/templates/base.html (app.js cache tag only); App/app/static/dashboard-calendar.js (post-replacement hook only); App/app/templates/_dashboard_calendar.html (changed JS cache tag); App/tests/test_dashboard_calendar_browser.py; this brief and docs/tasks/0123-calendar-refresh-controls-report.md; existing 0123 popup/visibility briefs/reports (follow-up/scope references), docs/HOST_APP_DESIGN.md 0123 section, docs/context/status.md, docs/context/decisions.md, docs/context/known-issues.md. Read host.js and components/template macros as needed for current actions. Do not edit host.js, admin.py or reporting.py.

## 4. Steps
1. Add one scoped content-update event/hook between successful Dashboard region replacement and existing app.js controls. Use a named document event such as ubyhost:content-updated with the new region in detail.root. Dispatch after importing/replacing server-rendered regions. Keep calendar/filter/dialog elements intact and preserve saved-success/retry semantics.
2. Inside existing app.js initializers, factor their per-node binding so startup and this scoped update initialize the new nodes. Guard each node idempotently (WeakSet or equivalent). Retain the original closures/state for row-menu positioning/portals/keyboard and confirmation dialog. Global document/window, shell and dialog handlers must register once. No full-app reinitialization, new global MutationObserver, copied second implementation or unrelated refactor.
3. Cover initRowMenus, initCopy, initClickableRows, confirmation form/button bindings in initConfirmDialog, and initDismissBanners. Newly imported archive forms must still ask confirmation; cancel must not submit. Preserve focus, menu keyboard behavior, copy fallback, native anchors and no-JS routes.
4. Extend the refreshed-row browser case: real menu visible; copy works or its existing fallback appears; archive confirmation opens/cancels with no archive POST; row keyboard navigation still opens the correct Stay after explicit user action. Verify controls still work after repeated refresh/retry and global listeners are not duplicated. Keep no-navigation-on-save assertions separate from explicit navigation. Keep five-row retry canonical SSR/sentinel + one-POST/DB checks.
5. Bump app.js asset cache tag in base only, and changed calendar JS cache tag. Run all eight required CI jobs, zero calendar/browser skips and screenshots. No docs finalization before green.

## 5. Do not touch
No filing, queue ranking/limit, schema, permissions, CSRF/auth policy, dependencies, public/guest/auth designs, lock/time rules, main/merge/deploy. Do not remove or weaken the failing menu test.

## 6. Commands
Executor/CI only; managed local environment unavailable. Complete full required suite, calendar and broad Chromium geometry suites with zero skips and screenshots.

## 7. Acceptance
After real in-page creation and refresh, imported row/menu/copy/confirm/banner controls behave like startup controls; repeated refresh does not double-bind. One saved record; refresh-only retries; native fallback and all original workflows preserved. All eight CI jobs green.

## 8. Stop and ask
Stop only for a genuinely additional unscoped change or security/data ownership conflict; routine implementation is authorized. Push coherent checkpoints, keep root informed; no owner approval needed for this scoped correction.

## 9. Report
Record actual fix, exact tested App SHA/run/counts/screenshots and local PNG-view limitation. Finalize all 0123 reports/context only in a docs-only commit after green; restore original detailed briefs from 8cdd plus this explicitly approved scope/follow-up. Preserve UI0041, PostHog snippet-not-dashboard and K-OPS72 history and context caps. Owner receives the tested App SHA for manual Render staging deployment, separate from docs head.
