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

## Phone (below 768 px; tablet and desktop unchanged)
- calendar: month grid only; each day shows its stays as dots (one per stay, property colour via `data-cal-color`, max 3 then "+n"), never text bars; tapping a day opens the existing day dialog (list of that day's stays, Add button); controls are the property picker, previous/next arrows and the month title; Calendar/Gantt, settings, Month/Week/Year, month and year selects and Today are hidden (0147)
- alerts: one `guest_pin_rotated` card for all properties, naming them in one line, linking to `/apartments`; dismissing it resolves all of them (0148, every width)
- `banner(attention)`: one line "N properties need setup" (`dashboard.setup.properties`, plural forms) with the "Finish setup" button; the per-field list is desktop only (0148)

## Empty state
- `dashboard.empty.title` ("Nothing needs you today"), body = next stay date when known, `dashboard.section.view_stays` -> `/reservations`

## Tests
- `test_dashboard_calendar_browser.py`, `test_host_geometry.py`, `test_dashboard_phone_browser.py` (390: dots, hidden controls, one PIN alert, one-line banner); screenshots 390 and 1280 plus the detail skeleton
