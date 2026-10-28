# 0434: Property page booking widget (property pages E, payments P2.1 first slice)

Status: todo
Depends on: 0433; payments P1.3 + P1.5 | Base commit: after both | Branch: task/0434-booking-widget
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens — the hold
system (§4 step 3) may spill into a follow-up brief; ship the form + total +
request path first

## 1. Objective

The "Book" card on the published property page, per the owner (28 Oct):
Airbnb-style in feel, **built from our own parts** — the existing stay
calendar's availability logic, the existing stay-fee total calculation, a
no-JS form POST, and Stripe checkout on the host's connected account
(0428). Ecological: no booking-by-bidding, no dark patterns, one clear
total, no tracking (rule 2; the page has no third-party scripts).

## 2. Context

- Owner decision: "same as Airbnb ideally or use from our filters one, be
  ecological" — read as: the *interaction pattern* (dates + guests →
  itemized total → book) and reuse of our own date/fee logic; nothing
  Airbnb-branded (plan Design section limits hold here too).
- Data contract (from 0431): the page knows its `apartment_id` through the
  slug; the widget renders only when `published` and the host's Stripe
  mirror state is `complete` (0428 `stripe_account.onboarding_state`).
- Widget, no-JS first (rule 6): a `<form method="post">` with date-from,
  date-to, guests; on POST the server validates availability against the
  same rules the host calendar uses, computes the itemized total with the
  existing stay-fee logic (nightly × nights + cleaning, per the host's
  settings — reuse `stay_fees`), and shows the confirmation panel: itemized
  rows, total, "Continue to payment" (Stripe Checkout Session on the host's
  connected account, application fee 0 — the payments plan §1 item 7
  payment mode) or "Send a request" (the request-to-book path is P2.2 and
  is NOT in this brief; the button says the host will confirm, creates a
  `payment_request`-style draft reservation row, and notifies the host).
- Holds: 15-min checkout hold per the payments plan §1 item 8 — a
  `booking_hold` row (migration 0030) excluding the dates at DB level;
  sweep in the existing scheduler pattern; the hold is released on Session
  completion/expiry. If the session runs long, this step moves to its own
  brief (0435) and the widget ships without holds but with a re-validation
  at "Continue to payment".
- Privacy: guest_email collected at the checkout step only (the
  `payment_request.guest_email` column already exists); retention already
  covered by 0425. No tracking cookies (rule 2); PostHog not on this page.
- Rate limit the POST per the public POST pattern (webhook row, 0428) +
  Turnstile on the form if the public forms row requires it (check
  `App/app/routes/guest.py` for the current public-form gate).
- Languages per 0344; rule 7 browser + geometry; 390 px screenshot of the
  page with the widget in the report.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/migrations/0030_booking_hold.sql` | create | hold table (dates range, apartment, expires_at) |
| `App/app/property_page.py` | edit | availability check reusing the calendar logic; hold create/release |
| `App/app/routes/property_page.py` | edit | widget render; POST availability + total; checkout start |
| `App/app/stripe_checkout.py` | create | thin wrapper: Payment Link/Checkout Session on the connected account (calls through `stripe_connect._api()` — cap counted) |
| `App/app/templates/property_page/*` | edit | the Book card, itemized panel, request path |
| `App/app/scheduler.py` | edit | hold sweep job |
| `App/tests/test_booking_widget.py` | create | availability, total math, hold lifecycle, no-JS path, state gating |
| `docs/context/status.md`, `test-map.md` | edit | Now line; row gains the widget tests |

## 4. Steps

1. Widget render gating (published + Stripe `complete`); form with
   dates/guests; no-JS POST.
2. Availability validation + itemized total via the existing stay-fee
   logic; confirmation panel.
3. Hold table + create/release + scheduler sweep (or defer to 0435).
4. "Continue to payment": Stripe Checkout Session on the host's connected
   account; webhook `checkout.session.completed` flips the row to paid
   (extend `process_event` — the connected-accounts destination endpoint
   from 0428's owner steps).
5. "Send a request" path: draft row + host mail via existing `mail.enqueue`.
6. Tests per §3; browser + geometry; screenshots.

## 5. Do not touch

`stripe_connect.py` internals (call it, don't edit it — if a change is
needed, stop and ask), `guest_guide_import.py`, `requirements.*`.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_booking_widget.py
tests/test_property_page.py tests/test_stripe_connect.py
tests/test_payment_request_model.py -q --tb=short -x 2>&1 | tail -30`
plus the design row (page templates changed).

## 7. Acceptance

- [ ] Widget only on published pages with a complete Stripe account.
- [ ] Dates/guests/total all work without JavaScript.
- [ ] Total matches the host-fee logic; itemized rows shown.
- [ ] Hold created/released/swept (or explicitly deferred to 0435).
- [ ] `checkout.session.completed` marks paid; replay dedupes (0428 table).
- [ ] Browser + geometry 0 skipped; 390 px screenshot in the report.

## 8. Stop and ask

- If `stay_fees` cannot express the public total (e.g. no nightly price on
  the property yet) — the widget needs a host-set nightly price field and
  that is a schema decision.
- If Stripe requires Apple/Google Pay domain registration steps (owner
  action, plan §1 item 3 R3/R19).
- Before any edit to `stripe_connect.py`.

## 9. Report

`docs/tasks/0434-report.md` (600 tokens at most): files, commands' last 5
lines, screenshot, deviations, owner steps. `Status: review`. Do not push.
