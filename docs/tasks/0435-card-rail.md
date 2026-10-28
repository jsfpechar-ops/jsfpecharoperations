# 0435: Card rail — Stripe Payment Links on the host's account (payments P1.3)

Status: review
Depends on: 0428 (#550 merged), 0429 shipped or in flight | Base commit: after 0429 | Branch: task/0435-card-rail
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Sending a payment request by card: when the host sends (or re-opens) a
`payment_request` with rail `card`, create a **Stripe Payment Link** on the
host's connected account (application fee 0 — the host is merchant of record),
store the link, and let the guest pay it. Stripe's receipt is automatic (no
code); our webhook flips the row to `paid`.

## 2. Context

- Everything rails need already exists: `stripe_connect._api()` (cap counted),
  the `payment_request` table (migration 0026, columns `stripe_payment_link_id`,
  `guest_email`, `expires_at`, `status`), the webhook endpoint with dedupe
  (0428, `stripe_webhook_event`).
- Payment Links live in the **connected-accounts destination** endpoint (0428's
  owner step registered it). Events needed here: `payment_link.paid` — or, if
  the account's link config differs, `checkout.session.completed` with the
  link id in the payload. [verify] which event fires for a Payment Link on a
  connected account during the first test-mode run; record it in the report.
- Creation: `stripe.PaymentLink.create` with `line_items=[{price_data: {currency: 'czk', unit_amount, product_data: {name: reason}}}, quantity=1]` on the connected account (`stripe.Account.create`-style client use; every call goes through `stripe_connect._api()` — never set `api_key` directly). Amounts are CZK integers (haléř); the model already stores CZK.
- Flow: host hits Send on a card-rail request in the 0429 screen → link
  created → row: `stripe_payment_link_id` stored, status `sent` → the guest
  email carries the link (existing `mail.enqueue`; `payment_request:{id}:sent`
  idempotency key per the plan §1 item 6) → webhook `paid` → row `paid`,
  host mail, dashboard list refresh.
- Expiry: `expires_at` on the row; Payment Links themselves stay valid — the
  email copy says "pay by {date}" and the sweep (P3, later brief) marks the
  row `expired`; the Stripe link is allowed to outlive the row (host can
  cancel the link on dispute/edge paths later).
- Edge: no Stripe account or state != `complete` → Send refuses with the calm
  connect-first copy (0429 already renders it; do not duplicate the sentence,
  rule 9 — link to the section).
- No templates change beyond what 0429 shipped: this brief makes its Send
  button work for the card rail. If 0429 has not landed yet, land 0429 first.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/payment_links.py` | create | create-for-request, amount mapping, CZK int |
| `App/app/routes/payments.py` | edit | Send action for rail `card` |
| `App/app/stripe_connect.py` | edit | ONLY `process_event`: dispatch `payment_link`/`checkout.session.completed` events to `payment_links.on_paid` — extend, do not restructure |
| `App/app/mail.py` | edit | mail kind: guest payment link (cs/en, one explanation lives here) |
| `App/tests/test_payment_links.py` | create | creation params, state gating, webhook paid path, dedupe, mail |
| `docs/context/status.md`, `test-map.md` | edit | Now line; payments row gains `test_payment_links.py` |

## 4. Steps

1. `payment_links.py`: `create_for_request(request_row)` → PaymentLink on the
   connected account; store id; amount = row amount × 100.
2. Send action: state gate (Stripe `complete`), `sent` + mail with the link;
   idempotency key on the mail kind.
3. Webhook: extend `process_event` dispatch; `paid` → row `paid` + host mail.
   Replays dedupe via the existing event table (no change needed — test it).
4. Tests: creation params (fee 0, CZK, reason as product name), refusal when
   Stripe off/incomplete, webhook flip, replay no-op, mail sent once.

## 5. Do not touch

`stripe_connect.py` beyond the `process_event` dispatch line; migrations
(0026 has the columns); `requirements.*`; guest/public templates.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_payment_links.py
tests/test_payment_request_model.py tests/test_stripe_connect.py
tests/test_payments_dashboard.py -q --tb=short -x 2>&1 | tail -30`

## 7. Acceptance

- [ ] Card-rail Send creates a Payment Link on the connected account, fee 0.
- [ ] Guest mail carries the link exactly once per send.
- [ ] Webhook flips `sent` → `paid`; replay is a no-op.
- [ ] Refused when Stripe off/mirror not `complete`, with existing copy.
- [ ] Tests pass; lint OK.

## 8. Stop and ask

- [verify] If the paid event for Payment Links on connected accounts differs
  from both candidates (record the exact event and payload shape).
- If Payment Links require a hosted `after_payment` redirect config (owner
  decision needed for the return URL).

## 9. Report

`docs/tasks/0435-report.md` (600 tokens at most): files, commands' last 5
lines, the verified event name, deviations, owner steps. `Status: review`.
Do not push.
