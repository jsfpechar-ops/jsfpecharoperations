# WP02: Property names in guest e-mails match the guest pages

Patch: `WP02-property-names.patch` (commit on top of `wpbase`, applies on `wpbase` alone; independent of WP01 and WP03).

## Summary
`mail_notify.property_label()` now returns the host's own name (`internal_name`) first and falls back to the police-register name (`uby_name`), the same order as the guest pages (`routes/guest.py` `_display_name`). The claim, claim resend, guest reminder and completion e-mails all get their name from this function. The `invoice_issued` mail now names the stay's property in the subject ("Invoice 2026-0001 – Downtown Comfort Loft") and adds an "Accommodation" row to the body when the invoice is linked to a stay. `uby_name` still goes to UbyPort; filing is unchanged.

## Files changed
- `App/app/mail_notify.py`: `property_label()` order and docstring; `build_invoice_issued(..., stay_property="")` with the stay subject and an extra panel and text row.
- `App/app/routes/invoices.py`: `_stay_property_name(invoice)` looks up the stay's property (`internal_name`, else `uby_name`) and passes it to the mail.
- `App/app/i18n.py`: `invoice_mail_issued_subject_stay` and `mail_invoice_property`, EN and CS.
- `App/tests/test_property_names_in_mail.py`: new.

## Tests added
`tests/test_property_names_in_mail.py` (15 tests):
- `property_label` prefers `internal_name`, falls back to `uby_name`, then to the translated stand-in;
- claim, claim_resend, reminder_guest, completion in EN and CS: subject and text contain `internal_name` and not `uby_name` ("č1");
- invoice sent through the route with a stay: subject, text and HTML contain the property name, not `uby_name`;
- invoice without a stay: plain subject "Invoice <number>", no property row;
- EN and CS subject wording with a stay.

## Test commands and results
From `App/`, with `/tmp/pr230/App/.venv/bin/python -m pytest -q`:
- `tests/test_property_names_in_mail.py`: 15 passed.
- On `wpbase` + this patch alone: `test_property_names_in_mail.py test_claim_mail.py test_guest_mail.py test_invoice_ux.py test_host_i18n.py`: 131 passed.
- Related: `test_claim*.py test_guest_mail.py test_invoice*.py test_mail*.py test_host_i18n.py test_cancelled_with_guests.py` plus every `*i18n*`, `*copy*` test: 299 passed.
- Broad run on the final stack: see WP01 notes (2192 passed, 3 skipped, 2 failures that also fail on `wpbase`).
- Ruff: all checks passed.

## Deviations from the spec and why
- `cancelled_with_guests` was not changed. It is a host mail and already uses `apartment["internal_name"]` directly (title only on `wpbase`). PR 230 item 5 rewrites this mail (property in subject, button); changing it here would conflict with that commit. Item 5 should use `mail_notify.property_label(apartment, lang)` or `internal_name`; both now give the same name.
- The invoice mail uses the property of the linked stay (`invoice.reservation_id`), not `invoice.apartment_id`, as the spec says "when the invoice is linked to a stay". An invoice with only an apartment and no stay keeps the plain subject.
- `reminder_host` and `submission_problem` were already on `internal_name`; not touched.

## What Cursor must verify or adapt when applying on the real main
- After PR 230 item 5 is merged: confirm `cancelled_with_guests` names the property with `internal_name` (or `property_label`) in subject and body.
- `test_claim_mail.py::test_the_registered_mail_kinds_are_the_ones_the_app_can_send` is not affected (no new mail kind).
- Search main for any new caller that reads `uby_name` for a guest-facing text.

## Manual steps for the owner
None.
