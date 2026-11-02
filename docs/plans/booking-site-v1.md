# Booking site v1 (Stripe phase S4)

Status: approved scope (owner, 1 Nov 2026); briefs 0814 onward. Builds on
[property-pages](property-pages.md) (slug, content, photos, availability) and
the S1-S3 Stripe work (onboarding live, card rail fixed, extras merged).

## 1. What v1 is

One public page per property at `/p/<name>-<code>` where a guest picks dates,
pays the full price by card through Stripe Checkout on the host's own Stripe
account, and gets a confirmed stay. UbyHost takes 0 %. Max plan only.

Owner decisions this plan applies (1 Nov 2026, scoping doc "UbyHost Stripe:
audit and scope"):

| Topic | Decision |
|---|---|
| Who | Max plan only (billing off in dev/tests = allowed) |
| URL | `ubyhost.cz/p/<slug>` as built in 0430 (name + 4-char code) |
| Mode | Instant book, full payment at booking, no request-to-book |
| Cancellation | Presets: Nevratná (default), Flexibilní, Střední; guest self-cancel link, Stripe refund runs automatically |
| Double booking | Automatic full refund, host absorbs the Stripe fee, host alerted |
| Advance notice | Same day until a cutoff hour (default 18:00), or 1, 2, 3, 7 days |
| Deposit | None |
| City tax | Never charged online; shown as "paid on site" |
| Terms | Guest terms CZ + EN (draft tabs in the scoping doc); Czech prevails |
| Invoice | Czech invoice PDF per booking in the host's name, from our own invoice engine; no Stripe Invoicing |
| Import | Apify listing import stays as built (0347, 0431) |
| Weight | Extremely light: no web fonts on the public page, inline CSS, no JS needed to book, no third-party script; Stripe Checkout is a redirect |
| Look | Public-page rules with the redesign tokens; host screens follow MASTER |

## 2. Rules (fixed in 0814, used by every later brief)

- **Price:** nightly price x nights + one cleaning fee. City tax shown as
  `stay_fee_rate_czk x guests x nights`, "platí se na místě".
- **Limits:** 1 to 30 nights, at least `min_nights`, guests 1 to `max_guests`
  (when set).
- **Advance notice** (Europe/Prague): days = 0 means today is bookable until
  the cutoff hour, then the earliest check-in is tomorrow; days = N means the
  earliest check-in is today + N.
- **Refunds** (check-in moment = check-in date at `apartment.checkin_hour`,
  default 15:00, Prague):
  - Nevratná: 0.
  - Flexibilní: 100 % until 24 h before check-in, then 0.
  - Střední: 100 % until 5 days before check-in; after that the cleaning fee
    plus 50 % of the accommodation until check-in; then 0.
  - Host cancels or a double booking is found: 100 %.
- **Availability:** no active reservation and no live hold overlaps
  (`property_page.dates_available`). Re-checked under a lock at checkout and
  again when the payment arrives.

## 3. Data

- Settings per property: JSON in the `settings` table, key
  `booking_site:<apartment_id>` (same pattern as the services catalog, 0762).
  Holds nightly price (also kept in `property_page.nightly_price_czk` for the
  existing widget), cleaning fee, min nights, max guests, cancellation policy,
  advance notice days, cutoff hour, iCal token.
- One new table `site_booking` (SQLite migration 0034 + goose 00004): the
  booking's dates, guests, guest name and e-mail, price lines, policy and terms
  version accepted, Stripe session and payment intent ids, refund amount,
  links to the reservation and invoice, status
  `pending | paid | expired | cancelled | refunded | clash_refunded`.
- On payment a `reservation` row with `source = 'site'` is created, so door
  codes, guest registration, police filing and stay fees work unchanged.

## 4. Briefs (order)

| # | Brief | Depends on | UI |
|---|---|---|---|
| 0814 | Data and rules: `site_booking` table, `booking_site.py` (settings, Max gate, quote, refund rule, iCal token, booking rows), Max gate on the widget | none | no |
| 0815 | Checkout: quote page "Pokračovat k platbě" -> locked hold (15 min) + pending booking + Stripe Checkout Session on the host's account (30 min); success and cancel pages; removes request-to-book | 0814 | small |
| 0816 | Payment webhook: paid -> re-check under lock -> reservation (`source='site'`) + mails, or automatic full refund on a clash; expired -> release hold | 0815 | no |
| 0817 | iCal export `/p/<slug>/<token>.ics` (site + manual stays) | 0814 | no |
| 0818 | [Public page v2](../tasks/0818-booking-site-public-page.md): Czech first with CS/EN switch (`?lang=`), server-rendered month calendar (booked and blocked nights, chosen range, no JS), guests, price lines, city-tax note, cancellation summary, terms checkbox with `TERMS_VERSION`, pay button to `/checkout`, page weight test | 0815 | yes |
| 0819 | [Host setup](../tasks/0819-booking-site-host-setup.md): `/apartments/<id>/booking-site`: 6-step checklist, price and rules form (`save_settings`), iCal link with copy button, site address with QR, publish, Max gate; design add-on `docs/design/pages/booking-site.md` | 0814, 0817, 0818 (same `host_i18n.py`) | yes |
| 0820 | [Invoice](../tasks/0820-booking-site-invoice.md): Czech invoice PDF per paid booking in the host's entity (reuses the host invoice code), `site_booking.invoice_id`, signed booking link (`booking_site.manage_token`), PDF route and link in the confirmation mail | 0816 | no |
| 0821 | [Cancellation, guest side](../tasks/0821-booking-site-cancellation.md): guest booking page and self-cancel by the signed link (refund per policy, Stripe refund with idempotency key), invoice storno on a full refund, mails to both, reservation freed | 0818, 0820 | yes |
| 0822 | [Cancellation, host side](../tasks/0822-booking-site-host-cancel.md): bookings list on the 0819 page, host cancel with full refund, repeat a failed refund | 0819, 0821 | yes |

0815 and 0817 can run in parallel after 0814; the rest go in order: 0818, 0819, 0820, 0821, 0822 (each edits `host_i18n.py` or a template the next one extends, so no parallel runs). Each UI
brief carries the redesign rules: page add-on, no new component classes,
browser + geometry tests, 390 px screenshots, Stripe links excluded from the
hover prefetch.

## 5. Owner steps (whole plan)

1. Merge 0814; deploy (deploy.sh applies goose 00004 itself).
2. In the Stripe Dashboard webhook for Connected accounts, also tick
   `checkout.session.expired` and `charge.refunded` (0816 names the full list).
3. Set the two test hosts to the Max plan in the billing cockpit.
4. After 0819: both test hosts set up a page on a phone without help, then
   one test-mode booking end to end before live.

## 6. Out of v1

Custom domains, price per season or weekday, discounts, request-to-book,
deposits, multi-property search, reviews, extras at checkout, embedded
Stripe Checkout.
