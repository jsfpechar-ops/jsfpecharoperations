# 0960 report

Status: review

## Changed files (`git diff de537cb3 --stat`)

- App/app/static/dashboard-calendar.css (8 +)
- App/app/static/dashboard-calendar.js (4 +-)
- App/app/templates/_dashboard_calendar.html (6 +-)
- App/tests/static_versions.json (8 +-)
- App/tests/test_dashboard_calendar_browser.py (76 +)
- App/tests/test_cleaning_browser.py (2 +-, step 4, outside section 3, see deviations)
- docs/tasks/0960-calendar-create-actions.md (brief status line)
- docs/tasks/0960-report.md

## Commands

1. `test_dashboard_calendar_browser.py -k "0960 or 0958 or reclamps"`: 26 passed, 0 skipped (earlier run, not repeated here)
2. `test_dashboard_calendar.py test_calendar_*.py test_sample_calendar.py`: 64 passed, 0 skipped (earlier run)
3. `test_dashboard_calendar_browser.py`: 63 passed, 0 skipped (earlier run)
4. `tests/test_cleaning*.py -q --tb=short -rs`, fresh DB: 80 passed, 0 failed, 0 skipped. Last lines: two progress lines (90 %, 100 %), `80 passed in 549.45s (0:09:09)`.
5. `test_static_versions.py test_wp07_cache_heartbeats.py -q -x`: 16 passed, 0 skipped
6. `python3 scripts/context_lint.py`: OK (WARN lines only: open-brief overlaps and "9 commits touched App/ after status.md")

## Centring decision

Replaced `abs(first["top"] - second["top"]) <= 8` with a centre check on each dialog: `abs(first["cy"] - first["vy"]) <= 8 and abs(second["cy"] - second["vy"]) <= 8`. Both dialogs are read by `[data-cal-create]` through `CREATE_CENTRE_JS` in `_assert_dialog_centred`. The top comparison fails by design once the form is `min-height:0`, because the two modes differ in height. CSS unchanged.

## Acceptance (section 7)

- [x] Steps 1 to 3 committed (a79c4ff3, e2de183d, 264f1eff); step 4 committed (94d53eb7).
- [x] Commands 1 to 6 green, 0 skipped (1 to 3 not rerun this session).
- [x] All 24 `calendar-0960-*` screenshots viewed.
- [ ] Diff stat lists only section 3 files: `App/tests/test_cleaning_browser.py` is also changed (step 4).
- [x] No guest data printed.

## Screenshots (all 24 viewed)

- All sizes, EN and CS: Cancel is white with a grey border on the left, Create is coral on the right, one row, same positions in stay and cleaning. No clipping, no horizontal scrollbar, no overlap, no empty block under the cleaning form. Label input matches Guests.
- 390: CS "Zrušit" and "Vytvořit pobyt/úklid" fit on one row.
- 768: dialog centred, one row, CS fits.
- 1280: dialog centred, one row.
- Red outline on Guests in stay mode is a focus state, not validation. The test focuses `#cal-guests` just before each stay screenshot, and cleaning shots (no focus) show no outline. No submit happened and no error text shows.
- Cleaning day-cell name is not visible in screenshots. Command 1 asserts "Add cleaning" / "Přidat úklid" (not run this session).

## Deviations

- Step 4 edits `App/tests/test_cleaning_browser.py`, outside section 3, as the orchestrator decided.
- Commands 1 to 3 and the 0960 screenshots come from the earlier run; the code they test is unchanged since step 3.

## Done / Left

- Done: steps 1 to 5, all commands, screenshots.
- Left: push `codex/0960-b02-calendar-create` and open the PR (owner or orchestrator). Not pushed.
