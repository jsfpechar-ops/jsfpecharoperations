# Page: Dashboard (`/`, template `dashboard.html`)

Master version: 2.0.0. Adds only.

## Identity
- nav: `dashboard`; body_kind: `detail`
- title key: `dashboard.title`; meta: today's date (`date_cz`) and `dashboard.last_synced` when a feed exists
- back link: none

## Header
- primary action: `stays.add_stay` -> `/reservations?new=1`
- secondary actions: `calendar.add_cleaning` -> `/cleaning/new`; `dashboard.sync_calendars` (form post, `refresh-cw` icon)
- tabs: none

## Body (sections in order)
- `stat_row`: Needs action (`#needs-action`), Ready to send (`/reservations?status=ready`), Overdue (`#needs-action`); zero stays neutral, the number is `--ink`, never coloured
- `banner(attention)`: property setup missing (existing `missing_report_display` lines, one banner, one `secondary` "Finish setup")
- `calendar`: existing month / week / Gantt, stays only, controls restyled as `tabs` and `secondary compact` buttons
- `list_section` "Needs you now (n)": at most 5 `row`s: primary = dates; secondary = property + stay label; badge = task; menu = Open, Add guest, Open guest form, Copy guest form link, Delete; "View all stays" link in the section title row
- onboarding banner and finish card stay as `banner(neutral)` and an `empty_state`-styled card
- badges: `action` = guest missing, failed filing (overdue "!"), check report; `attention` = deadline within 24 h; `done` = filed on time; `neutral` = not required

## Empty state
- `dashboard.empty.title` ("Nothing needs you today"), body = next stay date when known, `dashboard.section.view_stays` -> `/reservations`

## Tests
- `test_dashboard_calendar_browser.py`, `test_host_geometry.py`; screenshots 390 and 1280 plus the detail skeleton
