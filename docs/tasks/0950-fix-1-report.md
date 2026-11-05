# 0950-fix-1 report: PR #786 decisions and visible mobile filters

Status: blocked (implemented; runtime validation and merge unavailable)
Owner authorization: 2026-11-05, "you implement it".

## Changes

- Shared settings-pills partial accepts wrap_on_phone; Stays opts in, including its Archive filter view. Other settings/archive navigation retains its existing behavior.
- Below 768 px, opted-in strips wrap using the existing spacing token and visible overflow, keeping focus outlines and full labels available. Existing 44 px pill height, selected dark hover/focus state, link URLs and tablet/desktop layout are preserved.
- Added four browser regression cases: CS/EN at 320/390 px. They check each label's geometry, wrapping, touch size, strip/page overflow, keyboard order, archive selection, preserved property/status filters and selected hover/focus colors.
- Existing tests still cover settings archive and Stays at 390/768/1280. New phone cases save both active and archive screenshots when UBYHOST_SHOTS_DIR is set.
- Updated app2.css cache version and manifest hash together.
- Recorded all four owner decisions: no stay-page check-in/out times; four wizard steps; accepted/listed TTLock connection sufficient for "Lock online"; visible wrapped phone filters. No changes to wizard, TTLock or stay detail were needed.

## Validation

- Exact replacement anchors and the original stylesheet's manifest hash were checked before constructing the commit.
- New stylesheet SHA-256 was computed and recorded; browser geometry remains unverified.
- No tests, context lint, screenshot capture/review or merge script ran locally. Workspace startup fails with "managed network requirements require sandbox enforcement".
- Previous CI run #2908 on 4c7d11b5 does not validate these new changes. Fresh final-head CI is required.
- No UX checklist item is marked complete without execution. No new screenshot is claimed as reviewed.

## Remaining work

1. Run the relevant test-map host/static/browser/geometry checks and context lint from a functioning workspace, with zero browser skips.
2. Open the Stays screenshots at 390/768/1280 and CS/EN phone active/archive screenshots. Record actual observations and the design-system checklist in the PR description.
3. Replace the PR's open questions with the resolved decisions above and record final-head CI.
4. Review and merge only with scripts/merge-pr-on-green.sh. Production deploy remains manual.

## Scope notes

The shared partial lives in partials/settings_pills.html rather than _components.html; the brief's file list was corrected. Stays labels have no counts, so synthetic count text was not added. Settings archive navigation is unchanged; Stays' own Archive filter uses the new wrapping.

## Verified by the orchestrator session

- Status lint: `python3 scripts/context_lint.py` reports `context lint: OK` (status.md compacted in 3fff16a4; later owner-side edit also passes).
- Browser run from `App/` with `UBYHOST_REQUIRE_BROWSER=1`: 34 passed, 0 failed, 0 skipped across `test_host_pill_state_browser.py`, `test_layout_lint_browser.py`, `test_static_versions.py` and the 10 browser files that name the Stays/settings pills (0252, 0284, 0285, 0399, 0501-0506).
- `ruff check ... --select E9,F63,F7,F82,F401,F841`: All checks passed. `scripts/design_lint.py`: OK.
- Screenshots (EN, host fixture with no stays, so the empty list is shown): `docs/tasks/screenshots-0950-fix-1/verify-stays-en-390.png`, `verify-stays-en-768.png`, `verify-stays-en-1280.png`, `verify-stays-archive-en-390.png`.
  - 390 px: all six filters visible, no clipping. Wrapped into two rows: "Upcoming & current" and "In house" on row 1; "Past", "Report failed", "Archived" on row 2. Active pill dark. Archive view: "Archived" dark on row 2 with the archive empty state.
  - 768 px: single row, all five filters visible.
  - 1280 px: desktop header with Filters/Add stay; pills in one row, unchanged.
- Result: the owner's commit 355ec492 is verified for the Stays filters at these widths. CS at 320/390 is covered by the passing test cases, not by a screenshot here.
