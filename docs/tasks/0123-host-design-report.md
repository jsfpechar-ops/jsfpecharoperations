# 0123 — Host workspace visual refresh report

## Result

Implemented the owner-approved, host-only visual refresh in draft PR [#397](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/397), on branch `feature/host-design0123-20261016`, based on main commit `dc5f730d63f7183a6f261c5d0e44f0966430addf`.

The new stylesheet clarifies page and section hierarchy, softens panel and list/table borders, aligns filter labels and actions, presents the three dashboard counts as compact inline pills, and refines the calendar controls and dashboard action rows. It loads only for the signed-in host shell; shared tokens remain untouched.

The existing shell already provides the warm canvas, white surfaces, coral actions, 216px rail and centered 1080px work lane. This implementation builds on that visual base while preserving the existing layout breakpoints and action tracks. Cleaning section and date headings retain their larger readable sizes. A review correction keeps touch controls at least 44px and removes unused prototype queue selectors. Desktop calendar controls retain compact geometry for the 1024px height bound.

## Behavior retained

No route, endpoint, form method, CSRF field, data attribute, JavaScript interaction, permission, sharing rule, filing state, guest-data flow or dependency changed. Calendar creation and view preferences, overlap confirmation, filters and no-JavaScript GET behavior, exports, saved views, archive/restore, visible guest facts, stay controls, settings and expanded cleaning instructions remain on the current implementations.

## Files

- `App/app/static/host-design0123.css`: host-scoped hierarchy, controls, lists, dashboard and calendar styling.
- `App/app/templates/base.html`: conditional host-only stylesheet link and cache key.
- `App/tests/test_host_filter_panels_browser.py`: configurable screenshot destination.
- `App/tests/test_host_wide_geometry_browser.py`: shared configurable evidence directory for all test outputs.
- `.github/workflows/ci.yml`: required Chromium job adds both existing suites and uploads their screenshots.
- `docs/tasks/0123-host-design.md`: brief and scoped file list.
- `docs/context/status.md`, `docs/context/decisions.md`, `docs/context/known-issues.md`: review context.

## Validation

No local browser runner was available in the managed environment. The draft PR runs the existing full suite and required Chromium suites with missing-browser skips treated as failures. The wide-geometry tests retain lane, viewport, text-track and trigger bounds while checking native date links and opening two synthetic stay menus per locale and viewport for the localized Copy guest form link, popup bounds, 44px mobile items and keyboard dismissal; they assert the removed portal shortcut is absent. Filter and wide-geometry screenshots use the existing `dashboard-calendar-review` upload artifact. See [PR checks](https://github.com/jsfpechar-ops/jsfpecharoperations/pull/397/checks) for exact results and uploaded screenshots.
