# 0701: Overview look, part 1: "Potřebuje vás" as cards, simple "Dnes" table
Status: todo
Depends on: PR #657 branch | Base commit: claude/project-thread-50hyv5 | Branch: task/0701-overview-cards
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective
Overview (`/`) at computer width matches the approved mockup (`/mnt/project-files/ux-redesign/ubyhost-redesign-v2.html`, view "today"; screenshot `/mnt/project-files/ux-redesign/overview/mockup-overview-1280.png`; gap list items 8, 9, 11). Brief 0700 does the shared look (canvas, pills, tables) in parallel; do not repeat it here.

## 2. Context
- Template `App/app/templates/dashboard.html`: macro `needs_you_line`, section `.needs-you`, the `dashboard-today` section and macro `dashboard_rows` (added by 0520).
- CSS for these lives in `App/app/static/workflow.css` (`.needs-you*`, `.dashboard-quiet`).
- Mockup values: card `#fff`, `1px solid #ebebe7`, radius 12px, padding 16px, gap 14px; icon tile 44x44 radius 10px, bold, red tone `#fdecea`/`#b42318`, amber tone `#fff4d6`/`#8a5200`, grey `#efefeb`/`#55554f`; title 700; text 13px `#55554f`; small pill button. Section heading 16px/700, no box around the section.

## 3. Files
Edit `App/app/templates/dashboard.html`, `App/app/static/workflow.css` (+ its `?v=` in `base.html`, `App/tests/static_versions.json` via `--write`), `App/app/host_i18n.py` and `App/app/host_vi_i18n.py` (only keys named below), `docs/design/catalog.json` (new classes). Create `App/tests/test_0701_overview_cards_browser.py`. Screenshots `docs/tasks/screenshots-0701/`. Report `docs/tasks/0701-report.md`.

## 4. Steps
1. **Needs you as cards** (CSS only where possible, scoped `@media (min-width:768px)`): `.needs-you` loses its border, padding and background; its `h2` is 16px/700 and the count badge stays. `.needs-you-list` is a 2-column grid, gap 12px. Each `.needs-you-item` is a card (values above) laid out icon tile left, copy right, actions under the copy (not at the far right); no coloured left border. `.needs-you-icon` becomes the 44px tile coloured by the item's `data-tone` (red, amber, grey). Buttons inside are the small size (`ui-btn` with padding 6px 12px, 13px). Keep the 5-item cap and the "more" details. Commit `0701 step 1`.
2. **Dnes table**: replace the call `dashboard_rows(today_rows, ...)` in the `dashboard-today` section with a small new macro `today_rows_table(items)` in the same file using `ui_table_begin`/`ui_table_end` with columns: Host (`stay_label`, under it in `<small>` the guest count text via `tp('dashboard.today.guests', n)` where n is `progress.total` or the guest count the existing `guest_count` macro uses), Nemovitost (`property_identity(...)` as in `dashboard_rows`), Termín (`t('calendar.arrival')` + " · " + `tp('dashboard.today.nights', nights)` when arriving today, else `t('calendar.departure')`), Stav (the same badge logic as `dashboard_rows` column 4, but for `awaiting_guest` show `tp('host.missing', progress.not_registered)` too), and the same row menu. Rows keep `clickable-row` and `data-href`. Remove the `caption_key` and `mark_today` parameters 0520 added to `dashboard_rows` (restore its old signature) since nothing else uses them. New copy: `dashboard.today.guests` en "%(count)s guests" (.one "1 guest", .few same as plural), cs "%(count)s hostů" (.one "1 host", .few "%(count)s hosté"), vi "%(count)s khách"; `dashboard.today.nights` en "%(count)s nights" (.one "1 night"), cs "%(count)s nocí" (.one "1 noc", .few "%(count)s noci"), vi "%(count)s đêm". Nights = `(date_to - date_from).days` computed in the template from the ISO strings or passed from the route (`today_rows` in `App/app/routes/admin.py` may add a `nights` key per row; that is allowed). Commit `0701 step 2`.
3. **"Jak to funguje?"** is styled by 0700; do nothing here.
4. Register new classes in `docs/design/catalog.json` (list and description map, like `dashboard-quiet`), run `python3 scripts/design_lint.py | tail -3` from the repo root. Bump `workflow.css?v=` to `20261101-0701`, `--write` static versions. Commit `0701 step 3`.
5. Test `test_0701_overview_cards_browser.py` (copy fixtures from `tests/test_host_quiet_dashboard_browser.py`): at 1280 px two needs-you items sit side by side (same `top`, different `left`), each has no left border wider than 1 px, the icon box is 44x44; the Today table header texts are Host/Property/Dates/Status in en (use the keys you used); a stay arriving today shows "Arrival · N nights". At 390 px the needs-you items are still stacked (one column). Commit `0701 step 4`.
6. Screenshot `/?lang=cs` at 1280 and 390 px with several stays (reuse the rich fixture of `test_host_quiet_dashboard_browser.py`). Commit `0701 step 5`.

## 5. Do not touch
Needs-you logic (`needs_you_build`), the calendar, `dashboard-calendar.*`, `host2.css`, `tokens.css`, JS.

## 6. Commands (from `App/`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`)
`.venv/bin/python -m pytest tests/test_0701_overview_cards_browser.py tests/test_0520_overview_today.py tests/test_host_quiet_dashboard_browser.py tests/test_dashboard_rows_browser.py tests/test_dashboard_phone_browser.py tests/test_design_dashboard.py tests/test_needs_you_0240.py tests/test_needs_you_dashboard_0241.py tests/test_0375_needs_you_and_open.py tests/test_dashboard_order.py tests/test_query_budget.py tests/test_static_versions.py -q --tb=short -x -rs 2>&1 | tail -30`, then `python3 scripts/design_lint.py | tail -3` and `python3 scripts/context_lint.py 2>&1 | tail -3` from the repo root.

## 7. Acceptance
All pass, 0 skipped; design lint OK; diff only section 3 files plus tests updated under section 8.

## 8. Stop and ask
Existing assertions about the needs-you box geometry at >= 768 px (border, single column, button at the right) or the old Today table columns may be updated to the new layout; list each. Stop if a phone (< 768 px) assertion changes or the query budget test fails.

## 9. Report
`docs/tasks/0701-report.md`: Status, tails, diff stat, screenshots, updated assertions, deviations.
