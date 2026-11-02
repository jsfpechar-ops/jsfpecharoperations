# 0820 report

Status: blocked

## Done

- Step 1: `App/app/booking_site.py` got `import hmac`, `manage_token`, `token_ok`, `manage_url`. Commit `83eaffe`.
- Step 2: `App/app/booking_invoice.py` created. Commit `31c3f23`. Ruff passed.
- Step 3: `App/app/booking_webhook.py` got the invoice call and the `guest_manage` mail line. Commit `a43b378`. Ruff passed.
- Step 4: `App/app/routes/property_page.py` got the `invoice.pdf` route before `/thanks`. Commit `ebd8806`. Ruff passed.
- Step 5: `App/app/host_i18n.py` got the three keys in English and Czech. Commit `55b3108`. `tests/test_booking_site.py tests/test_host_i18n.py tests/test_no_em_dashes.py` run together: 50 passed.
- Step 6: `App/tests/test_booking_invoice.py` created, 8 tests. `pytest tests/test_booking_invoice.py -q`: 8 passed. Ruff passed. Committed in the commit that carries this report.

## Next

- Step 7: append the decision line to `docs/context/decisions.md`. Not done.
- Step 8: run §6 and tick §7. Not done.

## Blocked

The session hit the tool-call cap (28) before step 7. Nothing else failed.

## Deviations

- Brief step 6 says `invoice.total_czk`; the invoice table has no such column. The test compares `total_haler` with the booking's `total_czk * 100`.
- Step 6 `_cleanup` also deletes `invoice_sequence` rows and sets `settings.invoice_purge_unlock = 1` for the issued-invoice delete guard (`invoice_delete_guard` trigger). Both are needed for teardown.
- Step 6 test 4 (host invoice made by hand) first issues a real invoice, clears `site_booking.invoice_id`, then stubs `invoices.issue` to raise `StayLimit` with that id.
- Step 6 route tests use the fixed slug `invoice-flat`: the route reads only the token, not the slug.
- Step 6 mail test checks the `mail.enqueue` payloads captured in the fixture, not the `email_outbox` table.
- Steps 1 and 3 have no ruff command in the brief. I ran the step 2 ruff command on the touched files anyway.
- Commits used named files, not `git add -A`. The brief's commit line says `-A`.

## Questions

None.

## Owner steps

None yet.
