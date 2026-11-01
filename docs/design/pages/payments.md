# Page: Payments (`/payments`, template `payments.html`; consent `/payments/consent`, template `payments_consent.html`)

Master version: 2.0.0. This file adds; it never overrides MASTER.md. Keep it under 40 lines. No px, no colours.

## Identity
- nav: `payments`
- body_kind: `list` (`/payments`), `form` (`/payments/consent`)
- title key: `payments.title`; meta: none
- back link: none

## Header
- primary action: none (the setup card carries the one primary button while payments are not on)
- secondary actions: none
- tabs: none

## Body
- section 1, `payments.connect.title`: while Stripe is not complete, the guided setup (0625). One lead line (state copy), then 4 step cards in the existing `setup-wizard-checklist host-property-grid` list with `host-property-card host-property-card-static setup-summary-card` (same markup as the setup wizard summary, no new CSS):
  1. `payments.setup.step.consent` (done when the 0624 consent is recorded)
  2. `payments.setup.step.details` (done when a business entity exists; shows the name and e-mail we send to Stripe, link to `/entities`)
  3. `payments.setup.step.stripe` (todo, Stripe is checking, or needs you)
  4. `payments.setup.step.live`
- then exactly one primary button: the first unfinished step (consent -> `/payments/consent`, details -> `/entities`, Stripe -> `/payments/connect/start` with `target=_blank`, which also keeps it out of prefetch).
- complete: one green badge `payments.connect.complete` and the tip; rejected/disabled: state copy + support line.
- section 2: new payment request form; section 3: request list.
- badges used: `done` (step done), `attention` (Stripe needs you), `neutral` (to do / Stripe is checking).
- host copy never says Connect, KYC, payout or webhook.

## Empty state
- request list: `payments.list.empty_title`, `payments.list.empty`, no action

## Tests
- test-map row "Payments dashboard + rails" plus the design row; screenshot 390 of the setup card (`docs/tasks/screenshots-0625/`).
