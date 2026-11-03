# 0830B report: Overview and Menu (part B)

Status: review (not committed)

## Files
- `App/app/static/app2.css`: only between the `0830B overview+menu` markers. Overview cards get a 1 px border, no shadow and 16 px inner padding; the calendar day grid and stay bars get 12 px spacing; the headline-to-date gap is 12 px; the today-card border and shadow change and their radius is kept (0729 spec).
- `App/app/templates/dashboard.html`: not changed (the CSS alone fixed the Overview).
- `App/app/templates/menu.html`: not changed (see Deviations).
- `_dashboard_calendar.html`: not touched.

## Tests
- `-k partB` (`tests/test_0830_airbnb_pages_browser.py`): 12 passed, 0 failed, 0 skipped (before: overview 6 failed, menu 6 passed).
- `tests/test_0729_phone_today_geometry_browser.py -k today`: 4 passed after the change (a first version set radius 12 on the phone cards and broke it; fixed).
- Old tests run (14 files, dashboard and menu): 94 passed, 11 failed. Failures outside this part, not from this CSS:
  - `test_0252_touch_sweep_browser.py`: `/reservations` (part D) and `/settings/archived` (settings).
  - `test_0284_states_browser.py::test_hover_changes_every_clickable_thing`: `/reservations?range=all` chip (part D).
  - `test_design_shell_browser.py` (5 cases): look for `.ui-sidebar`, `.ui-tabbar` and `#main-content`, which the v2 shell does not render; likely failing before this part. Not verified at HEAD.
- `scripts/design_lint.py`: no findings in dashboard.html, menu.html or app2.css (the run ends FAIL on other parts' templates).

## Screenshots (390 px; 768 and 1280 also in the folder)
- `docs/tasks/screenshots-0830/partB-overview-390.png` (looked at once: bordered cards, no shadows, pills and bottom bar fine)
- `docs/tasks/screenshots-0830/partB-menu-390.png`

## Deviations
- Menu: not rebuilt. It already passes all six widths and its rows have no shadow. The link list still uses `.row` markup, not `partials/settings_index_row.html`, because the shared partial cannot show the cleaning badge. Owner or orchestrator decision needed if the index-row look is required.
- Overview: fixed in CSS only, no template edit.

## Questions
- Should menu switch to the index-row partial with a badge slot? The partial would need a `badge` parameter (shared file, not in this part).

Owner steps left: none.
