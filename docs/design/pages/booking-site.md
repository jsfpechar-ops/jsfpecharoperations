# Page: Booking site (`/apartments/<id>/booking-site`, template `booking_site_setup.html`)

Master version: 2.0.0. This file adds; it never overrides MASTER.md. Keep it under 40 lines. No px, no colours.

## Identity
- nav: `properties`
- body_kind: `form`
- title key: `bsite.title`; meta: the apartment's internal name
- back link: `payments.page.title` -> `/apartments/<id>/page`

## Header
- primary action: none
- secondary actions: none
- tabs: none

## Toolbar (list kind only)
- not applicable (form kind)

## Body
- form fields (in order, pairs marked):
  - setup steps: facts list with badge `done | action | neutral`; the current step shows one secondary action link
  - price and rules (form): `nightly_price_czk`, `cleaning_fee_czk`, `min_nights`, `max_guests`, `notice` select; three choice cards for the cancellation policy; one primary Save
  - calendar link: read-only field, copy button, secondary "I pasted the link" submit
  - site address: link, copy button, QR image
  - publish: one primary button, disabled until Stripe and price are done; secondary Unpublish when live
- badges used: `done` = step complete, `action` = next step, `neutral` = waiting
- row menu items: none
- Max gate: banner `bsite.max_only` -> `/predplatne` (no price form shown)

## Empty state
- none

## Tests
- test-map row: `App/tests/test_booking_setup.py`, `App/tests/test_booking_site_host_browser.py`, `App/tests/test_design_guardrails_browser.py`; screenshots: 390 and 1280 of the body
