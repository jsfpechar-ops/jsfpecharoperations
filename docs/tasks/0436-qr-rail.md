# 0436: QR rail — SPAYD request, confirm, invoice-draft trigger (payments P1.4)

Status: todo
Depends on: 0429; independent of 0435 | Base commit: after 0429 | Branch: task/0436-qr-rail
Executor: Haiku 5.5 | Fits one session: 30 tool calls, 60k tokens

## 1. Objective

Sending a payment request by bank QR: reuse `payments.spayd()` with a fresh
variable symbol, show the guest a page with the QR + the legal limits
disclosure (ubyhost is only the technology provider — no buyer protection,
irrevocable), let the host confirm receipt in one tap, and auto-create the
invoice draft from the stay data on confirmation.

## 2. Context

- The plan §1 item 4 is this brief's contract. Reuse, do not rebuild:
  `App/app/payments.py` `spayd(iban, amount, vs, message, bic)` (SPAYD string),
  the QR PNG renderer (qrcode dep, existing pattern), `payment_request`
  (migration 0026, `variable_symbol`, `status`), the invoice-draft-from-stay
  path (find it via `grep -n "draft" App/app/invoices.py` — the
  one-active-invoice-per-stay rule is enforced there; reuse, do not restate).
- Host's bank details: `legal_entity` already carries the host's IBAN for
  invoices; the QR uses the host's own account (ubyhost never receives funds).
- Flow: Send on a qr-rail request → row `sent`, VS assigned (unique per host
  scope — 0026 constraint) → guest mail with a link to the payment page (not
  the QR inline: the page renders the QR PNG + amount + VS + the limits
  disclosure in the guest's language; the mail stays small).
- Limits disclosure copy (cs/en, one place — this template): "Bank transfer
  has no card protection. The payment is irrevocable and ubyhost is only the
  technology provider; the payee is {host name}." Lawyer-reviewed line —
  mark the template with the existing legal-review comment pattern.
- Host confirm: one button on the request row ("Mark as paid"); sets `paid`,
  then the invoice-draft trigger: if the request has a `reservation_id`,
  create the draft invoice from the stay data via the existing path
  (one-active-invoice-per-stay respected); no stay → flash the manual-stay
  prompt per the existing D2 rule (do not invent a new flow).
- No webhook involvement: the QR rail is bank-side; matching by VS is the
  host's bank statement vs. the row (a later brief may add statement import —
  out of scope here).
- Expiry: `expires_at` sweep marks `expired` (the sweep itself is P3; here
  only the status value and the copy exist).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/routes/payments.py` | edit | Send action rail `qr`; confirm action; QR PNG endpoint |
| `App/app/payments.py` | edit | none if `spayd()` suffices — only extend if the VS/message shape needs it |
| `App/app/templates/payments/qr_page.html` | create | guest QR page + disclosure |
| `App/app/mail.py` | edit | guest mail kind with the page link |
| `App/app/invoices.py` | edit | only the call site for the draft trigger, if the existing helper needs a parameter |
| `App/tests/test_payment_qr.py` | create | VS uniqueness, SPAYD string content, page render + disclosure, confirm → invoice draft, no-stay prompt |
| `docs/context/status.md`, `test-map.md` | edit | Now line; payments row gains `test_payment_qr.py` |

## 4. Steps

1. Send action: assign VS (unique per host), `sent`, mail with page link.
2. Guest QR page: SPAYD → QR PNG (amount, VS, host IBAN from legal_entity),
   disclosure block, guest language handling per 0344; rate-limited GET.
3. Host confirm action: `paid` + invoice-draft trigger via the existing
   helper; no-stay prompt copy.
4. Tests per §3; browser/geometry row for the new guest page; 390 px
   screenshot of the QR page in the report.

## 5. Do not touch

`stripe_connect.py` (no Stripe in this rail), `spayd()` internals, the
invoice one-active-per-stay rule, `requirements.*`, migrations.

## 6. Commands

From `App/`: `.venv/bin/python -m pytest tests/test_payment_qr.py
tests/test_payment_request_model.py tests/test_payments_dashboard.py
tests/test_design_guardrails_browser.py -q --tb=short -x 2>&1 | tail -30`

## 7. Acceptance

- [ ] QR page renders SPAYD QR with amount + VS + host IBAN; disclosure
      present in cs/en; no-JS (the QR is an image).
- [ ] VS unique per host; mail sent once per send.
- [ ] Confirm → `paid` + invoice draft on the stay (rule respected);
      no-stay prompt otherwise.
- [ ] Browser + geometry 0 skipped; 390 px screenshot in the report; lint OK.

## 8. Stop and ask

- If `legal_entity` has no IBAN for a host (copy: the host must add bank
  details first — check the existing settings copy before writing new).
- If the invoice-draft helper cannot be called from the payments route
  cleanly (report the seam; do not refactor invoices).

## 9. Report

`docs/tasks/0436-report.md` (600 tokens at most): files, commands' last 5
lines, screenshot, deviations, owner steps. `Status: review`. Do not push.
