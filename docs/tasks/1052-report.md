# 1052 report: month filter chevrons

Status: review.

- `_list_filter.html` imports `icon`; "▾" -> `chevron-down` 16 px, month "‹ ›" -> `chevron-left/right` 20 px, year arrows 18 px. Shared with invoices (identical markup, clean swap).
- `app2.css`: v2 trigger and step buttons are inline-flex centred. `list-filter-compact.css`: chevron sizing and the muted trigger chevron colour on both shells.
- Cache keys `20261109-1052a` (app2.css, list-filter-compact.css).
- Tests: layout lint (0 skipped), 1051 month filter, host filter panels, a11y guard, list_filter, static versions: 22 passed.
- Screenshots: `/mnt/project-files/ux-shots/stayfees-chevron/`. The 390 shots show the trigger with its focus ring because the test closes the grid with Escape just before (focus returns to the trigger).
