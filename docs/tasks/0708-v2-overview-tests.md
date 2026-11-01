# 0708: dashboard tests follow the v2 Overview
Status: todo
Depends on: 0706 | Base commit: task/0706-v2-overview | Branch: task/0708-v2-tests
Executor: Haiku 5.5 | Fits one session: 30 tool calls

## 1. Objective
0706 rebuilt `/` from the mockup (owner decision 2026-11-01 14:33). 47 existing tests assert the old markup. Update them so they check the same information in the new markup, and add `tests/test_0706_v2_overview_browser.py`. Approved by the orchestrator: update all of them under the rules below.

## 2. Context
New `/` markup (see `App/app/templates/dashboard.html`): `.head h1`, `.sub`, quiet links, `.todo .card` needs-you items (keep `data-needs-you`, `data-needs-you-stay`, `data-needs-you-go`), `.quiet` month line, `.card.cal .cgrid` 14-day server-side grid (bars are `<a class="bar b-*">`), "Celý kalendář →" to `/?cal_view=calendar` which renders the old JS calendar include below, `Dnes` table. Old header buttons, `.needs-you` box, onboarding banner, welcome-back banner, noscript queue and refresh wrappers are gone from `/`.
Rules:
- Old markup/class assertions → same information in new markup.
- Old JS calendar tests (`test_dashboard_calendar_browser.py`, `test_dashboard_calendar.py`): open `/?cal_view=calendar` (append to the URL their `open_page`/fixtures use, keep their other params) instead of `/`; the calendar must behave as before there.
- Information removed from `/` by design (welcome-back banner, onboarding banner/finish card on `/`, add-cleaning header button → now the "+ Úklid" quiet link, demo-clear → quiet link): update to the new place; if the information is gone (welcome-back, onboarding banner on `/`), change the assertion to check it is NOT on `/` and add a one-line comment `# 0706: removed from Overview by the v2 rebuild`.
- `test_query_budget.py`: change `"/": 21` to `"/": 23` with comment `# +2 for the server-side 14-day calendar (0706)`. For `test_batched_pages_render_exactly_as_the_per_stay_path` on the dashboard: find what differs (print a diff of the two renders); if the difference comes from the calendar rows or today rows being built without the batched progress, fix the route to use the same rows (`App/app/routes/admin.py`, allowed for this only); report what it was.
- `test_0705_v2_shell_browser.py::test_non_v2_dashboard...`: point it at another non-v2 page (`/reservations`).
- Never delete a test function; never skip.

## 3. Files
The failing test files listed in `docs/tasks/0706` hand-back (run the set in section 6 to see them), `App/app/routes/admin.py` (batched-path fix only), new `App/tests/test_0706_v2_overview_browser.py` (1280 px: `.side`, `.head h1`, two `.todo .card` side by side, `.quiet`, `.cgrid` with 15 columns, `.cd.today`, Dnes header Host/Nemovitost/Termín/Stav in cs; only tokens.css + app2.css stylesheets unless `cal_view`). Report `docs/tasks/0708-report.md`.

## 4. Steps
Work file by file, commit after each file or two (`0708: <file> follows v2 Overview`). Run the file after each change.

## 5. Do not touch
Templates, CSS, JS (brief 0707 is polishing them in parallel; do not depend on its classes beyond those in section 2).

## 6. Commands (from App/, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`.venv/bin/python -m pytest tests/test_0706_v2_overview_browser.py tests/test_0705_v2_shell_browser.py tests/test_dashboard_*.py tests/test_needs_you_*.py tests/test_0375_needs_you_and_open.py tests/test_0520_overview_today.py tests/test_overview_headcount.py tests/test_host_quiet_dashboard*.py tests/test_design_dashboard.py tests/test_query_budget.py -q --tb=line -rs 2>&1 | tail -30`.

## 7. Acceptance
All pass, 0 skipped.

## 8. Stop and ask
Stop if a test shows a real behaviour regression on `/` (a needs-you action, link or count that is wrong, not just moved); report it.

## 9. Report
`docs/tasks/0708-report.md`: every test changed and why, the batched-path finding, final tail.
