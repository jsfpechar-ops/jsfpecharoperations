# Stay fee pay panel — guests pay the host at the end of the guest flow

Status: **scoped with the owner, build not started.** v2 of this plan
(2026-11-03) is deliberately **lean and read-only**: UbyHost shows the fee
amount and the means to pay it; it stores no payment state and marks nothing.
"Ecological": no new tables, no sweeps, no webhooks, no retention rows, no
personal data — only four host-config columns on `apartment`.

Product frame: the municipal stay fee (poplatek z pobytu) is owed to the
obec, but under zákon č. 565/1990 Sb. the **host collects and remits**. Some
hosts let Airbnb/Booking collect it; others collect it themselves. UbyHost
already **counts** the fee per signed guest (`App/app/stay_fee.py`). This
feature lets the guest **see and pay** the host at the end of the registration
flow. UbyHost never receives or holds funds and never tracks whether the
money arrived — the host reconciles against their own account, as they
already do (same stance as the payment-request rails, plan
`direct-payments-build-plan.md`, brief 0425).

## 1. Owner decisions (2026-11-03)

1. **Payee = the host's account.** Guest pays the host (IBAN / Revolut link /
   cash), the host remits to the council as today.
2. **Revolut rail = a host-pasted Revolut payment link.** A regular (personal)
   Revolut account can create a payment link in the Revolut app; anyone can
   pay it by card in the browser. No merchant SDK, no API, no third-party
   script on our pages (repo rule 2 stays happy, no CSP change). Programmatic
   amount-specific links + "paid" webhooks would need a Revolut **Business**
   merchant API — explicitly out of scope.
3. **Timing = once per stay, on the guest stay hub, when all expected guests
   are registered.** Adding a person later via the magic link re-shows the
   panel with the recomputed total — this falls out for free because the
   amount is computed live on every render, not stored.
4. **v1 rails = IBAN/QR (most important) + Revolut link + cash note.** No card
   rail in v1 (see open questions).
5. **Lean: read-only.** No `paid`/`pending` state, no mark-received UI, no
   host actions, no webhooks, no delta charges, no "collected" columns. We
   provide the means; the host sees the money in their own account.
6. Per-property **toggle + rail checkboxes** in the property fee section
   (rendered on both the property page and the onboarding wizard's property
   step, where the passport/OCR toggles live), behind a global env kill
   switch `UBYHOST_STAY_FEE_GUEST_PAY=off|on` (default off).

## 2. What exists — reuse map

| Piece | Where | Reuse |
|---|---|---|
| Fee counting: rate/cadence on `apartment`; per-guest liable/exempt nights incl. minor exemption, host `fee_host_decision`, >60-night rule | `App/app/stay_fee.py` (`guest_period()`, `is_active()`, `clamp_rate()`, `MAX_RATE_CZK=50`) | New `charge_for_reservation()` sums `guest_period()` over the whole stay per signed guest, live at render time |
| SPAYD QR + IBAN helpers | `App/app/payments.py` (`spayd()`, `qr_data_uri()`, host `legal_entity.iban`) | QR embedded as a data URI in the panel; VS = zero-padded reservation id |
| Guest hub + add-person flows | `routes/guest.py` (`/l/{token}/{reservation_id}`, `/party`, `/another`, `/save`), `templates/guest/stay.html` (fixed card order: status → next action → **money** → records → footer) | Pay panel is the "money" card; read-only, no new POST endpoints |
| Per-property toggles | `apartment.ocr_scan` (migration `0035` + pg twin `migrations_pg/00005`), `passport_photo_policy` | Same pattern: apartment columns + gate in the guest route |
| Property editor / wizard | `templates/_property_editor.html` (fee section includes `_stay_fee_fields.html`), saved via `routes/admin.py` + `routes/stay_fees.py::fee_form_values` | Toggle UI goes into `_stay_fee_fields.html` → appears on the property page and the wizard property step automatically |
| Migrations | `App/app/migrations/00NN_*.sql` + twin `App/migrations_pg/000NN_*.sql` (next: `0036` / `00006`) | Four `ALTER TABLE` columns only |
| i18n | guest copy `App/app/i18n.py` (en/cs/de/es/fr) + `guest_uk_i18n.py` (uk); host copy `host_i18n.py` | New keys, all 6 guest languages |

## 3. Data model (migration `0036` + pg twin `00006`)

Host configuration only — no guest or payment data is ever stored:

```sql
ALTER TABLE apartment ADD COLUMN stay_fee_collect INTEGER NOT NULL DEFAULT 0;
ALTER TABLE apartment ADD COLUMN stay_fee_guest_rails TEXT NOT NULL DEFAULT '';  -- csv subset of 'qr','revolut','cash'
ALTER TABLE apartment ADD COLUMN stay_fee_guest_revolut_link TEXT;                -- validated https revolut.com URL
ALTER TABLE apartment ADD COLUMN stay_fee_guest_note TEXT;                        -- e.g. "pay in cash at check-in"
```

QR variable symbol = `f"{reservation_id:010d}"` (unique per stay, lets the
host match the transfer to the stay in their own banking).

## 4. Amount computation

New `stay_fee.charge_for_reservation(apartment, reservation)`, computed live
on each hub render (never stored):

- Only **signed, non-archived guests** on an **active, non-demo** reservation
  count — the same predicate as `_GUESTS_SQL` in `stay_fee.py`, so the panel
  always agrees with the fee register.
- Per guest: `guest_period(guest, reservation, stay_from, stay_to)` over the
  **whole stay** → `liable_nights × rate`. Minors, host-`exempt`, and
  >60-night stays contribute 0 automatically.
- Panel shows when the computed due > 0 and all expected guests are registered
  (`remaining <= 0` or no expected count). Because nothing is stored, adding a
  person via the magic link and saving simply re-renders the panel with the
  new total.

## 5. UX

**Property settings + wizard.** In the fee section (`_stay_fee_fields.html`):
a switch "Collect the stay fee from guests" (`stay_fee_collect`), rail
checkboxes (Bank transfer QR / Revolut link / Cash note), the Revolut link URL
field, and an optional note shown to guests. Saved through the existing
`fee_form_values()` + `routes/admin.py` apartment save path, so it works
identically from the property page and the wizard's property step. The
Revolut link is validated on save: `https` + host `revolut.com` or a
subdomain — a pasted arbitrary URL on a guest page would be a phishing
vector. When `UBYHOST_STAY_FEE_GUEST_PAY=off`, the controls render disabled
and the guest pages never show the panel.

**Guest form (`guest/form.html`).** One-line notice at the bottom when the
property collects: "Municipal stay fee: about X CZK per person for this stay —
you'll pay it once everyone is registered." (Estimate from the entered
dates/birth date; informational only.)

**Guest hub (`guest/stay.html`).** The "money" card, fully read-only: total
due, per-person breakdown (nights × rate), and the allowed rails:

- **Bank transfer (QR)** — SPAYD QR rendered inline as a data URI plus
  IBAN / VS / message to copy (host's `legal_entity` IBAN, VS = reservation id).
- **Revolut** — plain `<a class="g-btn" href="…" rel="noopener">` to the
  host's pasted link (external navigation; CSP-safe, no script) with the note
  that the host sees the payment in their Revolut.
- **Cash** — the host's note text ("pay in cash at check-in").

No guest POST endpoints, no state changes, no audit rows for payments.

**Host side: nothing new.** The stay-fees pages stay exactly as they are; the
host reconciles guest payments against their own account (QR VS = reservation
id makes that matchable by hand or by their bank import).

## 6. Compliance / privacy

- No third-party scripts (Stripe/Revolut are plain links, QR is our own PNG):
  no CSP change. The Revolut/Stripe merchant SDKs stay out.
- Copy on the panel must state: the fee is owed to the municipality, **you pay
  the host**, the host remits it; ubyhost never receives funds and does not
  track whether payment arrived. Copy goes through the legal review path
  (`docs/POPLATEK_Z_POBYTU.md` open questions,
  `docs/UbyHost_workplan/04_legal_positions.md`).
- No new personal data: the four columns are host configuration on
  `apartment`, so **no `retention.py` / RETENTION.md change**.
- i18n: guest keys in all 6 languages; host keys in `host_i18n.py`.

## 7. Phases and files

**Phase 0 — config + toggle.** `migrations/0036_stay_fee_guest_pay.sql` +
`migrations_pg/00006_…sql`; `config.py` (`UBYHOST_STAY_FEE_GUEST_PAY`, default
off), `.env.example`, `docs/ENVIRONMENT.md`; the four columns; toggle UI in
`_stay_fee_fields.html` + `fee_form_values()` + admin save; kill-switch gate;
host i18n keys.

**Phase 1 — guest panel.** `stay_fee.charge_for_reservation()`; hub card in
`routes/guest.py` (`stay_overview` context) + `templates/guest/stay.html` +
new `templates/guest/_fee_pay.html`; form notice in `guest/form.html`; guest
i18n (6 languages).

**Phase 2 — optional only if asked.** A host-pasted Stripe payment link as a
fourth rail (same zero-state pattern as Revolut). Auto-minted Stripe links
with webhook "paid" marking are **not** built (that reintroduces state —
owner decision 5).

**Tests & gates.** Test-map rows for guest pages and `stay_fee`; browser +
geometry tests and one 390 px screenshot per changed guest page (rules 7/10);
`scripts/context_lint.py`; no new dependency.

## 8. Explicitly out of scope

- Any payment state: `paid`/`pending`/`cash_declared` statuses, mark-received
  or waive actions, host "collected" figures, register/PDF columns, delta
  charges, expiry sweeps, audit rows for payments.
- Webhooks or auto-minted links for this feature (Stripe or Revolut); guest
  receipts and "guest paid" e-mails.
- Guest paying the council directly; platform merchant accounts; PSP/licensing
  anything; multi-currency (CZK only).
- Changing the fee **counting** rules — untouched.

## 9. Open questions (not blocking)

1. Pasted Revolut/Stripe links cannot enforce the exact amount (only the QR
   rail embeds it) — the panel shows the amount next to the link and relies
   on the guest paying it. Accepted per owner priority on IBAN/QR; flag in the
   legal copy review.
2. Should the panel also show while the party is still being filled (remaining
   > 0), or strictly only when complete? Default: only when complete, per
   owner decision 3.
3. Counsel: confirm the panel's legal copy (payee wording, "not tracked"
   wording).
