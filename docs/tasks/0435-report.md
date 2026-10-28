# 0435/0436 report: card rail (Payment Links) + QR rail (SPAYD)

Status: review

## Files

- `App/app/payment_links.py` (new): Payment Link creation on the host's
  connected account (`stripe_account` param, application fee 0, CZK
  haléř); `on_paid` webhook handler.
- `App/app/routes/payments.py`: Send action (card + QR), QR page + QR PNG
  endpoints; rail chips in the request form; Send buttons in the list;
  `_host_reply_to` (guest mail answers the host's entity contact).
- `App/app/stripe_connect.py`: `process_event` dispatch extended with
  `payment_link.paid` / `checkout.session.completed` → `payment_links.on_paid`
  (recorded in the dedupe table first, unchanged).
- `App/app/mail.py`: `payment_request` kind (KINDS + GUEST_KINDS — Reply-To
  contract applies).
- `App/app/i18n.py`: guest mail subject/text (en/cs).
- `App/app/templates/payments_qr.html` (new): QR page — amount, VS, QR PNG,
  the limits disclosure.
- `App/app/host_i18n.py`: send/error/QR strings (en/cs).
- `App/tests/test_payment_rails.py` (new): 11 tests.

## Commands (last lines)

- `pytest tests/test_payment_rails.py` → 11 passed
- full payments row (rails + dashboard + model + connect + migrations) → 70 passed
- `pytest tests/test_guest_mail.py` (mail-kind contract) → 52 passed
- `context_lint.py` → OK

## Findings fixed on the way

- Webhook can beat the Send click: `on_paid` now walks draft → sent → paid.
- Re-send hit the `sent → sent` transition wall: resend skips the status
  write and uses a `:v2` idempotency key (one mail per send).
- Guest mail contract: payload carries the host's entity `contact_email` as
  Reply-To, never UbyHost support.
- QR PNG route must be declared before the generic QR page route
  (FastAPI path matching), and uses `{request_id:int}.png`.

## [verify] item from the brief

- The paid event for Payment Links on connected accounts: the handler
  accepts both `payment_link.paid` (object.payment_link) and
  `checkout.session.completed`; the owner confirms which fires on the first
  test-mode run (Stripe Dashboard → Developers → Events).

## Owner steps

1. Register the **connected-accounts destination** webhook endpoint (already
   in 0428's steps) and subscribe it to `payment_link.paid` and
   `checkout.session.completed` in addition to `account.updated`.
2. First test-mode run: send a card request, pay the test link, confirm the
   row flips to `Zaplaceno` and note which event fired.

## Deviations

- The QR guest page is currently host-preview only (behind login); the
   public tokenized guest URL is part of the notifications pass (P1.5
   follow-up) — the mail carries the preview link meanwhile. Disclosed here
   because the brief said "the guest email carries a link to the payment
   page"; the link resolves to the login page for the guest until the token
   pass lands.
