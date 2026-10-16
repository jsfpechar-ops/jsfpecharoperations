# 0123 — Host workspace visual refresh report

## Result

Implemented the approved host-only visual refresh in `feature/host-design0123-20261016`, based on main commit `dc5f730d63f7183a6f261c5d0e44f0966430addf`.

The new stylesheet clarifies heading and section hierarchy, quiets white panels and list/table rows, aligns filter controls and summaries, compacts dashboard counts into inline pills, and refines calendar controls and queue rows. It loads only in the signed-in host shell and leaves shared tokens untouched.

The existing host template and CSS already provide the warm canvas, white surfaces, coral actions, 216px rail and centered 1080px work lane. This change improves hierarchy and control treatment while preserving those established geometry rules and existing data/action tracks.

## Behavior retained

No endpoint, form method, CSRF field, data attribute, JavaScript interaction, permission, sharing rule, filing state, guest-data flow or dependency changed. Calendar creation, view preferences, overlap confirmation, filtering, no-JavaScript GET behavior, exports, saved views, archive/restore, guest facts and cleaning instructions remain on existing implementations.

## Files

- `App/app/static/host-design0123.css`: host-scoped visual layer.
- `App/app/templates/base.html`: conditional host-only stylesheet link and cache key.
- `App/tests/test_host_filter_panels_browser.py`: configurable screenshot destination for CI evidence.
- `App/tests/test_host_wide_geometry_browser.py`: one configurable output-directory helper for every geometry artifact.
- `.github/workflows/ci.yml`: required Chromium run includes both existing suites and uploads their screenshots.
- This brief and report.

## Validation

A local browser run was unavailable in the managed environment. Required CI is triggered by the draft PR. It runs the existing full suite and required Chromium suites with browser skips treated as failures, and uploads wide-geometry and filter-panel screenshots under `dashboard-calendar-review`. The report will be updated with the exact CI result after it completes.
