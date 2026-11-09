# 1051 report: Stay fees compact month filter

Status: review. Branch `claude/stayfees-month-filter`, draft PR.

## Done
- `_list_filter.html`: include flag `filter_compact` (set by `stay_fees.html` and `stay_fee_detail.html`). Compact = no toolbar Filters button, no summary line, centred `‹ Month YYYY ▾ ›`, sr-only label, property/status selects in a quiet "Filters" `<details>` (open when one is active, with Reset), no-JS submit hidden under `.has-js`. Invoices does not set the flag: markup unchanged.
- `app.js`: `initCompactFilter` + `navigateFilter` (drops empty params, `Turbo.visit`). Native change, grid pick, arrow step and select change navigate at once. Arrow steps now also dispatch `change` (invoices: only re-renders). Grid panel centred under the trigger in compact mode.
- `list-filter-compact.css` (new, tokens only, loaded on both shells because the fee detail is a v1 page): 3x4 grid, pill trigger, 44 px arrows and trigger, 16 px arrow gap (layout lint `tight-side`).
- `_default_month` = current month (owner decision 2026-11-09); covers list, detail, PDF, CSV, `pdfs.zip` and POST fallbacks. Future months still refused.
- `test_stay_fee_list.py` default pin moved 2026-08 -> 2026-09 with the owner-decision comment.
- New `test_stay_fee_month_filter_1051_browser.py`: default = current month, next disabled, no Apply/toggle with JS, trigger centred, prev/next/grid navigate without Apply, detail arrow navigates, no sideways scroll and 44 px targets at 390/768.
- Cache keys `20261109-1051a` (app.js, app2.css, list-filter-compact.css) in `base.html` and `static_versions.json`.

## Tests
`test_stay_fee*.py test_invoice_*.py test_list_filter.py` (non-browser) green; `test_layout_lint_browser.py`, `test_host_geometry.py`, the stay-fee browser tests and the new 1051 test green, 0 skipped.

## Screenshots
`/mnt/project-files/ux-shots/stayfees-filter/` list and detail at 390/768/1280, plus the open grid at 390.
