# 0817: Polish the 0814 phone calendar before Josef sees it

Status: done
Depends on: 0814 (committed) | Branch: claude/project-thread-vnnr9p
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The orchestrator reviewed `docs/tasks/screenshots-0814/calendar-range-390.png` and `calendar-create-390.png`. The 0814 build works (48 tests green) but does not look like Airbnb yet. Fix the items in section 2, then retake the 0814 screenshots. Run it before 0816 and 0815.

## 2. Context

What is wrong in the 390 px screenshots:
1. The grid still sits in a grey bordered card (`.cal-body` / `.cal-week` background and border). Remove it: white page background, no outer border, no grey behind the tiles.
2. Prev/next arrows are filled coral circles. Make them 40 px round, background `#f2f2f0`, ink chevron, no border.
3. The booking bars run past the tile edges and get clipped (they are 14 px wide, several per tile, and overflow). Max 3 bars per tile, each `flex:0 1 10px`, `.cal-dots` `max-width:100%; overflow:hidden; padding:0 6px`, then `+n`.
4. Selected tiles have a coral outline (old `.is-selected` box-shadow or the focus ring). Selected = `#222` fill, no outline, no box-shadow; keep a visible focus ring only for `:focus-visible` (keyboard), as a 2 px ink outline with 2 px offset.
5. In the sheet, the × is almost invisible: ink `#222` × glyph 18 px on `#f2f2f0`.
6. The sheet has a large empty gap between the pill and Add when there are no stays: the gap must be 16 px. The floating help "?" bubble overlaps Add: while the sheet is open, hide the help bubble (`body:has(.dashboard-calendar [data-cal-day-dialog][open]) <help bubble selector>`; find the selector in the shell templates) or lift it above the sheet.
7. The create dialog toggle "Stay / Cleaning" uses a coral filled pill for the inactive choice. Use a segmented control: track `#f2f2f0`, selected segment white with ink text and a soft shadow, 40 px tall.
8. `calendar-create-390.png` was taken mid-animation (half transparent). Wait for the dialog's transition to finish (`page.wait_for_function` on computed opacity == 1) before every screenshot.
9. The property select is 13 px text in a 40 px box: 16 px text, 48 px tall, radius 12 px (also stops iOS zoom).

## 3. Files

| Path | Action |
|---|---|
| `App/app/static/dashboard-calendar.css` | edit the 0814 block |
| `App/app/templates/_dashboard_calendar.html` | bump css `?v=` to `20261102-0817` |
| `App/tests/static_versions.json` | regenerate |
| `App/tests/test_dashboard_phone_browser.py` | add assertions for items 2, 3, 4, 6 and 8; retake screenshots |
| `docs/tasks/screenshots-0814/` | overwrite the 0814 PNGs |
| `docs/tasks/0817-report.md` | create |

## 4. Steps

1. Read the 0814 CSS block (`grep -n "0814" App/app/static/dashboard-calendar.css`) and the shell help-bubble selector.
2. CSS fixes, then tests, then screenshots, then report.

## 5. Do not touch

JS behaviour (tap, long press, sheet logic), the cleaning page, desktop bars.

## 6. Commands

From `App/` with `UBYHOST_REQUIRE_BROWSER=1`: `.venv/bin/python -m pytest tests/test_dashboard_phone_browser.py tests/test_dashboard_calendar_browser.py tests/test_cleaning_browser.py tests/test_0199_phone_geometry_browser.py tests/test_0252_touch_sweep_browser.py tests/test_static_versions.py -q --tb=short 2>&1 | tail -30`. Repo root: `python3 scripts/context_lint.py 2>&1 | tail -5`.

New assertions: arrow background not coral; every `.cal-dot` right edge ≤ its tile's right edge; selected tile `box-shadow` is `none` and outline style `none` (when not keyboard-focused); help bubble not overlapping the Add button; screenshot taken only at opacity 1.

## 7. Acceptance

- [ ] All tests pass, 0 skipped. Five 0814 screenshots retaken and visually match section 2.
- [ ] Lint OK. Only section 3 files changed.

## 8. Stop and ask

A fix needs JS; a shared shell rule must change; 25 tool calls.

## 9. Report

`docs/tasks/0817-report.md`: files, test last lines, deviations.
