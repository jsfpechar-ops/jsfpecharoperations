# 0429: Payments dashboard — connect state, request screen, `?` system (P1.5)

Status: review
Depends on: 0425, 0428 (merged) | Base commit: after #550 | Branch: task/0429-payments-ux
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

The host-facing half of direct payments, phase 1: a Payments section in the
dashboard that shows the Stripe Connect state from the mirror (with the "return
is not verified" copy), the one-time connect button (already routed at
`/payments/connect/start`), and the request-creation screen — stay, amount,
reason, rail toggle — writing `draft` rows into the existing `payment_request`
table. No Stripe calls beyond the connect flow that 0428 already ships: the card
rail (Payment Links) is P1.3, this brief only stores the draft and shows the list.

## 2. Context

- All backend pieces exist: `payment_request` model (0425, migration 0026),
  `App/app/stripe_connect.py` + routes (0428, merged as #550). Read them before
  writing templates.
- The connect button posts to `/payments/connect/start` (CSRF-protected POST,
  303 to the single-use Stripe link). Disabled with a calm explanation while
  `config.STRIPE_MODE` is off or the mirror state is `complete`/`rejected`/`disabled`.
- Mirror states and their copy (cs/en, plain words, rule 9 — no sentence the
  button already says):
  - `pending`: "Stripe is preparing your account."
  - `action_required`: "Stripe needs one more thing from you." + button "Open Stripe"
  - `complete`: "Payments are on." + `?` popover "Ready means Stripe verified the host. Guests pay the host's Stripe account directly."
  - `rejected`/`disabled`: calm one-liner + contact-support line.
- The `?` popover system: one per page section, `<details>` based, works without
  JavaScript (rule 6), styled like the existing popovers (see
  [MASTER](../design/MASTER.md), component section). Three popovers in this
  brief: "What is Stripe?", "When do I get paid?" (payout timing, from the
  plan §3 UX rules), "What does the guest see?"
- Request screen: stay (or no stay), amount (CZK), reason (chip list from the
  plan §3), rail toggle Card/QR (QR selectable only if the row schema's rail
  allows it; both disabled with one-line why while P1.3/P1.4 are not shipped).
  Drafts: `INSERT` with status `draft`, one flash "Draft saved."
- Request list: dashboard card list like the invoices list; draft/sent/paid
  states in plain Czech; empty state "No payment requests yet."
- Rule 7 applies: browser + geometry tests for every changed page, 0 skipped,
  one 390 px screenshot per page in the report.
- Route conventions: host router under `security.protect_host_post`,
  `auth.require_login(request)` guard, `access.owner_id(request)` — copy the
  pattern in `App/app/routes/stripe_connect.py`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/payments.py` | create | payments section: connect card + request form + list |
| `App/app/templates/payments/*.html` | create | section, request form, list, popovers |
| `App/app/templates/<dashboard shell>` | edit | nav entry "Payments" |
| `App/tests/test_payments_dashboard.py` | create | route + form + mirror-state copy tests, browser/geometry per rule 7 |
| `docs/context/status.md`, `test-map.md` | edit | Now line; payments row gains the dashboard tests |

Do not touch `App/app/stripe_connect.py`, its routes, or any migration. No new
dependency. No guest-page or public-host file changes.

## 4. Steps

1. Read 0428's report and `stripe_connect.py`; read the invoices list template
   for the card-list pattern; read MASTER for the popover component.
2. Payments route + section template: connect state card (reads
   `stripe_connect.account_for_owner(owner_id)`), request form, list.
3. POST /payments/requests/new → validate (amount > 0 CZK, reason from the chip
   list, stay owned by the host), `INSERT` draft, flash, redirect back.
4. `?` popovers per §2, `<details>`-based, no JS.
5. Nav entry; empty states; cs/en copy (one explanation lives in one place,
   rule 9).
6. Tests: template render per state (5 mirror states), form validation, draft
   insert, list ordering, no-JS popover presence; browser + geometry suite with
   0 skipped; screenshots at 390 px.

## 5. Do not touch

`stripe_connect.py`, `routes/stripe_connect.py`, migrations, `requirements.*`,
guest/public templates, `retention.py` (no new personal data: guest_email is
already covered).

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_payments_dashboard.py
tests/test_payment_request_model.py tests/test_stripe_connect.py
tests/test_design_guardrails_browser.py -q --tb=short -x 2>&1 | tail -30`

## 7. Acceptance

- [ ] All five mirror states render the right copy; connect button appears only
      in `pending`/`action_required`.
- [ ] Draft creation works; invalid amount/reason refused with a flash.
- [ ] Browser + geometry tests 0 skipped; 390 px screenshots in the report.
- [ ] Popovers work without JavaScript.
- [ ] Test-map row updated; lint OK.

## 8. Stop and ask

- If the chip list (reasons) needs new values beyond the plan §3 list.
- If the mirror row shape forces a template change beyond the five states.

## 9. Report

`docs/tasks/0429-report.md` (600 tokens at most): files, commands' last 5 lines,
screenshots, deviations, owner steps. Set `Status: review`. Do not push.
