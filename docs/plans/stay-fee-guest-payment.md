# Stay fee collected from guests at the end of the guest flow ("city tax" pay step)

Status: **scoped with the owner, build not started.** Owner decisions of
2026-11-03 are in §1. Nothing below is built yet.

Product frame: the municipal stay fee (poplatek z pobytu) is owed to the
obec, but under zákon č. 565/1990 Sb. the **host collects and remits**. Some
hosts let Airbnb/Booking collect it at booking; others collect it themselves.
UbyHost already **counts** the fee per signed guest (`App/app/stay_fee.py`).
This feature lets the guest **pay the host** at the end of the registration
flow, and lets the host see what was collected vs what is due for remittance.
UbyHost never receives or holds funds — same stance as the payment-request
rails (plan `direct-payments-build-plan.md`, brief 0425).

## 1. Owner decisions (2026-11-03)

1. **Payee = the host's account.** The guest pays the host (IBAN/Revolut/Stripe
   link on the host), the host remits to the council as today. Not the
   council account, not configurable per property.
2. **Revolut rail = a host-pasted Revolut payment link, not the merchant SDK
   in v1.** A regular (personal) Revolut account can create a payment link in
   the Revolut app; anyone can pay it by card from the browser — that is the
   "just click and a Revolut payment link pops up" the owner wants. Creating
   links programmatically with the exact amount + automatic "paid" webhooks
   requires a Revolut **Business** merchant API connection; that is phase 3,
   optional. The Revolut Merchant Web SDK (embedded button) is **not** used:
   it would be a third-party script on a guest page (repo rule 2) for no
   benefit over a plain link.
3. **Timing = once per stay, when all expected guests are registered.** The pay
   panel lives on the guest stay hub (`guest/stay.html`), shown when there is
   an unpaid balance and at least one signed guest. When someone is added
   later via the magic link (`/another` → `/new` → save), the panel reappears
   with the updated total — "smart": a pending charge is recomputed live, and
   a paid charge plus a new guest opens a new charge for the delta only.
4. **v1 scope = all three rails at once: IBAN/QR (most important), cash,
   Revolut link.** The existing Stripe card rail is added in phase 2 (it
   already exists and gives automatic webhook-paid marking for international
   card payers).
5. Per-property **toggle + rail checkboxes** in the property fee section
   (rendered both on the property page and in the onboarding wizard's property
   step, same place as the passport/OCR toggles), behind a global env kill
   switch `UBYHOST_STAY_FEE_GUEST_PAY=off|on` (default off).

## 2. What exists — reuse map

| Piece | Where | Reuse |
|---|---|---|
| Fee counting: rate/cadence/council fields on `apartment`; per-guest liable/exempt nights incl. minor exemption, host `fee_host_decision`, >60-night rule | `App/app/stay_fee.py` (`guest_period()`, `is_active()`, `clamp_rate()`, `MAX_RATE_CZK=50`) | `charge_for_reservation()` sums `guest_period()` over the whole stay per signed guest |
| SPAYD QR + IBAN helpers | `App/app/payments.py` (`spayd()`, `qr_png_bytes()`, `normalise_account()`, host `legal_entity.iban`) | IBAN/QR rail on the pay panel; VS = zero-padded charge id |
| Stripe card rail on the host's connected account + signed webhook | `App/app/payment_links.py`, `App/app/stripe_connect.py`, `routes/stripe_connect.py` `/webhooks/stripe` | Phase 2: mint a Payment Link per charge, webhook marks the charge paid |
| Public token-scoped guest pages, POST-then-plain-link pattern (CSP form-action, 0730/0761) | `routes/payments.py` `/pay/{id}/{token}`, `/payments/requests/{id}/link`→`/share` | Pay actions are POSTs that store state and re-render; external pay URLs are plain `<a>` links — **no third-party script, no CSP change** (`main.py:216`) |
| Guest hub + add-person flows | `routes/guest.py` (`/l/{token}/{reservation_id}`, `/party`, `/another`, `/save` → `?saved=1`), `templates/guest/stay.html` (fixed card order: status → next action → **money** → records → footer) | Pay panel is the "money" card |
| Per-property toggles | `apartment.ocr_scan` (migration `0035` + pg twin `migrations_pg/00005`), `passport_photo_policy`, gated in `_form_context` | Same pattern: new apartment columns + gate in guest routes |
| Property editor / wizard | `templates/_property_editor.html` (fee section includes `_stay_fee_fields.html`; passport/OCR in more-options), saved via `routes/admin.py` + `routes/stay_fees.py::fee_form_values` | Toggle UI goes into `_stay_fee_fields.html` → appears on the property page and the wizard property step automatically |
| Migrations | `App/app/migrations/00NN_*.sql` + twin `App/migrations_pg/000NN_*.sql` (next: `0036` / `00006`) | New columns + one table |
| i18n | guest copy `App/app/i18n.py` (en/cs/de/es/fr) + `guest_uk_i18n.py` (uk); host copy `host_i18n.py` | New keys, all 6 guest languages |
| Audit, mail outbox, retention | `db.audit`, `mail.enqueue`, `retention.py` + `docs/privacy/RETENTION.md` | Audit every status change; retention row for the new table (6 years, aligns with the house-book duty — counsel to confirm) |

## 3. Data model (migration `0036` + pg twin `00006`)

```sql
-- apartment: master switch, allowed rails, host-pasted Revolut link, guest note
ALTER TABLE apartment ADD COLUMN stay_fee_collect INTEGER NOT NULL DEFAULT 0;
ALTER TABLE apartment ADD COLUMN stay_fee_guest_rails TEXT NOT NULL DEFAULT '';  -- csv subset of 'qr','cash','revolut','card'
ALTER TABLE apartment ADD COLUMN stay_fee_guest_revolut_link TEXT;                -- validated https revolut.com URL
ALTER TABLE apartment ADD COLUMN stay_fee_guest_note TEXT;                        -- optional instruction shown on the pay panel

-- one row per chargeable event on a stay (one active 'pending' at a time)
CREATE TABLE stay_fee_charge (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    apartment_id     INTEGER NOT NULL REFERENCES apartment(id) ON DELETE CASCADE,
    reservation_id   INTEGER NOT NULL REFERENCES reservation(id) ON DELETE CASCADE,
    amount_czk       INTEGER NOT NULL CHECK (amount_czk >= 0),
    liable_nights    INTEGER NOT NULL DEFAULT 0,
    rate_czk         INTEGER NOT NULL DEFAULT 0,
    rail             TEXT NOT NULL DEFAULT '' CHECK (rail IN ('','qr','cash','revolut','card')),
    status           TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending','cash_declared','paid','waived','cancelled')),
    variable_symbol  TEXT,          -- qr rail: zero-padded id, unique by construction
    stripe_payment_link_id TEXT,    -- card rail (phase 2)
    stripe_link_amount_czk INTEGER, -- amount the live link was minted for
    paid_at          TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE INDEX stay_fee_charge_reservation ON stay_fee_charge(reservation_id, status);
```

Design note: `payment_request` was considered and **rejected** for this — its
`reason`/`rail` CHECK constraints would need a table rebuild, it is
host-initiated with a manual amount, and the fee charge must feed the fee
register as "collected". `stay_fee_charge` is self-contained; the payments
list can join it later (phase 3).

## 4. Charge computation ("smart" rules)

New `stay_fee.charge_for_reservation(apartment, reservation)`:

- Only **signed, non-archived guests** on an **active, non-demo** reservation
  count (same predicate as `_GUESTS_SQL` in `stay_fee.py`) — consistent with
  the fee register, which counts signed forms only.
- Per guest: `guest_period(guest, reservation, stay_from, stay_to)` over the
  **whole stay** (first=start, last=end) → `liable_nights × rate`. Minors,
  host-`exempt`, and >60-night stays contribute 0 automatically.
- Charge amount = live sum while `pending`; stored snapshot refreshed on each
  hub render. If `paid` and the party grows, a **new** charge is opened for
  `new_total − sum(paid charges)` — never silently edit a paid row.
- If a pending charge already has a live Stripe link and the amount changed,
  the link is dropped (amount is immutable per link) and re-minted on the next
  card-pay click (`stripe_link_amount_czk` guards this).

## 5. UX

**Property settings + wizard.** In the fee section (`_stay_fee_fields.html`):
a switch "Collect the stay fee from guests" (`stay_fee_collect`), rail
checkboxes (Bank transfer QR / Cash / Revolut link / Card), the Revolut link
URL field (validated: https + host `revolut.com` or subdomain — a pasted
arbitrary URL on a guest page would be a phishing vector), and an optional
note shown to guests. Saved through the existing `fee_form_values()` +
`routes/admin.py` apartment save path, so it works identically from the
property page and the onboarding wizard's property step (same editor partial,
where the passport/OCR toggles live). When the global env switch is off, the
controls render disabled and guest pages never show the panel.

**Guest form (`guest/form.html`).** One-line notice at the bottom of the form
when the property collects: "Municipal stay fee: about X CZK per person for
this stay — you'll pay it once after everyone is registered." Estimate from
the currently entered dates/birth date (same math, un-saved values).

**Guest hub (`guest/stay.html`).** New "money" card in the fixed order
(status → next action → money → records). Shows when `charge_for_reservation`
yields an unpaid balance > 0 and ≥1 signed guest: total, per-person breakdown
(nights × rate), and the rails the host allowed:

- **Bank transfer (QR)** — inline SPAYD QR PNG + IBAN/VS/message to copy
  (host's `legal_entity` IBAN; VS = charge id). Status stays `pending` until
  the host marks received (bank-statement VS matching in phase 3).
- **Cash** — POST "I'll pay in cash" → `cash_declared`; host marks received.
- **Revolut** — plain `<a class="g-btn" href="…revolut link…" rel="noopener">`
  (external navigation, CSP-safe) + copy "you'll confirm receipt with the
  host". Host marks received.
- **Card (phase 2)** — POST creates/reuses the Stripe Payment Link on the
  host's connected account (lazy, at click time, amount = current charge),
  then re-renders with the link as a plain button; webhook
  `checkout.session.completed` with `payment_status == paid` marks the charge
  `paid` (extend `payment_links.on_paid` to look up `stay_fee_charge` by
  `stripe_payment_link_id`).

If the balance is 0 or fully paid, the card collapses to a one-line "Stay fee
paid ✓" (or nothing when the fee doesn't apply). Adding a person via the
magic link re-renders the hub after save → the panel is back with the new
total. All guest POSTs reuse `_throttle_guest_post` and the existing
token/PIN/claim guards; no new public surface beyond the hub POSTs.

**Host side.** Stay-fees pages (`routes/stay_fees.py`): per-period
"collected from guests" = sum of `paid` charges in the period, shown next to
the amount due for remittance; per-stay charge rows with **Mark received** /
**Waive** actions (status transitions + `db.audit`, mirroring
`payment_request._TRANSITIONS`). Phase 3 adds the "collected" column to the
register CSV and the remittance PDF.

## 6. Compliance / privacy

- No third-party scripts: Stripe and Revolut are plain external links; the QR
  is our own PNG. No CSP change in v1. The Revolut Merchant SDK stays out
  (would need a `script-src` exception + decisions entry — not worth it).
- Pay-panel copy must state: the fee is owed to the municipality, **you pay
  the host**, the host remits it; card payments are processed by Stripe/Revolut
  on the host's account — ubyhost never sees funds. Copy goes through the
  legal review path (`docs/POPLATEK_Z_POBYTU.md` open questions,
  `docs/UbyHost_workplan/04_legal_positions.md`).
- `retention.py` + `docs/privacy/RETENTION.md`: new row for
  `stay_fee_charge` — 6 years from stay end (aligns with the §101
  house-book/fee-register duty; **counsel to confirm**), purged with the
  reservation cascade.
- i18n: guest keys in all 6 languages; host keys in `host_i18n.py`.

## 7. Phases and files

**Phase 0 — model + toggle.** `migrations/0036_stay_fee_guest_pay.sql` +
`migrations_pg/00006_…sql`; `config.py` (`UBYHOST_STAY_FEE_GUEST_PAY`, default
off), `.env.example`, `docs/ENVIRONMENT.md`; apartment columns; toggle UI in
`_stay_fee_fields.html` + `fee_form_values()` + admin save; kill-switch gate.

**Phase 1 — core (the three rails).** `stay_fee.charge_for_reservation()`;
`stay_fee_charge.py` (create/refresh/status/audit); hub card in
`routes/guest.py` + `templates/guest/stay.html` + new `guest/_fee_pay.html`;
form notice in `guest/form.html`; guest POST endpoints (choose cash, show QR —
QR PNG endpoint token-scoped like `/pay/{id}/{token}.png`); host
mark-received/waive in `routes/stay_fees.py` + templates; "collected" on the
stay-fees list; i18n; `retention.py` row.

**Phase 2 — card rail + notifications.** Stripe Payment Link per charge
(lazy mint, `stripe_link_amount_czk` guard), webhook extension in
`payment_links.on_paid` / `routes/stripe_connect.py`; Revolut link rail
already in phase 1 — here: guest receipt + host "fee paid" mails via
`mail.enqueue`.

**Phase 3 — reconciliation & reporting.** `bank_import.py` VS matching for
`stay_fee_charge.variable_symbol`; register CSV + remittance PDF "collected"
column; payments-page join; optional Revolut Business API (amount-specific
links + webhooks — only if a host asks; needs Business account); analytics.

**Tests & gates.** Test-map rows for guest pages, `stay_fee`, payments;
browser + geometry tests and one 390 px screenshot per changed guest page
(rules 7/10); `scripts/context_lint.py`; no new dependency in v1 (phase 2
reuses `stripe`; phase 3 Revolut API would be plain HTTP, rule 4 decision
line needed).

## 8. Explicitly out of scope

- Guest paying the council directly; platform merchant accounts; the Revolut
  Merchant Web SDK embedded in our page; PSP/licensing anything.
- Changing the fee **counting** rules (rate, exemptions, cadence) — untouched.
- Auto-filing anything to obec portals.
- Multi-currency: CZK only in v1.

## 9. Open questions (not blocking the plan)

1. Counsel: 6-year retention for `stay_fee_charge` (align with the fee
   register), and the pay-panel legal copy.
2. Charge expiry: leave `pending` until stay end + 30 days, then `cancelled`
   by the sweep? (Proposed default: yes, mirroring `payment_request.expire_sweep`.)
3. Should a waived/exempt outcome show on the guest hub at all, or only to the
   host? (Proposed: host only.)
