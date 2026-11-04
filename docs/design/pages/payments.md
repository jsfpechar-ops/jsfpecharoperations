# Page: Payments (`/payments`, template `payments.html`; new request `/payments/new`, template `payments_new.html`; consent `/payments/consent`, template `payments_consent.html`)

Master version: 2.0.0. This file adds; it never overrides MASTER.md. Keep it under 40 lines. No px, no colours.

## Identity
- nav: `payments`
- body_kind: `list` (`/payments`), `form` (`/payments/new`, `/payments/consent`)
- title key: `payments.title` (`/payments/new`: `payments.new.title`); meta: none
- back link: `/payments/new` back to `/payments`; none on `/payments`

## Header
- primary action: `payments.new.title` -> `/payments/new`, only when Stripe is complete (while payments are not on, the setup card carries the one primary button)
- secondary actions: none
- tabs: none

## Body
- setup, `payments.connect.title`: while Stripe is not complete, the guided setup (0729). One lead line (state copy), then 4 step cards in the existing `setup-wizard-checklist host-property-grid` list with `host-property-card host-property-card-static setup-summary-card` (same markup as the setup wizard summary, no new CSS):
  1. `payments.setup.step.consent` (done when the 0624 consent is recorded)
  2. `payments.setup.step.details` (done when a business entity exists; shows the name and e-mail we send to Stripe, link to `/entities`)
  3. `payments.setup.step.stripe` (todo, Stripe is checking, or needs you)
  4. `payments.setup.step.live`
- then exactly one primary button: the first unfinished step (consent -> `/payments/consent`, details -> `/entities`, Stripe -> `/payments/connect/start` with `target=_blank`, which also keeps it out of prefetch).
- complete: one `done` badge `payments.overview.on` with `payments.overview.on_sub`, and the tip. Rejected/disabled: state copy + support line; no services or requests below.
- services, `payments.overview.services`: card table (`ui_table_begin/end`), one row per service: name, amount, actions "Request payment" (`/payments/new?service=…`) and Remove (confirm). The add form stays inline under `payments.overview.add_service` (no dialog: no catalog trigger works without JS).
- requests, `payments.overview.requests`: the same card table, one row per request: reason or note, date, amount, status badge, actions (Get link, Send, QR preview, as before). Empty: `empty_state`.
- guest QR (0763): bank-transfer e-mails use the public URL `/pay/{id}/{token}` (`payment_request.guest_token`, no login); PNG at the same path with `.png`. Host preview stays `/payments/qr/{id}`.
- share page `/payments/requests/{id}/share` (template `payments_share.html`, body_kind `detail`): reason and amount, the link in a read-only field, then Copy, Send by e-mail (secondary) and Send on WhatsApp (primary, new tab), one note, a back link.
- `/payments/new`: amount, reason chips, note, stay select (first option is no stay), guest e-mail, rail chips; one primary submit `payments.new.submit`. POST `/payments/requests/new` with unchanged field names; failed validation redirects back here.
- Redirect: `GET /payments` with `service` or `reservation_id` in the query answers 303 to `/payments/new` with the same query string.
- badges used: `done` (step done), `attention` (Stripe needs you), `neutral` (to do, Stripe is checking).
- host copy never says Connect, KYC, payout or webhook.

## Empty state
- request list: `payments.list.empty_title`, `payments.list.empty`, no action

## Tests
- test-map row "Payments dashboard + rails" plus the design row; screenshot 390 of the setup card (`docs/tasks/screenshots-0729/`).
