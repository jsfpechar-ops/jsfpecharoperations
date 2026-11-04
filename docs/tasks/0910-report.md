# 0910 report

Status: blocked

## Done
- Step 1: Today moved before the arrows, class `cal-today`, stylesheet `?v=20261104-0910`. Commit `0910 step 1`.
- Step 2: calendar head is a two-row grid at >= 768 px (title, Today + arrows; row 2 filters; weekdays row 3). Old `order`/`flex` removed from the four rules, `.cal-today` margin added. Commit `0910 step 2`.
- Step 3: `App/tests/test_0910_calendar_toolbar_stable_browser.py` (15 tests). Imports `calendar_workspace` and `sync_api` in addition to the brief's list, because pytest needs them in the module namespace.

## Tests (From App/, 0 skipped)
- `test_0910_calendar_toolbar_stable_browser.py`: `15 passed in 45.17s`.
- `test_dashboard_calendar.py` + `test_calendar_*.py` + `test_sample_calendar.py`: `64 passed in 5.19s`.
- `test_dashboard_calendar_browser.py` + 0905 + 0898: `1 failed, 47 passed`. Failure: `test_month_tiles_and_side_panel[1024]` line 907, `.cal-toolbar h3` has `scrollWidth > clientWidth`. Cause: with the side panel open at 1024 px the calendar column is narrower than the 32 px title plus the 188 px arrow group, so the title is truncated (`overflow:hidden; text-overflow:ellipsis`, as the brief's design says). The old test asserts no clipping. Not fixed: the fix would change the 1024 title rule or the panel layout, which the brief forbids or does not cover.
- `test_layout_lint_browser.py`: `3 passed in 209.63s`.

## Screenshots
- `docs/tasks/screenshots-0910/calendar-0910-768.png`, `-1024.png`, `-1280.png` (test 3, default state, no panel). 1024 checked: Today left of arrows, arrows side by side, filters on row 2, title not clipped.
- 390 px: not captured (the `-k "0891 and 390"` run wrote no file to that folder).

## Deviations
Done: steps 1 to 3 (test 1 to 4 run). Left: Parts A, B, D (stay page and stay-fee guest details, their tests, screenshots); 768 and 1280 per-page UX notes; 390 shot; `scripts/context_lint.py`; PR.

## Questions
1. The 1024 side-panel-open title clip: accept truncation with ellipsis, or change the layout (for example let the title wrap or shrink the 32 px rule when a panel is open)?
2. Part C (Back/Forward) passed as written: Back went to /reservations, Forward restored the April 2026 month.

## Owner steps left
None until the questions are answered.
