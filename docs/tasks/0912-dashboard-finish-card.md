# 0912: Dashboard finish card in v2, honest month line, lint for overlapping buttons

Status: todo. Executor: Haiku 5.5, two runs (steps 1-5, then 6-9).
Read first: AGENTS.md, docs/context/executor.md, docs/design/MASTER.md `### 7.12` (help tip) only.

## 1. Objective
1. The "You are ready / Guest link and PIN are live" card on the v2 dashboard (and on /onboarding) gets real v2 styling: no bullet list, no fine print, buttons that never wrap or overlap.
2. The line "This month N guests · N nights · N reported" counts all three numbers on one basis, so "reported" can never be bigger than "guests".
3. The layout lint fails on overlapping buttons, wrapped button labels and buttons closer than 12 px in one row, at every width.

## 2. Context (verified by the orchestrator)
- v2 pages load only `tokens.css`, `app2.css`, `command.css` (`App/app/templates/base.html` lines 20-23). The `onboarding-finish*` rules live only in `app.css` and `host.css`, so on v2 the card is unstyled. New rules go in `App/app/static/app2.css` only. Do not edit app.css, host.css, host2.css.
- Macro `onboarding_finish` is in `App/app/templates/_components.html` (anchor `{% macro onboarding_finish(onboarding, show_toggle=True) %}`, about line 332); `onboarding_finish_strip` follows it. `dashboard.html` line 96 wraps the card in `ph-hide`, which hides it below 1024 px.
- `reporting.month_summary` (`App/app/reporting.py`, anchor `def month_summary(`) counts stays by arrival date but "reported" by `submitted_at`, so a stay that arrived on 31 Oct shows 0 guests next to 2 reported in November.
- Tests that pin the card: `test_onboarding.py` 248/259 and `test_dashboard_order.py` 132-155 look for `class="onboarding-finish"` (keep that exact attribute value first in the class list); `test_wp28_ui_sweep.py` 126 expects exactly one `>Skip setup guidance<` and the text "Share the guest link above with your guests." on /onboarding.

## 3. Files
Edit: `App/app/templates/_components.html` (the two finish macros only), `App/app/templates/dashboard.html` (line 96 only), `App/app/static/app2.css` (append at the end), `App/app/templates/base.html` (app2.css cache key only), `App/app/reporting.py` (`month_summary` only), `App/tests/test_0520_overview_today.py`, `App/tests/layout_lint.js`, `App/tests/test_layout_lint_browser.py`, `docs/design/pages/dashboard.md`.
Read only (for copying seed code): `App/tests/test_host_wide_geometry_browser.py` lines 79-160, `App/tests/test_dashboard_order.py` lines 40-95.
Create: `docs/tasks/0912-report.md`, folder `/mnt/project-files/dashboard-finish/`.
No new i18n keys, no key removed, `App/app/host_i18n.py` not touched.

## 4. Steps

### Run 1 (card, CSS, month line)
1. **Macro.** Rewrite the body of `onboarding_finish` (keep its signature, its outer `{% if %}` and the dismiss/resume form logic):
   - `<section class="onboarding-finish" data-layout="v2" aria-label=...>`.
   - Header: kicker `<p class="onboarding-kicker">` unchanged; then `<div class="onboarding-finish-title"><h2>{{ t('onboarding.finish_title') }}</h2>{{ help_tip('onboarding-finish-help', tips) }}</div>`; then the lede `<p class="lede">` unchanged.
   - Before the header build the help text: `{% set tips %}{{ t('onboarding.finish_message_tip') }} {{ t('onboarding.finish_passport_tip') }} {{ t('apartment.form.passport_policy.' ~ ('required' if finish.passport_policy == 'required_foreign' else 'off')) }}. {{ t('onboarding.finish_reopen_tip') }}{% endset %}`. Delete the whole `<ul class="onboarding-finish-tips">` list (its two links both went to the communication page, which the primary button already opens).
   - Share block: keep both `onboarding-finish-field` rows and their ids/copy buttons exactly as they are.
   - Actions: `<div class="onboarding-finish-actions">` with `<a class="ui-btn ui-btn-primary" ...>` (communication), `<a class="ui-btn ui-btn-secondary" ... target="_blank" rel="noopener">` (preview), and the Skip/Resume buttons as `<button class="ui-btn ui-btn-quiet" type="submit">`. Same hrefs, same keys.
   - `onboarding_finish_strip`: leave the markup; it gets CSS in step 3.
2. **Dashboard.** In `dashboard.html` line 96 remove `ph-hide` from the wrapper class (keep `cal-hide`), so the host sees link and PIN on the phone too. Do not change line 95 or line 98.
3. **CSS.** Append one block to `app2.css`, starting with the comment `/* 0912: finish card (v2) */`. Tokens only (`var(--s)`, `var(--line)`, `var(--ink)`, `var(--ink2)`, `var(--ink3)`, `var(--acc)`, `var(--oks)`, `var(--ok)`), no hex colours, light mode only. Selectors start `body.v2 .onboarding-finish`:
   - card: surface, 1 px `--line` border, radius 12, padding 20 (16 below 768), `display:grid; gap:16px`, margin 16 0.
   - kicker: 12 px, 600, `--ok`, margin 0. Title row: `display:flex; align-items:center; gap:8px`; h2 18/700 margin 0. Lede: 14 px `--ink2`, margin 0.
   - share: `display:grid; gap:12px`. Each field: `display:flex; align-items:center; gap:12px; flex-wrap:wrap; padding:12px; border:1px solid var(--line); border-radius:12px`. Label: 13 px `--ink3`, `flex:0 0 64px`. `code`: `flex:1 1 200px; min-width:0; overflow-wrap:anywhere; font-size:14px`. PIN: 18 px, 700, letter-spacing .08em, `flex:1 1 auto`. Copy button: `flex:none; margin-left:auto`.
   - actions: `display:flex; flex-wrap:wrap; align-items:center; gap:12px`; `.ui-btn` and `form` inside: `white-space:nowrap; flex:none`; forms inside get `margin:0` (never `display:contents`).
   - below 768 px: actions `flex-direction:column; align-items:stretch`; every `.ui-btn` in it and the form button `width:100%; justify-content:center; min-height:44px`; the quiet Skip button centred.
   - strip `body.v2 .onboarding-finish-strip`: `display:flex; flex-wrap:wrap; gap:12px; align-items:center; padding:12px 16px; border:1px solid var(--line); border-radius:12px; background:var(--s); font-size:14px; margin:12px 0`; its link `white-space:nowrap; min-height:44px; display:inline-flex; align-items:center` below 1024.
   Then in `base.html` change only `app2.css?v=0903b` to `app2.css?v=0912`.
   Run: `cd App && .venv/bin/python -m pytest tests/test_onboarding.py tests/test_dashboard_order.py tests/test_wp28_ui_sweep.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`. Commit `0912 step 1-3`.
4. **Month line.** Replace the query and loop in `month_summary` with one query over stays that overlap the month (`r.date_from < end AND r.date_to > start`), each row giving `date_from`, `date_to`, guest count `n` and sent count `sent` as two correlated subqueries (`(SELECT COUNT(*) FROM guest g WHERE g.reservation_id = r.id AND g.submit_state = ?) AS sent`). Params in placeholder order: `(SENT, owner_user_id, end.isoformat(), start.isoformat())`. In Python: `guests += n`, `reported += sent`, nights clipped to the month: `max(0, (min(leave, end) - max(arrive, start)).days)`. Keep the `owned` string, the demo and archived filters and the date parsing. Update the docstring: "stays that overlap the month; reported = their guests with submit_state SENT".
5. **Test.** In `test_0520_overview_today.py` keep the existing test green and add `test_month_summary_counts_reports_on_the_same_stays`: a stay from the last day of last month for 3 nights with two guests in `reporting.SENT` gives `guests == 2`, `reported == 2`, `nights == 2`; a stay that ended last month is not counted. Run: `cd App && .venv/bin/python -m pytest tests/test_0520_overview_today.py tests/test_dashboard_order.py -q --tb=short -x 2>&1 | tail -30`. Commit `0912 step 4-5`.

### Run 2 (lint, screenshots, docs)
6. **Lint rules.** In `layout_lint.js`, insert before the final `return out;` a new section `// 11. Action rows at every width: buttons that overlap, wrap, or sit closer than 12 px.` Controls: `button, a.btn, a.ui-btn, .btn, .ui-btn, input[type=submit]`, visible, not `skipZone`, not `.help-tip-btn`, not `position:fixed`, using the same exclusion list as section 10b. Row key: the control's parent, or the parent's parent when the parent is a `FORM`. For two controls with the same row key (neither contains the other): `button-overlap` when the rects intersect by more than 1 px on both axes; `tight-row` when they share a line (vertical overlap > 8) and the horizontal gap is between -1 and 12 px. For each control in a row of 2 or more: `button-wraps` when its label has 2 or more words and `textLines(el) >= 2`. Do not change sections 1-10.
7. **Lint tests.** In `test_layout_lint_browser.py`:
   - Add to `BAD_PAGE` (before `</body>`) one row `<div id=row style="display:flex;width:300px"><a class=btn style="width:200px;white-space:nowrap">Open communication settings</a><a class=btn style="margin-left:-60px;width:160px">Skip setup guidance now</a></div>` plus `<div style="display:flex;gap:4px"><button>One</button><button>Two</button></div>`, and add `"button-overlap", "button-wraps", "tight-row"` to `expected`.
   - Add `test_the_finish_card_passes_the_lint(wide_base)`: a fresh host made the way `wide_host` does it (copy account creation and login cookie lines from `test_host_wide_geometry_browser.py` 79-160), one entity and one property with the fields from `test_dashboard_order.py` `_ready_workspace`, and one stay +10 days. For widths 390, 768, 1280: open `/?lang=en`, assert `section.onboarding-finish` is visible, run `LINT`, collect findings, save `full_page` screenshots to `/mnt/project-files/dashboard-finish/finish-{width}.png`. Then add a stay from -5 days (overdue), reload, assert `.onboarding-finish-strip` is visible, lint and save `strip-{width}.png`. Assert no findings, printing them on failure. Same browser launch and skip guard as the other tests.
   Run: `cd App && UBYHOST_BROWSER_EXECUTABLE=/opt/pw-browsers/chromium UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q --tb=short -x -rs 2>&1 | tail -30`. Commit `0912 step 6-7`.
8. **Rows.** Run, each ending `-q --tb=short -x -rs 2>&1 | tail -30`, with the browser env vars from step 7: host pages row `tests/test_host_*.py tests/test_host_geometry.py`; onboarding row `tests/test_onboarding*.py tests/test_property_*.py tests/test_first_*.py`; `tests/test_design_guardrails_browser.py`; `tests/test_0710_v2_mockup_match_browser.py`; static row `tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py`; `tests/test_wp28_ui_sweep.py tests/test_0520_overview_today.py`. Then `python3 scripts/context_lint.py | tail -20` from the repo root.
9. **Docs and report.** Add to `docs/design/pages/dashboard.md` (3 lines at most, no px, no colours): finish card = link row, PIN row, one primary, one secondary, quiet Skip; tips behind the "?"; month line counts stays that overlap the month. Write the report (section 9), commit `0912 step 8-9`, open a draft PR from branch `task/0912-dashboard-finish-card`.

## 5. Do not touch
app.css, host.css, host2.css, components.css, `host_i18n.py`, `_ui.html`, routes, migrations, the `next_action` and calendar markup, lint sections 1-10, `ALLOW` (never add an entry).

## 6. Commands
Only the commands written in steps 3, 5, 7 and 8.

## 7. Acceptance
- [ ] At 1280 the card shows link and PIN as two bordered rows with Copy at the right, three actions on one line with at least 12 px between them, no bullet list, no tips text visible until "?" is opened.
- [ ] At 390 and 768 the card shows (no `ph-hide`), actions stacked full width, nothing wraps or overlaps.
- [ ] Strip variant styled as one row with its link.
- [ ] `month_summary` is one query; reported is never above guests; new test green.
- [ ] Lint flags `button-overlap`, `button-wraps`, `tight-row` on the fixture; the finish-card test and the full layout lint are green, 0 skipped.
- [ ] Six PNGs in `/mnt/project-files/dashboard-finish/` (finish and strip at 390/768/1280), each opened once.
- [ ] All step 8 rows green, 0 skipped; `">Skip setup guidance<"` still once on /onboarding.

## 8. Stop and ask
An anchor is not where this brief says; `section.onboarding-finish` is not visible for the fresh host; or the new lint rules flag a page other than the dashboard in `test_every_host_page_passes_the_layout_lint`. In the last case do not fix or allow-list it: commit what you have, list each route/width/finding in the report, `Status: blocked`.

## 9. Report
`docs/tasks/0912-report.md`, 600 tokens at most: files changed; each command with its last 5 lines; section 7 ticked; per screenshot one line "finish-390: ..." of what you saw (gaps, wrapping, overlap); Deviations; Questions; owner steps.

## 10. Owner steps
After merge and deploy: open the dashboard once on the phone and on the laptop, check the card and the month line. Nothing else.
