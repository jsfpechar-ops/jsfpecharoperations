# 0542: Cleaning page on the v2 shell (mockup HTML and app2.css)
Status: todo
Depends on: 0540, 0541, 0705-0709 (v2 shell, merged into this branch) | Branch: claude/project-thread-c1h7ok
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
The host cleaning page (`/cleaning`) renders on the v2 shell, like the Overview does: `{% set v2 = true %}`, so only `tokens.css` + `app2.css` load and the mockup's own classes (`.head`, `.sub`, `.btn`, `.card`, `.pill`) style it. Markup follows `docs/design/mockup/ubyhost-redesign-v2.html`, `<section class="view" data-v="clean">` (lines 204-215). The cleaner's shared page (`cleaning_shared.html`) is not touched.

## 2. Context
- Pattern to copy: `App/app/templates/dashboard.html` lines 1-13 (v2 flag, empty header blocks) and its `.head` block and Today table (lines ~51-130): `<div class="head"><div><h1>..</h1><p class="sub">..</p></div>BUTTON</div>`, then `<h2>` and `<div class="card"><table><thead>..</thead><tbody>..</tbody></table></div>`, pills as `<span class="pill p-ok|p-warn|p-bad">`.
- `App/app/templates/base.html`: on v2 pages it loads only `tokens.css` and `app2.css`; `cleaning.css` and `host*.css` are NOT loaded. The calendar include brings its own `dashboard-calendar.css`.
- Current cleaning templates: `cleaning.html` (header blocks), `_cleaning_screen.html`, `_cleaning_table.html` (host tables, 0540), `_cleaning_calendar.html` (legend + calendar, 0541). `_cleaning_screen.html` and `_cleaning_calendar.html` are shared with the cleaner page (`read_only=True`); the host branch is `not read_only`.

## 3. Files
Edit `App/app/templates/cleaning.html`, `App/app/templates/_cleaning_table.html`, `App/app/static/app2.css` (one block at the end, plus its `?v=` key in `base.html` and `App/tests/static_versions.json` via `--write`), host-page assertions in existing tests under section 8. Report `docs/tasks/0542-report.md`.

## 4. Steps
1. **v2 header.** In `cleaning.html` add `{% set v2 = true %}` after `extends`, make `page_title`, `meta`, `primary_action`, `secondary_actions` blocks empty, and start `{% block body %}` with `<div class="head"><div><h1>{{ ct('title') }}</h1><p class="sub">{{ ct('subtitle') }}</p><p class="ov-links"><a class="ov-link" href="/cleaning/new" data-calendar-add data-cal-create-type="cleaning">+ {{ ct('add') }}</a><span aria-hidden="true"> · </span><a class="ov-link" href="/cleaning/properties">{{ ct('settings') }}</a></p></div><a class="btn" href="/cleaning/shares">{{ ct('share_cleaner') }}</a></div>`, then the existing `cleaning-page` div. Commit `0542 step 1`.
2. **v2 tables.** In `_cleaning_table.html` keep the sections, ids, `data-href`, `clickable-row`, `role="link"` and the Open cue cell, but: drop `ui-table-wrap`, `ui_table_begin/ui_table_end` and `ui_badge`; write `<h2 id="cleaning-section-{{ key }}">` then `<div class="card"><table><thead><tr><th>..</th>..</tr></thead><tbody>..</tbody></table></div>` (5 columns: property, time/day, next arrival, status, empty), drop the `data-card` attributes and `ui-row`/`ui-cell-first` classes. Status pill: `conflict` -> `<span class="pill p-bad">{{ ct('status_conflict') }}</span>`; `timingUnavailable` -> `p-bad` `status_hours`; else `p-warn` `status_scheduled` (the mockup shows "Naplánováno" in amber). Last cell: `<td class="dots">{{ row_open(...) }}</td>`. The `today_empty` paragraph becomes `<div class="card"><table><tbody><tr><td>{{ ct('today_empty') }}</td></tr></tbody></table></div>`. Remove now-unused imports. Commit `0542 step 2`.
3. **Page CSS.** At the end of `app2.css` add one block `/* cleaning (0542) */`. For every class still rendered on the host `/cleaning` page that has no rule in `app2.css` (check: `cleaning-page`, `cleaning-list`, `cleaning-list-error`, `cleaning-notice`, `cleaning-empty`, `cleaning-legend`, `cleaning-legend-booking`, `cleaning-legend-event`, `cleaning-skip`, `row-open`, `row-open-text`, `visually-hidden`), copy its rule from `cleaning.css` / `host.css` / `components.css`, scoped under `body.v2`, using `app2.css` tokens (`var(--ink)`, `var(--ink3)`, `var(--line)`, `var(--acc)`; `grep -n -- '--' App/app/static/app2.css | head -20`). Add `body.v2 .cleaning-section{margin-bottom:28px}` (mockup gap between tables). No raw hex colours. Bump the `app2.css?v=` key in `base.html`, run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -3`. Commit `0542 step 3`.
4. **Tests.** Run section 6. Update only host `/cleaning` assertions that look for `ui-btn-primary`, `ui-table`, `ui-badge`, `data-card`, `host.css`/`cleaning.css` being loaded, or the old header blocks; point them at `.head .btn`, `.card table`, `.pill`. Never change shared-view assertions. Commit `0542 step 4`.

## 5. Do not touch
`cleaning_shared.html`, `_cleaning_list.html`, `_cleaning_screen.html`, `_cleaning_calendar.html`, `_dashboard_calendar.html`, `dashboard.html`, `_shell_v2.html`, any JS, routes, other pages' CSS rules in `app2.css`. No new dependency, no migration.

## 6. Commands (from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`.venv/bin/python -m pytest tests/test_0540_cleaning_tables.py tests/test_0541_cleaning_header.py tests/test_cleaning.py tests/test_design_cleaning.py tests/test_host_language.py tests/test_static_versions.py tests/test_no_em_dashes.py -q --tb=short 2>&1 | tail -30`, then `.venv/bin/python -m pytest tests/test_cleaning_browser.py tests/test_design_guardrails_browser.py tests/test_0252_touch_sweep_browser.py tests/test_dashboard_calendar_browser.py -q --tb=short -rs 2>&1 | tail -30`, then from the repo root `python3 scripts/design_lint.py 2>&1 | tail -5; python3 scripts/context_lint.py 2>&1 | tail -5`.

## 7. Acceptance
All pass, 0 skipped. `git diff --stat HEAD~4` lists only section 3 files.

## 8. Stop and ask
Assertions in step 4 may be updated; list each. Stop if a shared-view test fails, if the calendar drag test fails, or if `design_lint` asks for catalog entries you cannot place (report them).

## 9. Report
`docs/tasks/0542-report.md`: Status, test and lint tails, diff stat, assertions changed, deviations.
