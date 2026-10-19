# 0124-fix-1 report

Status: review

## Files changed
- App/app/static/dashboard-calendar.js: line 591 in setCreateKind now calls placeCreate(createAnchor) synchronously (was requestAnimationFrame). Lines 853 and 858 untouched.
- App/app/templates/_dashboard_calendar.html: cache version refresh2 to refresh3.
- docs/tasks/0124-fix-1-report.md: this report.

## Commands
- `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_dashboard_calendar_browser.py -q --tb=short -rs 2>&1 | tail -5` (from App/): `11 passed, 1 warning in 27.81s`. No skipped tests.

## Acceptance (brief section 7)
- [x] Only the two files and the report changed.
- [x] Section 6 passes with 0 skipped.

## Deviations
- Step 2 committed before step 1 (commit 0286f9a, then ce8fb13). Both edits are in the branch; step 1 was rechecked before its commit. Cause: the two steps were sent in parallel. Net diff is the same as the brief.
- Screenshot not taken: brief section 7 does not require one, and the template change is a version string only.

## Questions
None.

## Owner steps left
None for this brief. CI rerun on the branch is still needed to confirm test_create_popover_reclamps_when_switching_to_taller_stay_form[1280] passes in Chrome 153.
