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

## Police reports list (`/submissions`, `submissions.html`, brief 0138)
- nav: `submissions`; body_kind: `list`; title `reports.title`; meta `reports.lede`; tabs: the section tabs; no primary action; secondary: Download receipts (`download` icon, only when there are receipts)
- table: the stay detail's report-table grammar; phone card: `primary` = sent at, `secondary` = property, `badge` = outcome, `meta` = mode, then guests at the right; stamp is desktop-only (`hide`); `actions` = menu with Details and Receipt (the receipt is a menu item, never a coral row button)
- empty state: unchanged keys, its action is the page's only primary

## Police report detail (`/submissions/{id}`, `submission_detail.html`, brief 0138)
- nav: `submissions`; body_kind: `detail`; title `reports.detail.title`; meta: property · mode; back: `/submissions`
- `#now` command panel and the `details.panel.technical` fold keep their markup (tests read them); the one coral link is Fix stay or Download receipt (exclusive branches, `cta` variable as on the stay detail); errors PDF is `secondary`
- guests: `ui-section` with a stacked `ui-table`; `primary` = guest name with nationality and document as sub-line, `badge` = result, `#` desktop-only

## Guest register (`/housebook`, `housebook.html`, brief 0138)
- nav: `housebook`; body_kind: `list`; title `housebook.title`; tabs: the section tabs; no primary in the header
- the filter toolbar, filter form, CSV menu and PDF dialog keep their own markup and JS hooks (legacy list); the filter Apply is the template's one primary, the PDF dialog Download is `secondary`
- the eleven-column register and the archived table stay legacy `table-cards` (labelled cards on phone, sideways scroll on desktop); only their badges and buttons move to v2

## Tests
- `test_host_filter_panels_browser.py`, `test_host_controls_browser.py`, `test_host_geometry.py`, `test_host_list_layouts_browser.py` (rows ≤ 72 px at 1280, badges on one line), `test_design_stays.py`; screenshots 390 and 1280 of both pages plus list and detail skeletons
