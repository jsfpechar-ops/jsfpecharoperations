# 0703: finish the Overview look: warm canvas behind cards, calm headings, date in words, account card at the top
Status: todo
Depends on: 0700-0702 (on this branch) | Base commit: claude/project-thread-50hyv5 | Branch: task/0703-look-finish
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Close the last four visible gaps between `/` and the approved mockup (`/mnt/project-files/ux-redesign/overview/mockup-overview-1280.png`; current page `/mnt/project-files/ux-redesign/overview/overview-new-look-1280.png`). Computer width (>= 768 px) only, except item 3 which is copy.

## 2. Context (the four items)
1. **Canvas.** At 1280 px the area behind the cards is still white although `main#main-content` computes `#f6f6f4`. Find the element(s) painting white between `body` and the cards (Playwright: walk up from `.needs-you` and print each ancestor's computed `background-color` until `body`). Make those ancestors transparent with a rule in the `/* 0700 shared look (mockup v2) */` block at the end of `App/app/static/host2.css` (inside its `@media (min-width:768px)`), so the canvas shows. Cards (`.needs-you-item`, the calendar card, the table wrapper, `.ui-card`) stay white. The sidebar stays white.
2. **Headings.** Section headings in the main column are 16px/700, line-height 1.3: at least `.needs-you > h2`, `#dashboard-today-title`, `.cal-heading h2` (check real selector), `.ui-section-h` / section `h2` generally. Add to the same 0700 block (use rem: 1rem). The page title stays 24px/800.
3. **Date in words.** The header meta on `/` shows `01.11.2026`; make it e.g. cs "neděle 1. listopadu", en "Sunday 1 November", vi "Chủ nhật, 1 tháng 11". Add a Jinja filter `date_long` in `App/app/templating.py` next to `date_cz` (signature `date_long(value, lang)`), with weekday and month tables in that file (cs genitive months: copy `_CS_MONTHS` from `App/app/acceptance.py`, do not import it; cs weekdays lowercase: pondělí úterý středa čtvrtek pátek sobota neděle; vi weekdays: Thứ hai, Thứ ba, Thứ tư, Thứ năm, Thứ sáu, Thứ bảy, Chủ nhật; other languages fall back to English). In `dashboard.html` `{% block meta %}` use `today.isoformat() | date_long(lang)` instead of `date_cz` (keep the last-sync part). Only the dashboard uses it.
4. **Account card at the top of the sidebar.** In `App/app/templates/_shell_sidebar.html` move the `<details class="host-account" data-host-account>...</details>` block from `.host-rail-bottom` to just after the search trigger near the top (find it: `grep -n 'search\|Hledat\|command' App/app/templates/_shell_sidebar.html`). Style it at all widths >= 768 px as the mockup's card: background `var(--surface-2)`, radius 10px, padding 10px, name 14px/600, small line ink-3 11px; its menu opens below it. Keep every link and behaviour in the menu. Phone layout: check `test_dashboard_phone_browser.py` still passes; if the move breaks the phone drawer, stop.

## 3. Files
`App/app/static/host2.css` (0700 block only), `App/app/templating.py` (filter only), `App/app/templates/dashboard.html` (meta block only), `App/app/templates/_shell_sidebar.html`, `?v=` key of host2.css in `base.html` (`20261101-0703`), `App/tests/static_versions.json` (via `--write`), `docs/design/catalog.json` if a class is added. Create `App/tests/test_0703_look_finish.py` (filter unit tests: cs/en/vi for 2026-11-01) and `App/tests/test_0703_look_finish_browser.py` (at 1280 px on `/`: the computed background of the nearest non-transparent ancestor of `.needs-you` is rgb(246, 246, 244); `.needs-you > h2` font-size 16px; `.host-account` top is above the first nav link). Screenshots `docs/tasks/screenshots-0703/` (`/?lang=cs` at 1280 and 390 px: run `UBYHOST_SHOTS_0701=docs/tasks/screenshots-0703 .venv/bin/python -m pytest tests/test_0701_overview_cards_browser.py` from App/ with an absolute path). Report `docs/tasks/0703-report.md`.

## 4. Steps
One commit per item (`0703 item N`), then tests + screenshots + report commit. `python3 scripts/design_lint.py` before each CSS/template commit.

## 5. Do not touch
JS, routes, other templates, phone styles (< 768 px), other CSS files.

## 6. Commands (from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`.venv/bin/python -m pytest tests/test_0703_look_finish.py tests/test_0703_look_finish_browser.py tests/test_0700_shared_look_browser.py tests/test_0701_overview_cards_browser.py tests/test_0702_overview_calendar_card_browser.py tests/test_design_guardrails_browser.py tests/test_dashboard_phone_browser.py tests/test_host_quiet_dashboard_browser.py tests/test_design_dashboard.py tests/test_static_versions.py -q --tb=short -x -rs 2>&1 | tail -30`, then every `tests/test_*sidebar*.py` and `tests/test_*account*browser*.py` that exists, then `python3 scripts/design_lint.py | tail -3` and `python3 scripts/context_lint.py 2>&1 | tail -3` from the repo root.

## 7. Acceptance
All pass, 0 skipped; diff only section 3 files plus assertions updated under section 8.

## 8. Stop and ask
Existing assertions on the account block's position (bottom of the rail) or old heading sizes at >= 768 px may be updated; list each. Stop if a phone test changes result.

## 9. Report
`docs/tasks/0703-report.md`: Status, tails, diff stat, screenshots, updated assertions, deviations.
