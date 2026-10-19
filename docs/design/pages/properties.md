# Pages: Properties (`/apartments`, `apartments.html`), Property form (`/apartments/new`, `apartment_form.html`), Property detail (`/apartments/{id}`, `_property_*.html`)

Master version: 2.0.0. Adds only.

## Properties list
- nav: `apartments`; body_kind: `list`; title key: `apartments.title`; meta: `dashboard.last_synced` when known
- primary action: `apartments.add` -> `/apartments/new`
- secondary actions: `dashboard.sync_calendars` (form post, `refresh-cw`)
- tabs: (`apartments.tab.properties`, `/apartments`), (`entities.title`, `/entities`), (`smart_locks.title`, `/smart-locks` when a lock account exists)
- toolbar: search = property name; chips = none; filters = none; actions = none (count line is the meta)
- columns: Property (`property_dot` + name, "Inactive" neutral badge); Business entity (link); Calendars (n, right); Stays (n, right); Setup (badge); menu
- phone card: line 1 name + setup badge; line 2 entity; line 3 calendars and stays counts
- badges: `action` = setup missing items ("Fix 2 items"); `done` = ready for reporting; `neutral` = inactive
- row menu: Open, Bookings and calendars, Settings, Copy guest link, Archive
- secondary section under the list: "Property summaries" (existing `#property-summaries`) as a `section` with a `table` (guest link, timing), max 6 columns

## Property form (create)
- body_kind: `form`; title: `apartments.add`; back link: `apartments.title` -> `/apartments`
- fields: internal name; address (street, number pair; city, postcode pair; country select); check-in hour and check-out hour pair (time); business entity select with help_tip; expected guests default
- primary: `common.save` (sticky on phone); secondary: `confirm.cancel` quiet
- errors next to fields after 422; values kept

## Property detail
- body_kind: `detail`; tabs: Overview, Bookings and calendars, Settings (existing `?view=`); side column = readiness facts; sections = existing groups (Bookings, Guest link, Police reporting with the police-letter help tips, Business details, Stay fee, Door lock) each as `section` with small forms whose Save is `secondary`; the page primary is "Finish setup" when readiness is missing, else none

## Businesses (`/entities`, `entities.html`, brief 0140)
- nav: `entities`; body_kind: `list` (the businesses table keeps the desktop table at 1280; a `settings` lane would turn it into cards); title `entities.title`; meta `entities.lede`; back link `entities.back` -> `/apartments` (or `common.back` -> `next`)
- tabs: the Properties tabs, Business & legal details current
- the edit and add forms keep their markup; each form's Save is the page's `cta` (`ui-btn ui-btn-primary`)

## Tests
- `test_host_fit_browser.py`, `test_host_geometry.py`; screenshots 390 and 1280 of list and form plus list and form skeletons

## Smart locks (`/smart-locks`, `smart_locks.html`, brief 0145)
- nav: `smart_locks`; body_kind: `list` (same lane as the other Properties tabs); title `smart_locks.title`; meta `smart_locks.lede`
- tabs: the Properties tabs above, Smart locks current
- one primary per state: Connect (no account), Check connection in the share block (no locks), Check connection under the list (locks); the "add more" share block's Check is `secondary`
- sections (`ui-section`): How it works, Setup, Share, Add more (details), Lock list; Remove is `danger` with the existing confirm
