# Direct payments & payment requests — build plan (folded into the existing app)

Status: **draft for owner approval** — nothing below is built yet.
Decision (owner, 27 Oct 2026): fold into the existing FastAPI codebase. Simplicity first: intuitive UX, extremely easy setup and use — "leading babies or old people." Everything non-obvious goes into `?` help popovers, never into the main flow. Reconciliation review against the shipped product is in `ubyhost-complete-stripe.md` (top of file, read-first block).

Source of truth for payments architecture, charge patterns, and legal positions: `ubyhost-complete-stripe.md` (Parts 1–2, §12–§13). This plan only decides *how it maps onto the codebase*.

## 0. What exists already (do not rebuild)

| Exists | Where | Reuse in this plan |
|---|---|---|
| SPAYD QR payload + PNG generation | `App/app/payments.py` (`spayd()`, `qr_png_bytes()`) | QR rail requests, as-is |
| Czech account parsing/validation | `payments.py` (`czech_account_parts`, `normalise_account`) | Host payout IBAN entry |
| Invoice engine, stay-linked | `invoices.py`, `invoice_pdf.py`, `routes/invoices.py` | Auto-created faktura draft per confirmed request |
| Bank statement import + VS matching | `bank_import.py` (ČSOB GPC/ABO/CSV) | QR-rail reconciliation pattern (and possible reuse) |
| Stays, guests, e-kniha, stay fees, Ubyport | `stay_fee*.py`, routes | Untouched; payment requests link to `reservation` |
| Mail outbox (idempotent, kinds) | `mail.py`, `email_outbox` | Guest/host notifications |
| Auth, access control, audit log | `auth.py`, `access.py`, `audit` table | Request pages behind token links |
| Scheduling | `scheduler.py` | Expiry sweeps, payout trigger |
| Legal acceptance records | `legal_acceptance` table | Terms tick logging at checkout |

**Zero Stripe and zero Apify code exists today.** Both are new.

## 1. Scope — what we build, in build order

Owner's read (27 Oct): most money flows through **host-created payment links**, not page bookings. Build order reflects that: requests first, bookings second.

### Phase 1 — Payment requests (the front door)
Host picks a stay (or no stay) → amount + reason → chooses rail: **Card link (Stripe)** or **QR (SPAYD)** → guest pays → confirmation lands in the dashboard.

1. **DB migration** (`db.py` + migration): `payment_request` table — `id, apartment_id?, reservation_id?, host fields (reason, amount, currency, note), rail (card|qr), status (draft|sent|awaiting_payment|paid|expired|cancelled), variable_symbol, stripe_ids (payment_link_id, session_id, payment_intent), guest_email, expires_at, created_at, updated_at`. Index on VS; unique VS per host scope.
2. **Stripe Connect account provisioning** (`app/stripe_connect.py`): create Express account (prefilled from `legal_entity`), Account Links onboarding (hosted mode first), webhook handler (`account.updated`, `payment_link`, `checkout.session.completed`, `charge.dispute.created`), requirements-hash mirror into `stripe_account` table (`charges_enabled`, `payouts_enabled`, `requirements` JSON). Test mode behind env flag; sandbox keys.
3. **Card rail**: Payment Link creation on the host's connected account (application fee 0), automatic Stripe receipt (no code), webhook → `paid`. Per-account Apple/Google Pay domain registration in the provisioning pipeline (R3/R19).
4. **QR rail**: reuse `payments.py.spayd()` with a fresh VS; guest-facing page shows QR + limits disclosure (no buyer protection, irrevocable, ubyhost is only the technology provider). Host confirms receipt in one tap; auto-create the invoice draft from the stay data on confirmation (one-active-invoice-per-stay rule respected; hosts without a stay get a manual-stay prompt per existing D2 rule).
5. **Request UX**: one screen, three fields max (stay, amount, reason), big rail toggle, giant Send button. Statuses in plain Czech with `?` popovers for: VS matching, payout timing, Stripe's role, QR limits. Host dashboard card list like the existing invoices list.
6. **Notifications**: guest gets the request (email with link/QR PNG), host gets `paid`/`expired`/`dispute` mails via existing `mail.enqueue` kinds. Idempotency keys `payment_request:{id}:{event}`.

### Phase 2 — Booking checkout on the property page
7. Property page booking widget (dates → itemized total incl. stay-fee pass-through → booking-contract panel → Checkout Session). Instant book = payment mode; request-to-book = setup mode save + off-session charge on host approval (R1), with the notify-and-reauth path (R2) and **no silent expiry** — both parties notified, approval voided, dates freed (owner decision 27 Oct).
8. Booking holds: 15-min checkout hold, 24h request hold, DB-level range exclusion (per launch-readiness §2).
9. Smart payout trigger: `min(check_in − host_setting_days, payment + 80 days)`, default host setting 7, configurable 0–14 (0 = immediate). Payout state surfaced in our dashboard; hosts never need Stripe's dashboard.
10. Terms-acceptance records: booking-contract panel text + cancellation template version + tick + timestamp stored with the booking (`legal_acceptance`-style row) — the chargeback evidence pack source.

### Phase 3 — Evidence, expiry, edge paths
11. Dispute evidence pack: auto-compiled from stored acceptance records + booking details; host notified with Express Dashboard link (host-managed disputes, we don't adjudicate).
12. Expiry sweeps (`scheduler.py`): requests expire per `expires_at`; expired-hold notifications to both parties.
13. Page generator + Apify import: **deferred — separate plan.** The deterministic URL→page mapper and scraper orchestration are a separate workstream; this plan covers the payments product only.

### Explicitly out of scope (this plan)
- Deposits/damage-fee off-session charges — **blocked until Stripe answers MCC Q3** (question set in `ubyhost-complete-stripe.md`, "Still open" 1b).
- Czech bank buttons (Comgate hybrid), SEPA DD, Pay by Bank, Instant Payouts button, Stripe Invoicing orchestration, white-label embedded onboarding upgrade.

## 2. New dependencies

`stripe` (official Python SDK) — the only new package. Apify client deferred with the page-generator workstream. Everything else uses what's installed (qrcode, reportlab, jinja2, APScheduler, boto3…). Requirements go through the repo's `requirements.lock` hashed-install process.

## 3. UX rules (owner directive: babies and grandmas)

- Defaults everywhere: reason list as one-tap chips (repair contribution, extra guest, late checkout, cleaning, damage, custom), amount pre-filled from the stay's extras where possible. Doing nothing = a complete sane request.
- Max 3 fields visible before the first button. Advanced anything lives behind `?`.
- Every `?` popover: one short Czech sentence + optional "learn more" link. No walls of text in the main UI.
- All payment state in *our* dashboard, in plain Czech ("Peníze jsou na cestě — přijdou na váš účet cca za 3 pracovní dny"). Hosts never visit Stripe except the one-time onboarding redirect.
- The Stripe onboarding redirect is the only Stripe-branded step; the dashboard explains it before the host clicks ("Jednorázově vás pošleme na stránky Stripe — je to jejich formulář, my vaše údaje nevidíme").
- QR request page: limits disclosure directly under the QR, normal weight, Czech first.

## 3b. i18n

All new UI copy follows the existing CS/EN/VI i18n pattern (`*_i18n.py` modules, e.g. `terms_i18n.py`); Czech is the lead language, and every `?` popover exists in all three.

## 4. Legal ties (for the lawyer — already drafted)

- QR rail technology-provider position: `ubyhost-complete-stripe.md` Part 3 Appendix D item 11b.
- Stripe onboarding no-relationship note: Appendix D item 12b.
- Signup ticks E1–E8, booking-contract panel, acceptance logging: Part 3 Appendices E–A.
- MCC questions Q1–Q7 sent to Stripe **before Phase 2's approval-charge work** (Q3 blocks deposits only).

## 5. Phasing & sequencing

| # | Deliverable | Depends on | Rough effort |
|---|---|---|---|
| P1.1 | Migration + `payment_request` model | — | small |
| P1.2 | Stripe Connect module (sandbox) + onboarding flow | P1.1 | medium |
| P1.3 | Card-rail requests (Payment Links) | P1.2 | small-medium |
| P1.4 | QR-rail requests + confirm + invoice-draft trigger | P1.1 | medium |
| P1.5 | Request UX + notifications + `?` system | P1.3, P1.4 | medium |
| P2.1 | Booking checkout widget + holds | P1.2 | large |
| P2.2 | Request-to-book pattern + re-auth + no-silent-expiry | P2.1 | large |
| P2.3 | Smart payout trigger + settings | P1.2, P2.1 | medium |
| P3 | Evidence pack, expiry sweeps, disputes mail | P2 | medium |

A dev works strictly top-down. Each deliverable ships behind the repo's brief/task process (`docs/tasks/NNNN-*.md`, TEMPLATE.md) with tests per the [test-map](../context/test-map.md) for the changed area.

## 6. Verification per deliverable

- Every phase lands with pytest coverage in the established style (`App/tests/test_04xx_*.py` numbering), including Stripe webhook signature verification and idempotent handler tests.
- Sandbox go-live checklist from the plan (onboarding triggers, dispute sims, payout test clocks, two-layer pause test, live-mode dry run) runs before production activation — full list in `ubyhost-complete-stripe.md` launch-readiness §8.

## 7. Open items for the owner

1. **Approve this plan** (or amend).
2. Stripe prep — see the checklist in the next message.
3. Confirm the reason-chip list (§3) matches what hosts actually ask for.

---

Companion artifacts: `ubyhost-complete-stripe.md` (architecture/legal truth), `stay-fee-remittance/PLAN_STAY_FEE_REMITTANCE.md` (untouched), `stay-only-invoices.md` (invoice rules this plan respects).
