# 0093 report: visible controls and contextual help (host-wide pass)

Status: review. Base c482f48. Foundation (macros `field_label`, `help_tip`, JS, CSS, keys): see [0093a-report.md](0093a-report.md). This report covers the audit pass only.

## What changed
- Converted to the `?` tip (aria-describedby wired, unique ids): stay detail (guest e-mail, state, file-by-hand reference), invoice builder (due date), property create (address card lede), archive page (four section hints), smart-locks (title-only `?` link replaced by a real tip with Guide link; new key `smart_locks.steps_help`, EN+CS).
- `invoice_detail.html` "Invoice settings" now opens `/entities?edit={id}&next=...#entity-invoice`. Kept `/invoices/settings` where no entity is known: invoices list header, stay picker, host-local nav, command palette (several businesses possible; the redirect resolves it). Test updated.
- host.css: `/* 0093 pass */` block (`.heading-with-tip`, lock steps title). No JS, route, form, CSRF, fee, lock or filing change.

## Audit matrix
| Template | Converted | Left visible, why | Folds kept, why |
|---|---|---|---|
| apartment_form, _property_identity/address/operator, _stay_fee_fields | already (0093a/0088-0092) | - | - |
| _property_create | address lede to tip | copy-from notice (current state) | none |
| _account_parts | nothing to convert | - | - |
| dashboard | - | last-sync time (data) | none |
| apartments | - | locations, archived lede (list heading) | none |
| reservations | - | add-panel lede, counts, archive note (page purpose/state) | none |
| reservation_detail | e-mail, state, hand-filing reference hints | filing progress/send hints (state, warnings), values | file-by-hand details (pinned) |
| submissions | - | receipts hint beside its button | none |
| housebook | - (0091/0093 earlier: Guide link kept) | counts, archived lede, PDF dialog help | PDF dialog (export) |
| guide | - | canonical copy | none |
| entities | already (tips) | archived lede | none |
| invoices, invoice_stay_picker | - | no field help; settings link kept (entity unknown) | none |
| invoice_form | due-date help | ARES source note, stay price hint (data) | none |
| invoice_detail | link to canonical editor | note, empty-state | cancel details (confirmation) |
| stay_fees, stay_fee_setup (no template; fields in _stay_fee_fields) | - | counts, rates (data) | none |
| stay_fee_detail | already (VS tip) | QR help (describes amount), local-resident note (data), footnote | none |
| settings | already (settings_heading tips) | retention delete help beside its button | 2FA move/disable, passkey rename, Technical (pinned); audit stays open |
| settings_archived | 4 section hints | retention note (legal fact, pinned) | none |
| smart_locks | title `?` link to real tip | terms checkbox, warnings, status, assignments | "add another lock" details (0090 test pins; holds an action, no values) |
| onboarding | nothing (macro in _components) | - | - |

## Not edited, outside section 3 (findings for scope decision)
`_entity_business_fields.html` (email_hint), `_entity_invoice_fields.html` (next-number, snapshot hints), `_property_editor.html` (archive helps, TZ hint, ws password hint), `guest_form_admin.html` (field hints), `users.html` (create hint), `setup/bookings.html` (details), `privacy_requests.html` (details), `_host_navigation.html` (`/invoices/settings` link).

## Tests
- tests/test_host_help_browser.py extended: host-wide check (7 page families, EN+CS, 360/390/1280): ids unique, each `.help-tip-btn` has a matching body, focus opens it, tip inside viewport; plus a markup test that converted hints are tips with aria-describedby. 6 pass.
- 205 targeted tests across filed-by-hand, invoice nav/UX, smart locks, lock navigation browser, i18n, privacy, geometry, property controls, entity editor, stay detail: all pass, 0 skipped. Ruff clean. Full suite not run (per instruction).
- Updated: test_host_invoice_navigation (new link), test_lock_navigation_browser (tip instead of `a.help-link`).

## Evidence
docs/tasks/0093-evidence/{property-create,property-guests,stay-detail,invoice-builder,entities,settings,archive}-{360,390,1280}-{en,cs}.png (synthetic). Smart-locks shots: tests/test_lock_navigation_browser evidence of 0090.

## Owner steps
Review on staging with the combined branch; no deploy implied.
