# Pages: Invoices (`/invoices`, `invoices.html`), Invoice detail (`invoice_detail.html`), Invoice builder (`/invoices/new`, `invoice_form.html`)

Master version: 2.0.0. Adds only.

## Invoices list
- nav: `invoices`; body_kind: `list`; title key: `invoices.title`; meta: count for the selected period
- primary action: `invoice.new` -> `/invoices/new`
- secondary actions: none
- tabs: (`invoices.tab.all`, `/invoices`), (`invoices.tab.settings`, `/invoices/settings`)
- toolbar: search = number or customer; chips = This year, Last year, All; filters sheet = period (`_list_filter.html` month/year selects become two `select`s), status select; actions = Export CSV
- columns: Number (mono); Date; Customer; Kind; Total (right, tabular); Status (badge); actions = `secondary compact` PDF (`download`), menu
- phone card: line 1 customer + status badge; line 2 number and date; line 3 total
- badges: `done` = "Payment recorded" (host marker only, never bank-derived); `neutral` = "No payment recorded", draft, cancelled; `attention` = correction issued; never `action` (nothing to file)
- row menu: Open, Download PDF, Send by email, Record payment
- pagination: Show more / Previous, Next

## Invoice detail
- body_kind: `detail`; title: number; meta: customer and issue date; back link: `invoices.title`
- primary action: `host.invoice_pdf` (Download PDF)
- secondary actions: Send (`send`), menu: Record payment, Correct, Cancel
- side facts: seller, customer, VS, due date, payment state with recorded date
- sections: Items (`table`, 5 columns), Payment (facts + Record payment secondary), History (neutral rows)

## Invoice builder
- body_kind: `form`; lane narrow; steps indicator "Step n of 4" (seller, customer, items, review); primary `Continue` then `Issue invoice` on review; items as repeating `field_pair` rows with a quiet "Add item"; preview labelled "Preview" in a neutral banner

## Empty state
- `invoices.empty.title` ("No invoices yet"), body one sentence, `invoice.new` -> `/invoices/new`

## Tests
- `test_host_*invoice*` rows in the test-map, `test_host_geometry.py`; screenshots 390 and 1280 plus list and form skeletons
