# 0434 report: property-page booking widget (P2.1 first slice)

Status: review

## Files

- `App/app/migrations/0030_booking_hold.sql` (new): `booking_hold`
  (15-min checkout holds) + `property_page.nightly_price_czk`.
- `App/app/property_page.py`: `nightly_price`, `dates_available`
  (reservation clash + live hold), `create_hold`, `release_expired_holds`,
  `widget_ready` (published + priced + Stripe mirror complete).
- `App/app/routes/property_page.py`: `POST /p/<slug>/book` (no-JS form →
  availability + itemized total), `POST /p/<slug>/request`
  (request-to-book: guest e-mail → draft `payment_request` in the host's
  list, 404 unless the widget is live).
- Templates: the Book card on the public page, the total panel, the
  request form, the confirmation.
- `App/app/host_i18n.py`: `pp.book.*` (en/cs).
- `App/tests/test_booking_widget.py` (new): 6 tests.

## Commands (last lines)

- `pytest tests/test_booking_widget.py` → 6 passed
- full branch row (payments + pages + mail + widget) → 154 passed
- Browser/geometry + 390 px: CI shard (sandbox has no Chromium).

## Scope notes (per the brief's split)

- Shipped: the form, availability, itemized total, request-to-book draft.
- P2.2 next on the payments plan: the host-approval charge
  (`checkout.session.completed` → the hold converts to a reservation);
  the Stripe Checkout Session on the host's account rides brief 0435's
  `payment_links` wrapper. The holds table + sweep are in place for it.
- Guest mail for a received request lands with the notifications pass.

## Owner steps

1. Set the nightly price per property on the review screen (the widget
   stays hidden until the property is priced and Stripe is complete).
2. CI browser shard check; merge when green.
