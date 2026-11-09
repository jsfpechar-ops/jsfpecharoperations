# 1052: Month filter chevrons as SVG

Status: review

## 1. Objective
Owner (2026-11-09, after #830): the text glyphs in the month picker look poor. Replace "▾" in the month trigger and "‹" "›" on the month and year arrows with the app's own Lucide chevrons (`icon()` macro, `currentColor`).

## 2. Context
`_list_filter.html` is shared by Stay fees (compact) and Invoices. The swap is markup-identical for both, so it is shared: invoices get the same chevrons.

## 3. Files
`App/app/templates/_list_filter.html`, `App/app/static/app2.css` (trigger and step alignment), `App/app/static/list-filter-compact.css` (chevron colour and size, both shells), `App/app/templates/base.html`, `App/tests/static_versions.json`.

## 4. Steps
Import `icon`; chevron-left/right 20 px on month steps, 18 px on year steps, chevron-down 16 px in the trigger; centre with inline-flex; bump cache keys `20261109-1052a`.

## 5. Do not touch
Picker JS, routes, copy, other pages.

## 6. Commands
`test_layout_lint_browser.py test_stay_fee_month_filter_1051_browser.py test_host_filter_panels_browser.py test_a11y_guard_browser.py test_list_filter.py`

## 7. Acceptance
Tests green, 0 skipped; screenshots in `/mnt/project-files/ux-shots/stayfees-chevron/` opened and described in the PR.

## 8. Stop and ask
If a chevron needs a new icon or a dependency.

## 9. Report
[1052-report](1052-report.md)
