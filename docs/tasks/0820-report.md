# 0820 report

Status: blocked

## Done

- Step 1: `App/app/booking_site.py` got `import hmac`, `manage_token`, `token_ok`, `manage_url`. Commit `83eaffe`.
- Step 2: `App/app/booking_invoice.py` created. Commit `31c3f23`. Ruff passed.
- Step 3: `App/app/booking_webhook.py` got the invoice call after `_mail_confirmed` and the `guest_manage` mail line. Commit `a43b378`. Ruff passed.

## Next

Step 4: `App/app/routes/property_page.py`, the route `GET /p/{slug}/b/{booking_id}/{token}/invoice.pdf`.

## Deviations

- Steps 1 and 3 have no ruff command in the brief. I ran the step 2 ruff command on the touched files anyway.
- Done: steps 1 to 3. Left: steps 4 to 8.
- Step 3 references the key `site_booking.mail.guest_manage`, which step 5 adds. Until step 5 lands, the translate call for that key has no entry.
- Commits used named files, not `git add -A`, as the lead instructed. The brief's commit line says `-A`.
- Tests (step 8, brief §6) not run; this session stopped before them.

## Questions

None.
