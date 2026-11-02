# 0545: Cleaning page desktop polish to match the mockup row by row
Status: todo
Depends on: 0544 (same branch) | Branch: claude/project-thread-c1h7ok
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
At 1024 px and up, the `/cleaning` tables match the desktop mockup (`docs/design/mockup/ubyhost-redesign-v2.html`, view `clean`; screenshot `docs/tasks/screenshots-0544/mockup-clean-1280.png`) instead of the current tall rows (`docs/tasks/screenshots-0544/cleaning-1280.png`): row height about 46 px, short dates ("Po 3. 11."), a small open cue instead of an empty 44 px circle.

## 2. Context
- Rows: `App/app/templates/_cleaning_table.html`. Dates come from `cleaning_date` in `_context()` of `App/app/routes/cleaning.py` (full "Úterý 3.11.2026").
- CSS: the `/* cleaning (0542) */` block at the end of `App/app/static/app2.css`. Today it forces `td a{min-height:44px}` and `.row-open{width:44px;height:44px}` at every width; the shared tap-target rule is 44 px below 1024 px and 24 px from 1024 px up (see the `0711 tap targets` block above it).
- `.row-open` is from `row_open()` in `_components.html`; its text is visually hidden, so the circle looks empty.

## 3. Files
`App/app/routes/cleaning.py` (`_context` only), `App/app/templates/_cleaning_table.html`, the cleaning block of `App/app/static/app2.css` (+ `?v=` key in `base.html`, `tests/static_versions.json` via `--write`), date assertions in `App/tests/test_0540_cleaning_tables.py`, `App/tests/test_cleaning_browser.py` (host table only). Screenshots `docs/tasks/screenshots-0545/`. Report `docs/tasks/0545-report.md`.

## 4. Steps
1. **Short dates.** In `_context()` add `cleaning_day(value)` -> cs `"Po 3. 11."`, en `"Mon 3 Nov"`, vi `"T2 3/11"` (weekday abbreviations cs `Po Út St Čt Pá So Ne`, en `Mon Tue Wed Thu Fri Sat Sun`, vi `T2 T3 T4 T5 T6 T7 CN`; en months `Jan`..`Dec`), and `cleaning_short(value)` -> cs `"3. 11."`, en `"3 Nov"`, vi `"3/11"`. Keep `cleaning_date` (the shared view uses it). In `_cleaning_table.html` use `cleaning_day(item.date)` in the Day cell and `cleaning_short(item.nextArrival)` in the arrival cell. Update date assertions in the two test files. Commit `0545 step 1`.
2. **Row height and cue.** In the cleaning block: move `td a{min-height:44px}` and `.row-open{width:44px;height:44px}` into `@media (max-width:1023px)`; from 1024 px: `td a` `min-height:24px`, `.row-open` 24x24 px, no border, `color:var(--ink3)`, with `::after{content:"›";font-size:18px;line-height:1}`; `td.dots` `width:40px;text-align:right`. Commit `0545 step 2`.
3. **Check.** `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -k "cleaning and (768 or 1024 or 1280 or 1440)" -q --tb=short -rs 2>&1 | tail -30` (must stay green), then `.venv/bin/python -m pytest tests/test_cleaning_browser.py tests/test_0252_touch_sweep_browser.py tests/test_0540_cleaning_tables.py tests/test_cleaning.py tests/test_static_versions.py -q --tb=short -rs 2>&1 | tail -20`. Fix only cleaning causes. Commit `0545 step 3` if anything changed.
4. **Screenshot** `/cleaning?lang=cs` at 1280 into `docs/tasks/screenshots-0545/cleaning-1280.png` (throwaway script in `/tmp`, copy from `test_v2_screenshots` in `test_0710`). Look at it next to the mockup screenshot and list any visible difference in the report. Commit `0545 step 4`.

## 5. Do not touch
Shared `app2.css` rules, the phone layout (a later brief), the shared view, JS. No new dependency, no migration.

## 6. Commands
In the steps (from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`), then from the repo root `python3 scripts/design_lint.py 2>&1 | tail -3`.

## 7. Acceptance
Cleaning cases at 768-1440 pass; step 3 second set passes (the known Overview "/" touch-sweep failure may remain; list it); lint OK; screenshot exists.

## 8. Stop and ask
Stop if a fix needs a shared rule or a file outside section 3.

## 9. Report
`docs/tasks/0545-report.md` (required): Status, tails, visible differences left, deviations.
