# Page: Cleaning (`/cleaning`, template `cleaning.html` + `_cleaning_screen.html`)

Master version: 2.0.0. Adds only; never overrides MASTER.md.

## Identity
- nav: `cleaning`
- body_kind: `list`
- title key: `cleaning.title`; meta: `cleaning.subtitle` shortened to one line (next cleaning date and count)
- back link: none

## Header
- primary action: `cleaning.share_cleaner` -> `/cleaning/shares`
- secondary actions: `cleaning.add` -> `/cleaning/new` (plus icon); `cleaning.settings` -> `/cleaning/properties`

## Body (host)
- three tables in order: Today, This week, Later (`_cleaning_table.html`, 0540)
- columns: Property; Time or Day; Next arrival; Status badge
- badges: `action` = check the time; `attention` = hours missing; `neutral` = scheduled
- below the tables: the cleaning calendar (`_cleaning_calendar.html`, drag to move)

## Body (cleaner, shared view)
- unchanged: cards (`_cleaning_list.html`), calendar first, skip link to the list

## Empty state
- `cleaning.empty.title` ("No cleaning scheduled"), `cleaning.empty.body` ("Cleaning is added from a stay's checkout or by hand."), `cleaning.add` -> `/cleaning/new`

## Tests
- test-map row: `test_cleaning_browser.py`, `test_host_geometry.py`; screenshots 390 and 1280 plus the list skeleton
