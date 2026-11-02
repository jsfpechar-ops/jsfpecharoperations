# 0761 report: get and share a card payment link

Status: review

## Files changed

- App/app/routes/payments.py: POST `/payments/requests/{id}/link` (makes or reuses the link, sets draft to sent, 303 to our own share page) and GET `/payments/requests/{id}/share`.
- App/app/templates/payments_share.html (new): link field, Copy, Send by e-mail, Send on WhatsApp, note, back link.
- App/app/templates/payments.html: "Get link" button on open card requests; QR hint stays for QR only.
- App/app/host_i18n.py: en and cs keys.
- App/tests/test_payment_rails.py: 4 tests.
- App/tests/test_payment_share_browser.py (new): 390 px overflow check and screenshot.
- docs/design/pages/payments.md: 2 lines.
- docs/tasks/screenshots-0761/share-390.png (new).
- docs/tasks/0761-payment-link-share.md: Status line only.

## Test results (section 6)

1. `pytest tests/test_payment_rails.py tests/test_payments_dashboard.py tests/test_payment_request_model.py tests/test_stripe_connect.py tests/test_payments_consent.py -k "not fits_a_phone"`: `78 passed, 1 deselected`
2. `pytest tests/test_payment_share_browser.py tests/test_design_guardrails_browser.py` (browser required): `12 passed in 71.64s`, 0 skipped
3. `design_lint.py`: `design lint: OK`
4. `context_lint.py`: `context lint: OK`

## Screenshot

docs/tasks/screenshots-0761/share-390.png: Czech share page at 390 px, no horizontal overflow. The image also shows a test-environment banner and a 2FA prompt overlay from the app; neither comes from this change.

## Deviations

- Step 2: `payment_request.get` returns a dict, so the `dict(row)` wrap was not needed.
- Step 5: the new keys are inserted directly after the `payments.qr.preview` line in each language block.
- The screenshot test run rewrote the PNG; the committed version was restored.

## Owner steps

Do not push or merge yet. After review and merge, deploy manually. Then test: Platby, create a card request without an e-mail, press "Získat odkaz", then "Poslat přes WhatsApp".
