# 0544: Cleaning page: approved phone layout, pill tones, remaining geometry
Status: todo
Depends on: 0543 (same branch; Overview shell merged at 7fdeecc) | Branch: claude/project-thread-c1h7ok
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
1. Below 768 px, `/cleaning` looks like the approved phone mockup's Úklid screen (owner approved 2026-11-01 16:55): `/mnt/project-files/ux-redesign/phone/ubyhost-phone-v1.html`, `<section ... data-s="uklid">` (lines 411-430), CSS at the top of that file.
2. Pill tones follow the phone mockup at every width: scheduled = `p-ok`, conflict and hours missing = `p-warn`.
3. All 12 `cleaning-*` cases of `App/tests/test_0710_v2_mockup_match_browser.py` pass.

## 2. Context
- Markup: `App/app/templates/cleaning.html` (`.head.cleaning-head` with h1, `.sub`, two `.ov-link`s, `.btn`), `App/app/templates/_cleaning_table.html` (per section: `<h2>`, `.card > table`, rows `tr.clickable-row` with 5 cells: property link, time/day, next arrival, `.pill`, `td.dots` with `.row-open`). Calendar: `_cleaning_calendar.html` include (`.cleaning-legend` + `section#calendar.dashboard-calendar`) after the list.
- CSS: the `/* cleaning (0542) */` block at the END of `App/app/static/app2.css`; put all new rules there, scoped `body.v2 .cleaning-page` or `body.v2 .cleaning-head`. Shared rules above it are not yours.
- Phone mockup values (copy exactly): `.big` 32px/800, letter-spacing -.025em, line-height 1.15; `.sub` 15px `var(--ink3)`; `.grp` (section title) 13px/800 uppercase `var(--ink3)` letter-spacing .05em, margin 22px 0 2px; `.card` white, radius 18px, padding 0 18px, border 1px solid #f1f0ec, box-shadow `0 1px 2px rgba(0,0,0,.05),0 6px 20px rgba(0,0,0,.07)` (design lint forbids raw colours and literal box-shadow in CSS: use existing tokens or add the two values as custom properties in the cleaning block only if `scripts/design_lint.py` passes; else use `var(--line)` border and no shadow, and note it); `.row` min-height 76px, padding 12px 0, border-bottom 1px solid `var(--line)` (none on the last); row title 16px bold; row line 14px `var(--ink3)`, margin-top 2px; `.pill` 13px/700, padding 5px 10px, a 7px dot before (`::before`, `currentColor`), margin-top 6px; `.btn` full width, min-height 50px, radius 12px, 16px/700.
- `App/tests/v2_mockup.py` `PAGES` cleaning entry; the desktop mockup shows "Naplánováno" amber, the newer approved phone mockup green. The owner's latest approval wins.

## 3. Files
`App/app/templates/_cleaning_table.html` (pill classes only), the cleaning block of `App/app/static/app2.css` (+ `?v=` key in `App/app/templates/base.html`, `App/tests/static_versions.json` via `--write`), `App/tests/v2_mockup.py` (cleaning entry only), `App/tests/test_0540_cleaning_tables.py` (pill assertions only). Screenshots `docs/tasks/screenshots-0544/`. Report `docs/tasks/0544-report.md`.

## 4. Steps
1. **Pill tones.** In `_cleaning_table.html`: conflict -> `p-warn`, hours missing -> `p-warn`, scheduled -> `p-ok`. Update the matching asserts in `test_0540_cleaning_tables.py`. In `v2_mockup.py` remove `"main .pill"` from the cleaning selectors and add a comment on that entry: `# pills follow the approved phone mockup (2026-11-01): scheduled green, the desktop mockup shows amber`. Commit `0544 step 1`.
2. **Phone layout**, one `@media (max-width: 767px)` block in the cleaning block, CSS only (no markup change):
   - `.cleaning-head h1` like `.big` (keep the coral underline only if the phone mockup has one: it does not, so `.cleaning-head h1:after{display:none}`); `.sub` like `.sub`; `.btn` like `.btn` (full width, below the links).
   - section `h2` like `.grp`.
   - `.card` like the phone `.card`; inside it `table, tbody, tr, td {display:block}`, `thead {display:none}`; each `tr` like `.row` with `position:relative; padding-right:56px`; first cell like the row title; the time/day and arrival cells `display:inline` 14px `var(--ink3)`, with `content:" · "` before the arrival cell; the pill cell on its own line like `.row .t .pill`; `td.dots` `position:absolute; right:0; top:50%; transform:translateY(-50%)` (keeps the 44 px `.row-open` cue, which the touch-sweep test requires).
   - Pill: 13px/700, padding 5px 10px, dot `::before` 7px round `currentColor`, gap 6px.
   - Hide the legend and the calendar (`.cleaning-legend`, `#calendar`): the phone screen has none.
   Commit `0544 step 2`.
3. **Geometry.** Run `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k cleaning -q --tb=short -rs 2>&1 | tail -60`. Fix findings inside the cleaning block: calendar toolbar controls (`.cleaning-page #calendar button, .cleaning-page #calendar select, .cleaning-page #calendar a`) min 44x44 px from 768 to 1023 px and min 24 px from 1024 px up; any remaining overlap or overflow in `.cleaning-head` or the tables. Re-run until all 12 pass. If a finding comes from the sidebar or another shared rule, do not fix it: list it in the report and stop. Commit `0544 step 3`.
4. **Regression.** `.venv/bin/python -m pytest tests/test_cleaning_browser.py tests/test_0252_touch_sweep_browser.py tests/test_design_guardrails_browser.py tests/test_0540_cleaning_tables.py tests/test_0541_cleaning_header.py tests/test_cleaning.py tests/test_static_versions.py -q --tb=short -rs 2>&1 | tail -30`. Fix only cleaning-page causes; list others. Commit `0544 step 4`.
5. **Screenshots** with a throwaway script in `/tmp` (copy `test_v2_screenshots` from `test_0710`): `/cleaning?lang=cs` full page at 320, 390, 768, 1024, 1280, 1440 as `cleaning-<w>.png`; the phone mockup Úklid screen at 390 as `mockup-phone-uklid.png` (open the file, then `page.evaluate("document.querySelectorAll('#live .scr').forEach(s=>s.classList.toggle('on', s.dataset.s==='uklid'))")`, screenshot `#live`); the desktop mockup `clean` view at 1280 as `mockup-clean-1280.png`. Commit `0544 step 5`.

## 5. Do not touch
Shared `app2.css` rules, `_shell_v2.html`, `dashboard.html`, the mockups, other `PAGES` entries, the cleaner's shared view, JS, routes. No new dependency, no migration.

## 6. Commands
In the steps (from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`), then from the repo root `python3 scripts/design_lint.py 2>&1 | tail -3`.

## 7. Acceptance
12 `cleaning-*` cases pass; step 4 set passes or only lists non-cleaning failures; 0 skipped; lint OK; 8 screenshots.

## 8. Stop and ask
Stop if a fix needs a shared rule, markup outside section 3, or if the phone layout cannot be reached with CSS on the current markup (report what is missing).

## 9. Report
`docs/tasks/0544-report.md` (write it; it is part of the brief): Status, test and lint tails, findings fixed, findings left with their source, screenshot paths, deviations.
