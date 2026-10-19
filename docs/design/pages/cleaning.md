# Page: Cleaning (`/cleaning`, template `cleaning.html` + `_cleaning_screen.html`)

Master version: 2.0.0. Adds only; never overrides MASTER.md.

## Identity
- nav: `cleaning`
- body_kind: `list`
- title key: `cleaning.title`; meta: `cleaning.subtitle` shortened to one line (next cleaning date and count)
- back link: none

## Header
- primary action: `cleaning.add` -> `/cleaning/new`
- secondary actions: `cleaning.settings` -> `/cleaning/properties`; `cleaning.share` -> `/cleaning/shares`
- tabs: (`cleaning.tab.list`, `/cleaning`), (`cleaning.tab.calendar`, `/cleaning?view=calendar`)

## Toolbar
- search: property name
- chips: `Upcoming`, `This week`, `Done`
- filters (sheet on phone): property: select; date range: date_range
- actions: none

## Body
- list columns: date and window (`d. m., HH:MM to HH:MM`); property (`property_dot` + name); stay context (checkout guest count or "manual"); door code (mono, copy_button, omitted when none); status badge; row menu
- phone card: line 1 date and window + badge; line 2 property; line 3 code or stay context
- grouped by day: a `section` title per date (existing 17 px date headings become section titles)
- badges: `action` = cleaning today without a cleaner confirmed or hours missing ("Hours missing"); `attention` = window changed by a later arrival; `done` = marked cleaned; `neutral` = scheduled
- row menu items: Open, Edit, Mark cleaned, Copy door code, Delete
- calendar tab: `calendar` component in month/week with cleaning markers (existing behaviour, restyled)

## Empty state
- `cleaning.empty.title` ("No cleaning scheduled"), `cleaning.empty.body` ("Cleaning is added from a stay's checkout or by hand."), `cleaning.add` -> `/cleaning/new`

## Tests
- test-map row: `test_cleaning_browser.py`, `test_host_geometry.py`; screenshots 390 and 1280 plus the list skeleton
