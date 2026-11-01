# 0523: Stays list redesign, part 2: computer styling, payment preselect, tests
Status: todo
Depends on: 0522 | Base commit: the 0522 branch head | Branch: task/0523-stays-list-style
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Finish the stays list from brief 0522: computer-width styling like the approved mockup (white card table, quiet grey header row, rows with generous padding), the "Request payment" link preselects the stay on `/payments`, and tests cover the new columns. The phone layout is not redesigned yet (owner has not approved a phone version): below 1024 px the rows keep today's card look.

## 2. Context
- Desktop table CSS lives in `App/app/static/host2.css` (grep `ui-table` and `stays-view`). Linked in `App/app/templates/base.html` as `host2.css?v=...`.
- New classes from 0522: `stay-col-property`, `stay-col-departure`, `stay-col-pay`, plus `data-stays-housebook`. Every new class must be listed in `docs/design/catalog.json` (the `classes` list and its description map), else `scripts/design_lint.py` fails CI.
- `/payments` route: `payments_page()` in `App/app/routes/payments.py` (around line 62); the stay `<select name="reservation_id">` is in `App/app/templates/payments.html` around line 37.

## 3. Files
Edit `App/app/static/host2.css`, `App/app/templates/base.html` (the `?v=` key only), `App/tests/static_versions.json` (only via `--write`), `docs/design/catalog.json`, `App/app/routes/payments.py` (payments_page only), `App/app/templates/payments.html` (the one `<option>`). Create `App/tests/test_0523_stays_list.py`. Existing tests only under section 8. Screenshots in `docs/tasks/screenshots-0523/`. Report `docs/tasks/0523-report.md`.

## 4. Steps
1. **CSS**, inside `@media (min-width: 1024px)` in `host2.css`, scoped to `.stays-view`: column widths so the row reads left to right like the mockup (guest widest; property, arrival, departure, reporting auto; `.stay-col-pay` and `.stay-col-actions` shrink to content, `white-space:nowrap`). Use only existing custom properties (`grep -n -- '--' App/app/static/host2.css | head -40`). Below 1024 px hide nothing except `.stay-col-pay` `th` (the link stays in the card's actions). Commit `0523 step 1`.
2. **Catalog.** Add the three classes with one-line descriptions to `docs/design/catalog.json`. Run `python3 scripts/design_lint.py 2>&1 | tail -10` from the repo root until clean. Commit `0523 step 2`.
3. **Preselect.** In `payments_page()` read `reservation_id` from the query (digits only, else `None`) and pass it as `selected_reservation_id`. In `payments.html` add `{% if selected_reservation_id == stay.id %}selected{% endif %}` to the stay `<option>` (match the loop variable name used there). Do not change anything else on the payments page. Commit `0523 step 3`.
4. **Test** `test_0523_stays_list.py` (copy fixtures and login from `tests/test_design_stays.py`): (a) `/reservations` headers in order Guest, Property, Arrival, Departure, Reporting; (b) a stay with lead guest "Sofia Costa" shows "Sofia Costa" in the row and the property name in `stay-col-property`; a stay with no guests shows `stays.row.no_name`; (c) the deadline badge still renders for an active stay; (d) the row links to `/payments?reservation_id=<id>`, and `/payments?reservation_id=<id>` has that option `selected`; another owner's stay id preselects nothing; (e) header has `data-stays-housebook` pointing at `/housebook.csv`. Commit `0523 step 4`.
5. Bump `host2.css?v=` in `base.html`, run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -5`. Screenshots of `/reservations?lang=cs` at 1280 and 390 px into `docs/tasks/screenshots-0523/`. Commit `0523 step 5`.

## 5. Do not touch
Any JS file, other templates, other routes, the phone card layout beyond step 1, the payments page layout. No new dependency, no migration.

## 6. Commands (from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`.venv/bin/python -m pytest tests/test_0523_stays_list.py tests/test_design_stays.py tests/test_archive_stays_on_page.py tests/test_stays_empty_workspace.py tests/test_payments_dashboard.py tests/test_static_versions.py -q --tb=short -x 2>&1 | tail -30`, then browser: `tests/test_host_wide_geometry_browser.py tests/test_host_list_layouts_browser.py tests/test_host_list_page_layout_browser.py tests/test_host_filter_panels_browser.py tests/test_host_fit_browser.py tests/test_0199_phone_geometry_browser.py tests/test_design_guardrails_browser.py -q --tb=short -x -rs 2>&1 | tail -30`, then from the repo root `python3 scripts/design_lint.py 2>&1 | tail -5` and `python3 scripts/context_lint.py 2>&1 | tail -10`.

## 7. Acceptance
All pass, 0 skipped. `git diff --stat` against the 0522 head lists only section 3 files plus section 8 test edits.

## 8. Stop and ask
Standing rule: a browser or server test that selects the old stays columns (`.stay-col-guests`, `.stay-col-dates > a` text with both dates, a five-column header) may be updated to the new columns: guest count now sits in `.stay-col-source`, departure in `.stay-col-departure`. Keep every geometry rule (no overflow, no clipped text, tap sizes) as strict as before. List each edited assertion in the report. Stop if a geometry rule itself fails.

## 9. Report
`docs/tasks/0523-report.md`: Status, test and lint tails, diff stat, screenshot paths, deviations.
