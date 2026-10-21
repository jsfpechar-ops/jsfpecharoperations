# Pages: Stay fees (`/stay-fees`, `stay_fees.html`) and Fee detail (`/stay-fees/{apartment_id}?month=`, `stay_fee_detail.html`)

Master version: 2.0.0. Adds only. Calculations and legal data belong to the fee plan; this file owns layout only.

## Stay fees list
- nav: `stay_fees`; body_kind: `list`; title key: `stay_fees.title`; meta: `stay_fees.list.summary` (period, properties, set up count)
- primary action: none (the period selector is the toolbar; set-up happens per property)
- secondary actions: none
- tabs: none
- toolbar: search = none; chips = none; filters = month select and year select inline on desktop, sheet on phone; actions = none
- columns: Property (`property_dot`); Period; Liable nights (right); Exempt nights (right); Total (right, `Kč`); Status (badge); menu
- when every property is unset the table shrinks to Property, Status, actions
- phone card: line 1 property + badge; line 2 period; line 3 liable, exempt, total
- badges: `action` = "Report not ready" with the blocker named in the detail; `attention` = period open, nights still changing; `done` = "Finalised" snapshot; `neutral` = "Not set up"
- row menu: Open, Download PDF, Download CSV, Set up fee (-> property settings)
- pay steps (0203): above the table, one `ui-section` per set-up property with an `ol` of three steps (confirm figures, Download PDF, QR Platba). Before the period is saved, steps 2 and 3 show a dashed `fee-step-locked` placeholder ("appears after step 1"). Step buttons are secondary (the filter Apply is the page's primary). No paid button.

## Fee detail
- body_kind: `detail`; title: property name and period; back link: `stay_fees.title`
- primary action: `Download PDF` when the route exists and the report is ready, else `Fix details` -> the exact property or entity field
- secondary actions: Download CSV; menu: Finalise period (confirm dialog)
- side facts: council, rate, variable symbol, account, "Payment details ready" state; copy_button on account and VS; QR Platba image when complete
- sections: Blockers (attention banner listing each missing field with a link); Totals (facts); Guest decisions (`table`: guest, dates, nights, liable or exempt badge, amount, `quiet compact` Change); exemption reason field inside the Change dialog with the data-minimising hint

## Empty state
- `stay_fees.empty.title` ("No property collects a stay fee"), body one sentence, action "Set up in property settings" -> `/apartments`

## Tests
- `test_host_*fee*` rows in the test-map, `test_host_geometry.py`; screenshots 390 and 1280 plus list and detail skeletons
