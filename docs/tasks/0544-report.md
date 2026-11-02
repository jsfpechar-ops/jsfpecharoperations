# 0544 report

Status: blocked (geometry 10 of 12; 2 cases left for an owner decision)

## Files changed
- App/app/templates/_cleaning_table.html (pill classes)
- App/tests/test_0540_cleaning_tables.py (pill asserts)
- App/tests/v2_mockup.py (cleaning entry: `main .pill` removed, comment added)
- App/app/static/app2.css (cleaning block: calendar tap targets and text floor)
- App/app/templates/base.html (`app2.css?v=20261101-0544n`)
- App/tests/static_versions.json (regenerated with --write)
- docs/tasks/screenshots-0544/*.png (8 files)

## Commits
- cab448b `0544 step 1` (pill tones)
- eef4889 `0544 step 3` (geometry CSS, key bump, manifest)
- Step 2 (phone layout): skipped per coordinator instruction; not committed.
- Step 4: no file changes, so no commit.

## Commands (last lines)
- `test_0540_cleaning_tables.py`: `5 passed in 2.24s`
- `test_0710 -k cleaning` (browser, 0 skipped): `6 failed, 6 passed` before CSS; after step 3: `2 failed, 10 passed, 13 deselected`
- Regression set (`test_cleaning_browser`, `test_0252_touch_sweep_browser`, `test_design_guardrails_browser`, `test_0540`, `test_0541`, `test_cleaning`, `test_static_versions`): `1 failed, 87 passed in 150.37s`
- `python3 scripts/design_lint.py`: `design lint: OK`

## Cleaning-case results per width
- 768, 1024, 1280, 1440: pass
- 320, 390: fail (calendar only, see below)

## Findings fixed
- Calendar toolbar tap targets: 44 px at 768 to 1023, 24 px from 1024 (brief section 4 step 3).
- Calendar text under 12 px: scoped `max(12px,1em)` floor on `#calendar` in `.cleaning-page`.

## Findings left (source: calendar grid, cleaning page)
- 320 px: 56 findings. Calendar day numbers (38x44), `cal-more` buttons (39x44), `cal-event` links (37x46). The 7-column grid is 38 to 46 px per cell, so 44 px width does not fit without overflow.
- 390 px: 1 finding. `a.cal-event continues-end` 23x46.
- Cause: calendar grid at phone width. The phone layout (step 2, which hides the calendar) was skipped, so the calendar still shows below 768 px. Needs an owner decision: hide the calendar on phones, or accept the grid tap-target exemption.

## Deviations
- Step 2 skipped per coordinator.
- Step 4 regression: `test_0252_touch_sweep_browser` fails on `/` (Overview, not cleaning) at phone390 and ipad820: "Reserved" and "Reserved · N" items outside the touch area. Not on the cleaning page; not fixed (shared rule).
- Commit trailer: Co-Authored-By Haiku 5.5 used (the system attribution reminder); the brief text named Opus 5.5.
- No PR opened and nothing pushed (task said do not push).

## Questions
- Calendar on phones: hide it below 768 px, or exempt its day cells from the 44 px rule?

## Owner steps left
- Decide the calendar question above, then the phone layout brief (step 2 rebuild).
- Push and open the PR when the branch is ready: `git push -u origin claude/project-thread-c1h7ok`, then review.

Screenshots: docs/tasks/screenshots-0544/cleaning-{320,390,768,1024,1280,1440}.png, mockup-phone-uklid.png, mockup-clean-1280.png
