# Pages: Stays list (`/reservations`, `reservations.html`) and Stay detail (`/reservations/{id}`, `reservation_detail.html`)

Master version: 2.0.0. Adds only.

## Stays list
- nav: `reservations`; body_kind: `list`; title key: `stays.title`; meta: `stays.pagination.showing` count line
- primary action: `stays.add_stay` (opens the add-stay `dialog`: property select, arrival, departure, expected guests, label, email; primary `stays.add_panel.create`)
- secondary actions: `bulk_send_ready` ("Send n ready reports", shown only when n > 0, `send` icon)
- tabs: (`stays.tab.stays`, `/reservations`), (`stays.tab.reports`, `/submissions`), (`stays.tab.register`, `/housebook`)
- toolbar: search = guest or label; chips = Upcoming, Past, All, Archive; filters sheet = property select, state select, stay dates date_range; actions = Save view, Export CSV
- columns: Stay (label + `source` as 13 meta); Dates (`d. m. to d. m.` + nights, "In house" neutral badge); Property (`property_dot`); Guests (n of m, right); Police report (badge + deadline line); actions (one `secondary compact` Send when ready, menu)
- phone card (MASTER 7.3 roles, one DOM): `primary` = stay label with source inline; `secondary` = dates with nights inline; `badge` = report badge, then the deadline badge, on their own line; `meta` = property, then guests at the right; `actions` = menu at the top right, Send (only when ready) as the full-width last line
- desktop rows: the Stay, Dates and Police report cells carry one sub-line; rows stay under 72 px; the date text is plain ink (the row is the link)
- setup strip (`onboarding_banner`): one quiet line, `secondary compact` Continue + `quiet compact` Skip; the page's only primary is Add stay
- badges: `action` = ready to send, guest missing, rejected, failed ("!" when overdue); `attention` = deadline within 24 h, sent and no confirmation after 48 h; `done` = confirmed; `neutral` = waiting for guests, not required, cancelled, archived
- row menu: Open, Copy guest form link, Add guest, Open guest form, Delete (or Restore in Archive)
- pagination: Show more on phone, Previous/Next on desktop
- empty states (unchanged keys): no property, no calendar, no match, archive empty

## Stay detail
- nav: `reservations`; body_kind: `detail`; title: stay label; meta: dates, nights, property link; back link: `stay.detail.back` -> return_to
- primary action: the one next step (Send report | Fix guests | Download receipt | View reports), from `send_controls`; nothing else coral on the page
- secondary actions: Edit stay (`pencil`), menu: Copy guest form link, Open guest form, Invoice, Delete
- side column (facts): property, dates, guests n of m, source, automation mode, guest form link with copy_button
- main sections: Now (banner for cancelled / ignored / archived / demo, then one sentence state); Guests (one card per saved guest with facts in 2 columns, missing slots as neutral rows with "Share invitation" secondary, "Edit count" quiet); Police reporting (badge per filing row, receipt download, "File by hand" as a `details` section); Stay settings (small form, primary Save is NOT used here: this section's Save is `secondary`, the page primary stays the next step)
- badges: as the list; filing rows add `neutral` "Sent" until UbyPort answers

## Tests
- `test_host_filter_panels_browser.py`, `test_host_controls_browser.py`, `test_host_geometry.py`, `test_host_list_layouts_browser.py` (rows ≤ 72 px at 1280, badges on one line), `test_design_stays.py`; screenshots 390 and 1280 of both pages plus list and detail skeletons
