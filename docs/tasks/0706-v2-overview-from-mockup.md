# 0706: Overview rebuilt from the mockup HTML on the v2 shell
Status: todo
Depends on: 0705 | Base commit: task/0705-v2-shell | Branch: task/0706-v2-overview
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
`/` renders the mockup's "today" view (`<section class="view on" data-v="today">` in `/mnt/project-files/ux-redesign/ubyhost-redesign-v2.html`, lines ~121-143) with real data, markup copied 1:1, on the v2 shell (`{% set v2 = true %}`). Owner decision 14:33: extras the mockup lacks stay but as small quiet links ("Jak to funguje?" help, month calendar, add cleaning, clear demo data).

## 2. Context
- Current template `App/app/templates/dashboard.html`, route `dashboard()` in `App/app/routes/admin.py` (~line 438). Keep the route's data; add only what is listed below.
- Mockup blocks and their data:
  1. `.note` (yellow): show only when the account is in practice/test mode; reuse the condition and text of the existing practice/test banner (find it: `grep -rn 'ubyport_env\|practice\|Policii se nic' App/app/templates/*.html | head`). Link text and href from that banner.
  2. `.head`: `<h1>` = `t('dashboard.title')` ("Přehled"), `.sub` = `today.isoformat() | date_long(lang)`, button `.btn` "Přidat pobyt" → `/reservations?new=1` (keep `data-calendar-add data-cal-create-type="stay"`). Quiet links under the sub line (13px ink-3, inline, separated by " · "): "Jak to funguje?" → `/guide` (or the existing how-key target), "+ Úklid" → `/cleaning/new`, and when `demo_loaded` the existing demo-clear form as a link-styled button.
  3. `<h2>Potřebuje vás</h2>` + `.todo` grid: one `.card` per line of `needs_you.lines` (built exactly as now with `needs_you_build(...)` and the onboarding-banner filter). Card = `.ic` tile (red tone: `background:var(--bads);color:var(--bad)` with "!"; amber: warns/warn with "!"; grey: `#efefeb`/ink2 with "i"), `.t` = `line.subject`, `<p>` = `line.text`, button `.btn.sm` (first card) or `.btn.sm.ghost` (others) = `line.action` → `line.href`; dismiss form if `line.dismiss_id` as a small "×" link-button; the paste how-to `<details>` kept inside the card. More than 4 lines: show 4, rest in a `<details>` "+N dalších". No lines: one `.card` with "Dnes na vás nic nečeká." (`t('needs_you.calm')`). Keep `data-needs-you`, `data-needs-you-stay`, `data-needs-you-go` attributes on the same elements as now so JS and tests still find them.
  4. `.quiet` month line from `month_summary` (keys `dashboard.month.*` exist).
  5. `<h2>Kalendář</h2>` (`t('calendar.calendar')`) + `.card.cal` 14-day grid rendered SERVER-SIDE: in the route compute `cal_days` (14 dates from today) and `cal_rows` = for each active apartment, its stays from `dashboard_calendar.events(owner_user_id, today, today + 14 days)` (import from `app.routes.dashboard_calendar`) with `col_start = 2 + max(0, (start - today).days)`, `col_end = 2 + min(14, (end - today).days)` (skip if col_end <= col_start), class by tone: done → `b-ok`, action/ready/overdue → `b-warn` (overdue → `b-warn` plus inline `background:var(--bads);color:var(--bad)`), neutral → `b-grey`; label = guest label (`event.label` or property-source name like "Airbnb"/"Booking" from `source`), each bar an `<a href="{{ event.url }}">`. Header row: `.cd` per day with weekday short + day number (cs: Po Út St Čt Pá So Ne), first `.cd.today`. Max query budget: `tests/test_query_budget.py` allows "/" < 21; `events()` must replace queries, not add: remove the old JS calendar from `/` (see 7) so its queries/fetch go away; if the budget still fails, raise it by exactly the queries `events()` adds and say so. Under the card a quiet link "Celý kalendář →" to `/?cal_view=calendar`; when that query parameter is present, render the old `{% include "_dashboard_calendar.html" %}` below the card and load `dashboard-calendar.css` via `{% block head_extra %}` (find its link tag in `_dashboard_calendar.html` or base).
  6. `<h2>Dnes</h2>` + `.card` table exactly like the mockup (columns Host / Nemovitost / Termín / Stav / ···) from `today_rows` (existing): Host = stay label + `<small>` guest count; Termín = "Příjezd · N noci" / "Odjezd"; Stav = `.pill` `p-ok` "Hotovo, nahlášeno policii" when status reported/not_required, `p-warn` with `tp('host.missing', n)` when guests missing, `p-bad` when failed/overdue (reuse existing status words; no new copy unless missing, then add en/cs/vi keys). Row → `/reservations/{id}?return_to=/`. Empty: one row "Dnes nikdo nepřijíždí ani neodjíždí." (`dashboard.today.empty`).
  7. Drop from `/`: the old `host_page.html` header, `.needs-you` section markup, the old calendar include (unless `cal_view`), the `data-dashboard-refresh` wrappers, onboarding banner and welcome-back banner (keep `onboarding_welcome` for accounts with no apartments: when `not apartments`, render the existing welcome block inside `.main` as now).
- Many existing dashboard tests assert old markup. Rule: a test that asserts old markup/classes of `/` at any width may be updated to the new markup when the same information is still on the page; a test asserting information that is no longer on `/` (e.g. old header buttons) is updated to its new place (quiet links) or removed only if the brief above removes that information. List every test change in the report. Stop if more than 12 test functions need changes; report the list.

## 3. Files
`App/app/templates/dashboard.html` (rewrite), `App/app/routes/admin.py` (dashboard only: `cal_days`, `cal_rows`), `App/app/static/app2.css` (only additions needed by real data, e.g. dismiss button, details), i18n files for any new key, failing dashboard tests under the rule above, `App/tests/test_query_budget.py` only as allowed above, `App/tests/static_versions.json`. Create `App/tests/test_0706_v2_overview_browser.py`. Screenshots `docs/tasks/screenshots-0706/`. Report `docs/tasks/0706-report.md`.

## 4. Steps
1. Route data + template rewrite (sections 1-4). Commit.
2. Calendar grid (5). Commit.
3. Dnes table (6) and drops (7). Commit.
4. Test: at 1280 px on `/` the page has `.side`, `.head h1`, `.todo .card` items side by side, `.quiet`, `.cal .cgrid` with 15 grid columns, `.cd.today`, Dnes table header Host/Nemovitost/Termín/Stav (cs); no element with class `ui-ph`; only `tokens.css` and `app2.css` stylesheets loaded (plus dashboard-calendar.css when `cal_view`). Commit.
5. Run the dashboard test set (section 6), apply the test-update rule, commit.
6. Side-by-side screenshots at 1280x1100: mockup (`file:///mnt/project-files/ux-redesign/ubyhost-redesign-v2.html`) and `/?lang=cs` with the rich fixture of `tests/test_host_quiet_dashboard_browser.py`, saved as `docs/tasks/screenshots-0706/mockup-1280.png` and `overview-1280.png`, plus `overview-390.png`. Commit.

## 5. Do not touch
needs-you logic, reporting, JS, other pages, old CSS files.

## 6. Commands (from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`.venv/bin/python -m pytest tests/test_0706_v2_overview_browser.py tests/test_0705_v2_shell_browser.py tests/test_dashboard_*.py tests/test_needs_you_*.py tests/test_0375_needs_you_and_open.py tests/test_0520_overview_today.py tests/test_overview_headcount.py tests/test_host_quiet_dashboard*.py tests/test_design_dashboard.py tests/test_query_budget.py tests/test_privacy_first.py tests/test_static_versions.py -q --tb=line -rs 2>&1 | tail -30`; `python3 scripts/design_lint.py | tail -2`; `python3 scripts/context_lint.py 2>&1 | tail -2`.

## 7. Acceptance
Listed tests pass, 0 skipped; screenshots taken.

## 8. Stop and ask
See the test rule in section 2. Stop if the needs-you data cannot fill the mockup card without logic changes.

## 9. Report
`docs/tasks/0706-report.md`: status, tails, every changed test with reason, query count, screenshots, deviations.
