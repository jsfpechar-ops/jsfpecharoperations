# 0911 report

Status: blocked

Done: steps A1 to A4 and C written and committed. Part B CSS and app2.css calc applied; step B4 fails.
Left: fix the Part B chip geometry (see Deviations), run the rest of section 6, screenshots, lint, report finish.

## Files changed
- App/app/static/dashboard-calendar.js: ganttAllowed(), view(), syncControls() rows, PROPERTY_TONES palette (5 tones), pill data-cal-color, select data-cal-color (commit 6ccb259)
- App/app/static/dashboard-calendar.css: 0911 block at end (view rule, indigo/ink tones, bar colours, select dot, Part B >=768 vars and chip margin) (commit 6ccb259)
- App/app/static/app2.css: cleaning tile min-height line ~2219 now calc(52px + var(--pl,1) * 44px + 2 * 24px + 4px + 8px + 12px) (commit 6ccb259)
- App/app/templates/_dashboard_calendar.html, App/app/templates/base.html: cache keys 20261105-0911; App/tests/static_versions.json rewritten by --write
- App/tests/test_dashboard_calendar_browser.py: Gantt-for-one lines replaced (step A4)
- App/tests/test_0911_calendar_rule_colours_browser.py: new (tests 1 to 5)

## Commands (last lines)
- `pytest tests/test_dashboard_calendar_browser.py -k auto_view_threshold`: `1 passed, 38 deselected in 7.17s`
- `pytest tests/test_0911_calendar_rule_colours_browser.py -x -rs`: `1 failed, 9 passed in 16.23s` (stopped at first failure)
- Failing test: `test_0911_bars_never_cover_cleaning_chips[768]`, `assert chip["y"] >= lowest_pill + 7`, values `684 >= (689 + 7)`.
- Not run yet: the dashboard, 0905, 0910, 0898, cleaning, lint-browser, static and context_lint commands; screenshots; `docs/tasks/screenshots-0911/`.

## Deviations
- Brief assumed bars 32 px high with a 44 px lane. Measured at 768: each `.cal-pill` box is 44 px high, so the lane pitch is 56 px (44 + 12 gap), not 44. Tile at 768 is 230 px high. Last bar bottom is at tile top + 152 px, chips at tile top + 147 px. Chip natural top is 47 px below tile top (684 - 537 - 100).
- Proposed fix for the orchestrator to approve (not applied): `--cal-lane:56px`; `.cal-tile-chips` margin-top `calc(var(--cal-num-band) + var(--pl,1) * var(--cal-lane) - 12px + 8px - 47px)`; app2.css min-height `calc(52px + var(--pl,1) * 56px + 60px)`. Cause of the 44 px bar height not yet found (no 44px rule found in grep of cal-pill; check computed height in the browser).
- A4 test: one assertion block changed as the brief says; no other existing assertion changed.

## Questions
- Why is `.cal-pill` 44 px high at 768 but 32 px at >= 1024 (the 32 px rule is in dashboard-calendar.css line 799)? Is the 768 bar stretched by the grid row?

## Owner steps left
- None yet. No push, no PR.
