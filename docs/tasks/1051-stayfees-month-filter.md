# 1051: Stay fees month filter (compact, no Apply)

Status: review

Owner: Josef, 2026-11-09. Executor: Claude (implemented directly, caller asked).

## 1. Objective
The Stay fees list and fee detail get one compact, centred month control under the page header: `‹  November 2026 ▾  ›`. The trigger opens the existing 3x4 month grid with year arrows; it closes on pick. Picking a month (grid, arrow, native input) navigates at once to `/stay-fees?month=YYYY-MM` (detail: `/stay-fees/{id}?month=`). No Apply button when JavaScript runs.

## 2. Context
Owner asked for a Wolt-like compact month filter on Stay fees; `_list_filter.html` is shared with invoices, so the new look is opt-in.

## 3. Files
- `App/app/templates/_list_filter.html`: new include flag `filter_compact`. When set: no toolbar "Filters" button and no summary line, form gets `list-filter--compact` and `data-filter-compact`, label is screen-reader only, property/status selects sit in a quiet `<details>` ("Filters"), open when one is active. The submit button stays for no-JS and is hidden under `.has-js`. Invoices does not set the flag and is unchanged.
- `stay_fees.html`, `stay_fee_detail.html`: `{% set filter_compact = true %}` before the include.
- `App/app/static/app.js`: compact forms skip the collapse panel; month change, arrow step, grid pick and select change call `navigateFilter` (drops empty params, `Turbo.visit` or `location.assign`). The grid panel is centred under the trigger in compact mode. Arrow steps now dispatch `change` on the native input (harmless for invoices: the listener only re-renders).
- `App/app/static/app2.css`: one `0818b` block scoped to `form.list-filter--compact`; tokens only; 44 px targets below 1024 px.
- `App/app/routes/stay_fees.py`: `_default_month` returns the current month (owner decision 2026-11-09). Every route and the `pdfs.zip` fallback use it. Future months stay refused (max month = current month).
- Cache keys: `base.html` app.js and app2.css, `tests/static_versions.json`.
- Docs: `docs/design/pages/stay-fees.md` toolbar line, decisions, status.

## 4. Steps
Template flag, JS navigation, scoped CSS, default month, cache keys, tests, screenshots, docs, in that order.

## 5. Do not touch
Invoices look, list_filter.py parsing, filing logic, new i18n keys, new dependency, outbound request, personal data.

## 6. Commands
- Test-map row "Invoices, stay fee": `test_invoice_*.py test_stay_fee*.py`, plus `test_list_filter.py`.
- `test_layout_lint_browser.py` (0 skipped), `test_host_geometry.py`.
- New `tests/test_stay_fee_month_filter_1051_browser.py`: default is current month, grid pick navigates without Apply, prev/next arrows navigate, next disabled at current month, no overflow at 390 px, no Apply visible with JS.
- Screenshots 390/768/1280 of list and detail in `/mnt/project-files/ux-shots/stayfees-filter/`.

## 7. Acceptance
All tests above green with 0 skipped; screenshots opened and described in the PR; invoices unchanged.

## 8. Stop and ask
Any change to filing logic or to which months can be saved.

## 9. Report

[1051-report](1051-report.md)
