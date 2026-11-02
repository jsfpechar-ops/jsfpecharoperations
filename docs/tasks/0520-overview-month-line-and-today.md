# 0520: Overview redesign, part 1: one primary button, a quiet month line, a "Today" table
Status: todo
Depends on: 0496 shell (merged) | Base commit: origin/main | Branch: task/0520-overview-today
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Make the Overview page (`/`) follow the approved computer mockup (`ubyhost-redesign-v2.html`, view "today"), owner approved 2026-11-01: page order is "What needs you", then one quiet line of month numbers, then the calendar, then a "Today" table of arrivals and departures. One primary button in the header. No money figures anywhere.

## 2. Context
- Template `App/app/templates/dashboard.html`; route `dashboard()` in `App/app/routes/admin.py` (around line 438). The "What needs you" section and the calendar include stay as they are and in that order.
- The macro `dashboard_rows(items, empty_key)` in `dashboard.html` already draws stay rows (dates, property, guests, status badge, row menu). Today it is used only inside `<noscript>`. Reuse it for the Today table; leave the `<noscript>` block alone.
- Count queries to copy the style of: `App/app/welcome_back.py` lines 55-68 (owner scope with `db.null_safe_eq("a.owner_user_id")`, demo stays excluded, sent guests via `reporting.SENT` and `g.submitted_at`). SQL only through `App/app/db.py` helpers and Postgres-portable: no SQLite date functions; do date arithmetic in Python.
- Translations: English and Czech in `App/app/host_i18n.py`, Vietnamese in `App/app/host_vi_i18n.py`. Plural keys use `tp()` with `.one` and `.few` variants: copy the shape of `welcome_back.stays` in each language.
- Dashboard CSS lives in `App/app/static/workflow.css` (find `.needs-you`).

## 3. Files
Edit `App/app/templates/dashboard.html`, `App/app/routes/admin.py` (dashboard function only), `App/app/reporting.py` (one new function), `App/app/host_i18n.py`, `App/app/host_vi_i18n.py`, `App/app/static/workflow.css` (plus its `?v=` key where it is linked, and `App/tests/static_versions.json` only via `--write`). Create `App/tests/test_0520_overview_today.py`. Screenshots in `docs/tasks/screenshots-0520/`. Report `docs/tasks/0520-report.md`.

## 4. Steps
1. **Header.** In `dashboard.html` keep the title, the date meta and the "+ Add stay" primary button. Remove the secondary "+ Add cleaning" button, the "more actions" icon button (`data-toggle-panel="dashboard-more"`) and the `#dashboard-more` panel div in the body. Keep the demo "clear" form. Commit `0520 step 1`.
2. **Month numbers.** Add `month_summary(owner_user_id, today)` to `reporting.py`, returning `{"guests": int, "nights": int, "reported": int}` for the calendar month of `today`, non-demo stays of the owner's non-archived properties:
   - `guests`: guest rows on stays whose `date_from` is in the month.
   - `nights`: sum of `(date_to - date_from).days` for those stays (fetch the two dates, add in Python).
   - `reported`: guests with `submit_state = reporting.SENT` and `submitted_at` in the month.
   Three queries at most. Pass it to the template as `month_summary`. Commit `0520 step 2`.
3. **Quiet line.** Directly after the closing `</section>` of "What needs you" (inside the same refresh div), add one line: `<p class="dashboard-quiet" data-dashboard-month>` with label `dashboard.month.label` then `dashboard.month.guests`, `dashboard.month.nights`, `dashboard.month.reported` (all `tp` with the number in `<b>`), joined by a `·` in `<i aria-hidden="true">`. Copy: en "This month" / "%(count)s guests" / "%(count)s nights" / "%(count)s reported to the police"; cs "Tento měsíc" / "%(count)s hostů" / "%(count)s nocí" / "%(count)s nahlášeno policii" (.one: "1 host", "1 noc", "1 nahlášen policii"; .few: "%(count)s hosté", "%(count)s noci", "%(count)s nahlášeni policii"); vi "Tháng này" / "%(count)s khách" / "%(count)s đêm" / "%(count)s đã khai báo công an" (same text for all forms). Template prints the number in `<b>` and the rest as text: split the key as `<b>N</b> word` by making the keys word-only if simpler (for example `dashboard.month.guests` = "guests"/"hostů"), as long as plural forms stay right. CSS in `workflow.css`: `.dashboard-quiet{color:var(--ink-3, #6b7280);font-size:14px;margin:4px 0 24px;display:flex;flex-wrap:wrap;gap:8px;align-items:baseline}` `.dashboard-quiet b{color:var(--ink-1, #111827);font-size:15px;font-weight:700}` `.dashboard-quiet i{font-style:normal}` (use the real token names: `grep -n -- '--ink' App/app/static/*.css | head`). Commit `0520 step 3`.
4. **Today table.** After the calendar include, before the `data-dashboard-refresh="work"` div, add `<section class="dashboard-today" aria-labelledby="dashboard-today-title"><h2 id="dashboard-today-title">{{ t('dashboard.today.title') }}</h2> ... </section>` holding `dashboard_rows(today_rows, 'dashboard.today.empty')` where `today_rows` (set in the template) is the `rows` whose `reservation.date_from` or `reservation.date_to` equals `today` (compare as ISO strings: check the type with a quick print if unsure). Give the macro a third parameter `caption_key='dashboard.section.needs_action'` used for the table caption, and pass `'dashboard.today.title'` here (keep the `count=` argument only when the key takes it). Under the dates in the first cell, for today rows show `t('calendar.arrival')` when `date_from == today`, else `t('calendar.departure')`, in the existing `ui-sub` span when that span is empty. Copy: `dashboard.today.title` en "Today", cs "Dnes", vi "Hôm nay"; `dashboard.today.empty` en "No arrivals or departures today.", cs "Dnes nikdo nepřijíždí ani neodjíždí.", vi "Hôm nay không có khách đến hoặc đi.". Commit `0520 step 4`.
5. **Test** `test_0520_overview_today.py` (copy fixtures and login from `tests/test_dashboard_order.py`): (a) `/` shows the month line with the right three numbers for a seeded stay arriving this month with two guests, one sent, 3 nights; (b) the Today table lists a stay arriving today and one departing today, and not a stay arriving tomorrow; (c) order in the HTML: needs-you section, `data-dashboard-month`, `id="calendar"`, `dashboard-today`; (d) no "Add cleaning" button and no `dashboard-more` in the page; (e) `month_summary` ignores demo stays and other owners' stays. Commit `0520 step 5`.
6. Bump the `workflow.css?v=` key, run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`. Screenshots of `/?lang=cs` at 1280 px and 390 px into `docs/tasks/screenshots-0520/` (see executor.md, Screenshots). Commit `0520 step 6`.

## 5. Do not touch
The "What needs you" content and logic, `_dashboard_calendar.html`, any JS file, other templates, other routes, the `<noscript>` block, the welcome-back banner and onboarding parts. No new dependency, no migration.

## 6. Commands (from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`.venv/bin/python -m pytest tests/test_0520_overview_today.py tests/test_dashboard_order.py tests/test_dashboard_queue.py tests/test_dashboard_queue_copy.py tests/test_dashboard_empty.py tests/test_dashboard_missing_banner.py tests/test_design_dashboard.py tests/test_host_quiet_dashboard.py tests/test_needs_you_0240.py tests/test_needs_you_dashboard_0241.py tests/test_0375_needs_you_and_open.py tests/test_overview_headcount.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`, then the browser set `tests/test_dashboard_rows_browser.py tests/test_dashboard_phone_browser.py tests/test_host_quiet_dashboard_browser.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30`, then from the repo root `python3 scripts/context_lint.py 2>&1 | tail -10`.

## 7. Acceptance
All pass, 0 skipped. `git diff --stat origin/main` lists only section 3 files, plus test files changed under section 8.

## 8. Stop and ask
If an existing test asserts the removed header buttons, update only that assertion and list it in the report. Stop if any other existing test changes result, or if `rows` does not hold stays that depart today (then report which rows it holds).

## 9. Report
`docs/tasks/0520-report.md`: Status, test and lint tails, `git diff --stat origin/main`, screenshot paths, deviations.
