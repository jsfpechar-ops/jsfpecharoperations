# Stay fee pay panel — guests pay the host at the end of the guest flow

Status: **scoped with the owner, build not started.** v3 (2026-11-03):
lean and read-only, and the **guest picks the rail**. UbyHost shows the fee
amount (calculated from what the guest filled in) and the means to pay;
it stores no payment state and marks nothing. No new tables, no webhooks,
no retention rows, no personal data — only host-config columns on
`apartment`.

Product frame: the municipal stay fee (poplatek z pobytu) is owed to the
obec, but under zákon č. 565/1990 Sb. the **host collects and remits**. Some
hosts let Airbnb/Booking collect it; others collect it themselves. UbyHost
already **counts** the fee per signed guest (`App/app/stay_fee.py`). This
feature lets the guest **see the amount and pick how to pay the host** at the
end of the registration flow. UbyHost never receives or holds funds and
never tracks whether the money arrived (same stance as the payment-request
rails, plan `direct-payments-build-plan.md`, brief 0425).

## 1. Owner decisions (2026-11-03)

1. **Payee = the host's account.** Guest pays the host (IBAN / QR / Revolut /
   Stripe link / cash); the host remits to the council as today.
2. **The guest picks the rail.** The panel lists every rail the host enabled;
   picking one reveals its means (QR, IBAN details, external link, or cash
   instructions). Read-only UI — picking stores nothing (decision 5).
3. **v1 rails = QR (SPAYD, "pay here") + plain IBAN + Revolut link + Stripe
   link + cash**, all shown when enabled; IBAN/QR first (free), card links
   last (see §5 cost table). Links are **host-pasted** (from the host's own
   Revolut/Stripe dashboard) — no merchant SDK, no API, no third-party
   script on our pages, no CSP change.
4. **Amount is calculated from what the guest filled in**: a per-person
   estimate card at the end of the guest form (dates + birth date), and the
   per-stay total on the guest hub once all expected guests are registered.
   Adding a person later via the magic link re-shows the panel with the
   recomputed total — free, because the amount is computed live, not stored.
5. **Lean: read-only.** No `paid`/`pending` state, no mark-received UI, no
   webhooks, no delta charges, no "collected" columns. We provide the means;
   the host reconciles in their own account/bank import.
6. **Backend same-obec exemption** (§4): a guest whose residence is in the
   property's obec owes no fee — decided in the backend only, **never shown
   or hinted to the guest** (they must not learn they can skip it by typing
   "Praha"); the host can still override via `fee_host_decision`.
7. Per-property **toggle + rail checkboxes** in the property fee section
   (property page and onboarding wizard property step, where the passport/OCR
   toggles live), behind a global env kill switch
   `UBYHOST_STAY_FEE_GUEST_PAY=off|on` (default off).
8. **Fee = 0 → show nothing.** When the computed amount is 0 (any reason —
   minor, >60 nights, same-obec, host-exempt), the estimate card and the hub
   panel render **nothing at all**: no "no fee due", no exemption reason, ever.
   The statutory framework may be described generally in the legal notice, but
   the interactive UI never explains why a guest owes nothing. The host-facing
   register records the reason (e.g. "resident of the obec").

## 2. What exists — reuse map

| Piece | Where | Reuse |
|---|---|---|
| Fee counting: rate/cadence on `apartment`; per-guest liable/exempt nights incl. minor exemption, host `fee_host_decision`, >60-night rule | `App/app/stay_fee.py` (`guest_period()`, `is_active()`, `clamp_rate()`, `MAX_RATE_CZK=50`) | New `charge_for_reservation()` sums `guest_period()` over the whole stay per signed guest, live at render; same-obec rule added in the shared per-guest logic so panel and register agree |
| Residence data | `guest.res_street/res_city/res_country` (`validation.py:514-515`, `compose_residence`) and property `addr_obec` from the RÚIAN autofill (`ruian.py` `suggest()`, host route `/apartments/ruian-suggest`) | Same-obec comparison, diacritics-folded, CZ only, exact match only (conservative — a non-match falls back to the host's manual decision) |
| SPAYD QR + IBAN helpers | `App/app/payments.py` (`spayd()`, `qr_data_uri()`, `normalise_account()`, host `legal_entity.iban`) | QR rail embedded as data URI; VS = zero-padded reservation id; plain-IBAN rail = copyable account |
| Guest hub + add-person flows | `routes/guest.py` (`/l/{token}/{reservation_id}`, `/party`, `/another`, `/save`), `templates/guest/stay.html` (card order: status → next action → **money** → records → footer) | Pay panel is the "money" card; read-only, no new POST endpoints |
| Per-property toggles | `apartment.ocr_scan` (migration `0035` + pg twin `migrations_pg/00005`), `passport_photo_policy` | Same pattern: apartment columns + gate in the guest routes |
| Property editor / wizard | `templates/_property_editor.html` (fee section includes `_stay_fee_fields.html`), saved via `routes/admin.py` + `routes/stay_fees.py::fee_form_values` | Toggle UI goes into `_stay_fee_fields.html` → appears on the property page and the wizard property step automatically |
| Legal notice mechanism | `templates/guest/_legal_notice.html` (conditional sections, `legal_ack`), `UBYHOST_GUEST_NOTICE_VERSION` + `notice_version`/`notice_ack_at` on `guest` (`config.py:617`, `docs/ENVIRONMENT.md:86`) | Conditional `legal_notice_fee_*` section; version bump on ship |
| Migrations | `App/app/migrations/00NN_*.sql` + twin `App/migrations_pg/000NN_*.sql` (next: `0036` / `00006`) | Five `ALTER TABLE` columns only |
| i18n | guest copy `App/app/i18n.py` (en/cs/de/es/fr) + `guest_uk_i18n.py` (uk); host copy `host_i18n.py` | New keys, all 6 guest languages |

## 3. Data model (migration `0036` + pg twin `00006`)

Host configuration only — no guest or payment data is ever stored:

```sql
ALTER TABLE apartment ADD COLUMN stay_fee_collect INTEGER NOT NULL DEFAULT 0;
ALTER TABLE apartment ADD COLUMN stay_fee_guest_rails TEXT NOT NULL DEFAULT '';  -- csv subset of 'qr','iban','revolut','stripe','cash'
ALTER TABLE apartment ADD COLUMN stay_fee_guest_revolut_link TEXT;  -- validated https, host revolut.com or subdomain
ALTER TABLE apartment ADD COLUMN stay_fee_guest_stripe_link TEXT;   -- validated https, host stripe.com or subdomain
ALTER TABLE apartment ADD COLUMN stay_fee_guest_cash_note TEXT;     -- how cash is collected, e.g. "at check-in"
```

Link validation on save (https + allow-listed host) — a pasted arbitrary URL
on a guest page would be a phishing vector. QR variable symbol =
`f"{reservation_id:010d}"`, unique per stay, so the host can match the
transfer to the stay in their own banking.

## 4. Amount computation

New `stay_fee.charge_for_reservation(apartment, reservation)`, computed live
on each render (never stored):

- Only **signed, non-archived guests** on an **active, non-demo** reservation
  count — the same predicate as `_GUESTS_SQL` in `stay_fee.py`, so the panel
  always agrees with the fee register.
- Per guest: `guest_period(guest, reservation, stay_from, stay_to)` over the
  **whole stay** → `liable_nights × rate`. Minors, host-`exempt`, and
  >60-night stays contribute 0 automatically.
- **Same-obec rule (backend only):** if `res_country == 'CZ'` and the
  diacritics-folded `res_city` exactly matches the property's `addr_obec`
  (plus a tiny alias map such as Praha/Prague), the guest is a resident of
  the obec and owes no fee (poplatník is not a resident of the obec — see
  `docs/POPLATEK_Z_POBYTU.md`). Implemented in the shared per-guest liability
  so the fee register shows the same exemption (reason: resident of the
  obec). Conservative by design: any non-match → no auto-exemption, the host
  decides via `fee_host_decision`. The guest UI never mentions the rule — the
  panel simply shows the amount due (and is hidden when it is 0).

  **Why CZ-only is correct here, not a gap:** RÚIAN is the Czech national
  address registry, so it can only ever identify *Czech* municipalities —
  which is all this rule needs, because the property's obec is always in
  Czechia (UbyHost properties are Czech). A guest who picks any other country
  in `res_country` can never be a resident of a Czech obec, so the
  `res_country == 'CZ'` guard makes them liable by default. There is no EU-wide
  equivalent to query instead: INSPIRE is a harmonisation framework, not one
  queryable API, and national address/residence registers differ per country
  (many are not public at all). So no EU lookup is needed or wanted — the
  comparison is guest's free-text `res_city` (folded) vs the property's
  RÚIAN-sourced `addr_obec` (host autofill, `ruian.py`, 0884), CZ only.
- Form-end estimate card: the same math on the **entered, un-saved** form
  values (stay dates + birth date), rendered server-side on every form render
  (initial GET and the 422 re-render with the guest's values), so the number
  always reflects what they filled in. No live JS recalculation (rule 6,
  no duplicated exemption logic in the browser).
- **Residence card field order (owner decision):** country → city → street.
  The two fields the same-obec rule reads (`res_country`, `res_city`) come
  first, which also matches how the existing nationality→residence sync JS
  treats `res_country` as the primary field. Pure template reorder in the one
  residence card of `guest/form.html`; labels, `required`, and `autocomplete`
  attributes unchanged, validation untouched, and nothing about the fee rule
  is hinted to the guest.
- **Czech address integration in the guest form (owner decision):** with
  country first, when the picked country is CZ the city/street inputs get the
  RÚIAN autocomplete — reuse `ruian.suggest()` behind a new **token-scoped**
  guest route (e.g. `GET /l/{token}/ruian-suggest?q=`), rate-limited
  (`ruian.rate_limited(apartment.owner_user_id)` + the guest-route throttle),
  enabled only for CZ client-side, and **progressive enhancement only**: without
  JS the plain free-text inputs work exactly as today (rule 6). The
  autocomplete improves the `res_city` quality the same-obec match relies on;
  it never reveals the exemption — the panel still just shows the amount due.
  Bump the `?v=` cache key in `templates/guest/base.html` for the changed
  guest JS (rules.md guest-pages).
- Hub panel shows when the computed due > 0 and all expected guests are
  registered (`remaining <= 0` or no expected count).

## 5. UX — the guest picks the rail

**Property settings + wizard.** In the fee section (`_stay_fee_fields.html`):
switch "Collect the stay fee from guests" (`stay_fee_collect`), rail
checkboxes (QR / IBAN / Revolut link / Stripe link / Cash), the two link URL
fields (validated), and the cash-instructions textarea. Saved through the
existing `fee_form_values()` + `routes/admin.py` apartment save path — works
identically from the property page and the wizard's property step. When
`UBYHOST_STAY_FEE_GUEST_PAY=off`, the controls render disabled and guest pages
never show the panel.

**Guest form (`guest/form.html`).** Estimate card at the end of the form when
the property collects: "Municipal stay fee: about X CZK for you (n counted
days × Y CZK) — you'll choose how to pay once everyone is registered."
Plus the legal explanation as a new conditional section in
`templates/guest/_legal_notice.html` (same pattern as the passport section,
gated on the same `fee_notice` flag computed in `_form_context`):

```jinja
{% if fee_notice %}
  <h3>{{ t('legal_notice_fee_title') }}</h3>
  <p>{{ t('legal_notice_fee_body') }}</p>
{% endif %}
```

The section explains **why the guest must pay**: poplatek z pobytu under
zákon č. 565/1990 Sb. — the guest (not a resident of the obec) is the payer
(§3), the host collects and remits to the obec, the base is commenced days
after arrival (§3c), the rate comes from the obec's vyhláška, capped at 50
Kč/day (§3d), under-18s and other statutory exemptions don't pay (§3a–3b),
stays over 60 nights are out of scope (§3a). It states the guest pays the
**host**, and that ubyhost never receives funds and does not track payment.
Copy drafted from `docs/POPLATEK_Z_POBYTU.md` + the stay-fee row of
`docs/UbyHost_workplan/04_legal_positions.md` (§3g(4), 6-year register);
**counsel review required before shipping**. Keys `legal_notice_fee_*` in
all 6 guest languages; the single existing `legal_ack` checkbox covers the
section; ship with a bumped `UBYHOST_GUEST_NOTICE_VERSION` (rule:
`docs/ENVIRONMENT.md:86`) — stamped on the guest at save and shown in the
house-book export and DSR.

**Guest hub (`guest/stay.html`).** The "money" card, fully read-only: total
due, per-person breakdown (counted days × rate), then the rail picker — one
radio/`<details>` per enabled rail, each revealing its means:

- **QR ("pay here")** — SPAYD QR inline as a data URI + amount/VS/message to
  copy (host `legal_entity` IBAN, VS = reservation id).
- **IBAN** — plain copyable account (IBAN + name), no QR.
- **Revolut** — `<a class="g-btn" href="…" rel="noopener">` to the host's
  pasted Revolut link, note "you'll see it in the host's Revolut".
- **Stripe** — same pattern, host's pasted Stripe payment link.
- **Cash** — the host's cash-instructions text.

The card ends with a one-line pointer to the legal information the guest
already confirmed ("why this fee applies — see the legal information"), not a
second copy of the legal text. No guest POST endpoints, no state changes.

### Rail cost comparison (host bears the fee; our application fee is 0)

| Rail | Cost to the host | Notes |
|---|---|---|
| Cash | 0 | host's instructions text |
| IBAN / SEPA transfer | 0 | VS = reservation id for matching |
| QR (SPAYD) | 0 | same account, amount embedded |
| Revolut payment link | ≈1–2% + small fixed, plan-dependent; only on successful transactions, refunds free; settles to the merchant account in ~24 h | host pastes a link created in the Revolut app |
| Stripe payment link | EEA card **1.5% + €0.25** (~6.3 Kč), premium/corporate EEA 1.9% + €0.25, non-EEA 3.15–3.25% + €0.25, +1–2% FX; disputes $15 | on the host's connected account, application fee 0 |

For a typical city tax (e.g. 3 nights × 50 Kč = 150 Kč) the **fixed card fee
dominates**: Stripe costs ≈ 8.5 Kč (EEA) to ≈ 11 Kč (non-EEA), i.e. ~6–7% of
the fee; Revolut is similar or slightly cheaper; IBAN/QR/cash are free. So
yes — **Stripe is the most expensive rail for this use case**; it still earns
its place for international guests who cannot SEPA. Recommended default
order in the picker: QR → IBAN → Revolut → Stripe → Cash; the host enables
what they want and the guest picks.

### Revolut deep-dive (developer.revolut.com, checked 2026-11-03)

- **Personal Revolut accounts have no API.** Payment/request links are created
  in the Revolut app (a few taps); anyone can pay them by card or Revolut Pay
  in the browser. That is exactly our v1 rail: host pastes the link.
- Programmatic links, the Merchant Web SDK, and `ORDER_COMPLETED` webhooks
  all require a Revolut **Business merchant account**: secret API key
  server-side only, public key for the SDK, orders created server-side, and
  webhook authenticity via the `Revolut-Signature` header (webhooks are the
  authoritative "paid" signal; test against `sandbox-merchant.revolut.com`).
  Since this feature deliberately stores no paid state (decision 5), we do
  **not** build the Merchant API integration — pasted link only.
- The embedded Merchant Web SDK would be a third-party script on a guest page
  (repo rule 2) — another reason it stays out.

### Design options (for owner review before build — Arrival-lane rules apply: light mode, one 640 px column, no sideways scroll from 320 px, exactly one coral action per screen, all 6 languages, `?v=` bump, 390 px screenshot gate)

All options share the same data (live `charge_for_reservation()`), the same
"fee = 0 → render nothing" rule, and the same rails. They differ only in
where the picker lives.

**Option A — one "money" card on the stay hub (recommended for v1).**
Zero new routes; appears in the fixed card order at position 3; re-shows
automatically when a person is added. Rail picker = an accordion of
`<details>` rows inside the card; picking a rail reveals its means inline, so
only one pay control is ever visible (the card's single coral element).

```
┌─ g-card (money) ────────────────────────────────┐
│  Municipal stay fee            450 Kč           │  ← serif heading + big amount
│  3 counted days × 50 Kč · 2 guests              │  ← g-intro muted line
│  ▸ Per person (3 × 50 Kč, 2 × 75 Kč)            │  ← details.g-summary, quiet
│                                                 │
│  ▾ Bank transfer (QR)          ← open row      │
│     [ QR png ]   IBAN CZ… · VS 0000000123      │  ← copy button (ghost)
│  ▸ IBAN only                                    │
│  ▸ Revolut link                                 │
│  ▸ Card (Stripe link)                           │
│  ▸ Pay in cash — "at check-in, ask Josef"      │  ← host note text
│  Why this fee — see the legal information  ›    │  ← one quiet link, no legal repeat
└─────────────────────────────────────────────────┘
```

Pros: fewest moving parts, no new page, "smart" re-show for free, consistent
with the hub's existing cards. Cons: long stays with many guests make the card
tall on a phone (mitigate: per-person breakdown stays collapsed by default).

**Option B — dedicated pay step `/l/{token}/{reservation_id}/pay`.**
A full-screen ticket card (strip "Stay fee", big amount, rail list, stub with
the ONE coral action for the chosen rail). The hub shows a compact card
"Stay fee 450 Kč — Pay ›" linking to it. Pros: phone-friendly, feels like the
"end of the flow" moment you originally described, easy to share/re-open.
Cons: one more route + page to test/screenshot; the hub still needs the
compact card anyway.

**Option C — hub card, no accordion: all rails visible at once** as quiet
rows (QR always shown when enabled, links as ghost buttons, cash note last).
Pros: dead simple, everything visible without interaction (good for elderly
guests). Cons: several pay-looking controls at once; on 320 px the card gets
very tall; weaker "guest picks one" semantics.

**Recommendation: A for v1** (leanest, fewest routes), with the per-person
breakdown collapsed; revisit B if hosts ask for a standalone pay page.

**Standards check for option A (against `docs/DESIGN.md` Arrival lane +
`guest.css`, mockup A v3 after visual review):** real QR PNG data-URI (not a
placeholder), rails as standard `details.g-summary` rows so the rhythm matches
the "Per person" row, minimal custom css (amount size, QR row flex, IBAN wrap), no nested `g-card` (rails are `details` rows with
dividers — a nested card would double the border/shadow); the "why" lives in a
`details.g-head-help` `?` popover on the card head, not in the main flow
(non-obvious → `?` rule); exactly one coral action per screen — the default-open
QR rail shows only a ghost Copy, and a pay link's coral `g-btn` appears only
inside its own opened row; IBAN `dd` gets `overflow-wrap: anywhere` so 320 px
never scrolls sideways; per-person breakdown uses the existing
`details.g-summary`; card sits at the fixed "money" position 3; light mode,
tokens only, `?v=` bump on guest.css; native `<details>` = no JS needed;
all strings via `t()` in 6 languages; 390 px screenshot gate at build.

**Renderable mockups** (open from the repo root in a browser — they link the
real `App/app/static/tokens.css` + `guest.css`, EN copy; the build ships all
6 languages):

| File | Shows |
|---|---|
| [stay-fee-guest-payment/mockup-A-hub-accordion.html](stay-fee-guest-payment/mockup-A-hub-accordion.html) | Option A — hub money card, rail accordion, QR + copy rows |
| [stay-fee-guest-payment/mockup-B-pay-step.html](stay-fee-guest-payment/mockup-B-pay-step.html) | Option B — dedicated pay step, radio rails, one coral stub action |
| [stay-fee-guest-payment/mockup-C-hub-all-rails.html](stay-fee-guest-payment/mockup-C-hub-all-rails.html) | Option C — all rails visible at once |
| [stay-fee-guest-payment/mockup-D-form-estimate.html](stay-fee-guest-payment/mockup-D-form-estimate.html) | Form-end estimate card (quiet, no button, hidden when 0) |
**Form-end estimate card** (all options): a quiet grey card like the legal
notice box — one line "Municipal stay fee: about X Kč for you (n days × Y Kč)"
+ "you'll choose how to pay once everyone is registered", no button, no coral,
hidden when the estimate is 0.

## 6. Compliance / privacy

- No third-party scripts (Revolut/Stripe are plain external links, QR is our
  own PNG): no CSP change.
- Pay-panel and legal-notice copy state: fee owed to the municipality, **you
  pay the host**, host remits it; ubyhost never receives funds and does not
  track payment. All `legal_notice_fee_*` copy goes through counsel review
  (`docs/POPLATEK_Z_POBYTU.md`, `04_legal_positions.md`); shipping bumps
  `UBYHOST_GUEST_NOTICE_VERSION`.
- The same-obec rule is backend-only and never surfaced to guests (copy must
  not hint at it).
- No new personal data: five columns are host configuration on `apartment` —
  **no `retention.py` / RETENTION.md change**.
- i18n: guest keys in all 6 languages; host keys in `host_i18n.py`.

## 7. Phases and files

**Phase 0 — config + toggle.** `migrations/0036_stay_fee_guest_pay.sql` +
`migrations_pg/00006_…sql`; `config.py` (`UBYHOST_STAY_FEE_GUEST_PAY`, default
off), `.env.example`, `docs/ENVIRONMENT.md`; the five columns; toggle UI in
`_stay_fee_fields.html` + `fee_form_values()` + admin save (link validation);
kill-switch gate; host i18n keys.

**Phase 1 — guest panel + legal notice + same-obec rule.**
`stay_fee.charge_for_reservation()` (incl. same-obec exemption in the shared
per-guest logic); hub rail-picker card in `routes/guest.py` (`stay_overview`
context) + `templates/guest/stay.html` + new `templates/guest/_fee_pay.html`;
form-end estimate card in `guest/form.html` (`_form_context`);
`legal_notice_fee_*` section in `_legal_notice.html` + keys in 6 languages +
`UBYHOST_GUEST_NOTICE_VERSION` bump (counsel sign-off first); guest i18n.

**Tests & gates.** Test-map rows for guest pages and `stay_fee`; per
`docs/context/rules.md#guest-pages`: `tests/test_guest_browser_e2e.py` and
`tests/test_host_geometry.py` with **0 skipped**, plus one 390 px screenshot
per changed guest page (rules 7/10), following the Arrival-lane rules in
`docs/DESIGN.md`; `scripts/context_lint.py`; no new dependency. EN+CS (here:
all 6 guest languages) in the same commit. Implementation goes to a Haiku
executor brief in `docs/tasks/` per `AGENTS.md` — the orchestrator plans, the
executor builds.

## 8. Explicitly out of scope

- Any payment state: `paid`/`pending` statuses, mark-received/waive actions,
  "collected" figures, register/PDF columns, delta charges, sweeps, audit rows
  for payments, guest receipts / "guest paid" e-mails.
- Revolut Merchant API / Web SDK, auto-minted links, and Revolut or Stripe
  webhooks for this feature (no state to update); Stripe link creation on the
  connected account for this feature.
- Guest paying the council directly; platform merchant accounts; PSP/licensing
  anything; multi-currency (CZK only).
- Live JS fee recalculation in the form (server-rendered estimate only).

## 9. Gap check (2026-11-03, orchestrator review)

Verified against the code; the material findings:

- **Sealed filings are safe.** `stay_fee_filing.frozen_summary()` renders sealed
  periods from the frozen row, so adding the same-obec rule to the *live*
  per-guest logic does not rewrite already-filed periods. Live, unsealed
  periods (list page, `stay_fee_auto` e-mails) will drop resident guests after
  deploy — legally correct, but flag it in the PR and add a decisions.md line.
- **QR/IBAN rails need a host account.** `payment_request.qr_payload` requires
  `legal_entity.iban`/`bank_account`; the settings save must warn (or block)
  when `qr`/`iban` is enabled but the owner has no account, and the panel must
  hide those rails if it is missing at render time.
- **Guest RÚIAN route throttling.** `rate_limit.record(scope, key)` is generic;
  the guest suggest route uses a scope like `ruian_guest` keyed by link token +
  client IP, on top of `ruian.rate_limited(owner)`.
- **pg twin pattern.** `migrations_pg/00005` shows the twin file needs
  `+goose Up`, `IF NOT EXISTS` statements, **and** an
  `INSERT INTO schema_migrations … ON CONFLICT DO NOTHING` for SQLite version
  36 — the build brief must copy that exactly (next: `0036` / `00006`).
- **Never reveal *why* the fee is 0** (owner decision 8). When the computed
  amount is 0, the form estimate and hub panel render nothing at all — no
  "no fee due", no reason, for ANY exemption. The **same-obec exemption** is
  additionally never hinted anywhere in guest copy (the legal notice must not
  state the residence criterion — see §10). The register (host-facing)
  records the reason "resident of the obec".
- **Rate change mid-stay:** the panel uses the current `stay_fee_rate_czk` ×
  counted days; the register splits per period at sealed rates. No rate
  history exists, so the panel states "at the current rate". Accepted for v1
  (rates change rarely; the council PDF remains the legal artefact).
- **Cash rail without a note:** if enabled with an empty note, render a default
  "pay in cash to the host at check-in" line (host can customize).
- **Privacy page:** no change needed — the feature stores no guest personal
  data; the duty + payee wording lives in the form's legal notice (above).
- **Delivery:** PR template sections filled, CI green, merge only via
  `scripts/merge-pr-on-green.sh`, never push to `main` (AGENTS.md rule 8).

## 10. Counsel draft — `legal_notice_fee_*` copy (research 2026-11-03; human lawyer sign-off still required per repo rules)

Legal grounding checked against public sources: zákon č. 565/1990 Sb. §3
(renamed "poplatek z pobytu" from 1.1.2020, zákon č. 278/2019 Sb.): poplatník =
the accommodated guest **not registered for permanent residence in that obec**;
plátce = the accommodation provider, who collects and remits (§3f); subject =
paid stay ≤ 60 consecutive days with one provider (§3a); base = commenced days
excluding the arrival day (§3c); rate set by the obec's OZV, **capped at 50
Kč/person/day** (§3d, in force since 1.1.2021); statutory exemptions §3b
(under 18, ZTP/P + guide, hospitalised, seasonal workers, …); evidenční kniha
duty §3g. Praha: OZV č. 18/2019 Sb. hl. m. Prahy as amended (19/2021) — 50 Kč
from 1.1.2022. **The copy deliberately omits the residence criterion** so the
backend exemption stays secret.

CS draft:
- `legal_notice_fee_title`: "Místní poplatek z pobytu"
- `legal_notice_fee_body`: "Obec, ve které se ubytováváte, může obecně
  závaznou vyhláškou zavést místní poplatek z pobytu (zákon č. 565/1990 Sb.).
  Poplatek platíte vy jako host vašemu ubytovateli; ten ho odvádí obci.
  Základem poplatku je počet započatých dnů pobytu bez dne počátku pobytu,
  sazbu určuje obec, nejvýše však 50 Kč za osobu a den. Zákon dále stanoví
  osvobození od poplatku (např. osoby mladší 18 let) a pobyt delší než 60 po
  sobě jdoucích dnů u jednoho ubytovatele poplatku nepodléhá. Poplatek platíte
  přímo ubytovateli podle jeho pokynů — UbyHost platbu nezprostředkovává a
  nezaznamenává, zda byla zaplacena."

EN draft:
- `legal_notice_fee_title`: "Municipal stay fee"
- `legal_notice_fee_body`: "The municipality where you are staying may charge
  a local stay fee under its by-law (Act No. 565/1990 Coll.). You pay it to
  your host, who remits it to the municipality. The fee is based on the number
  of commenced days of stay excluding the arrival day; the rate is set by the
  municipality and is capped at CZK 50 per person per day. The Act also provides
  exemptions (for example for persons under 18), and a stay longer than 60
  consecutive days with one provider is not subject to the fee. You pay your
  host directly as instructed — UbyHost does not process the payment and does
  not record whether it was paid."

de/es/fr/uk: faithful translations at build (brief 0901). Ship with a bumped
`UBYHOST_GUEST_NOTICE_VERSION` (docs/ENVIRONMENT.md:86).

## 11. Briefs (executor tasks, Haiku 5.5, one per session)

| Brief | Scope | Depends on |
|---|---|---|
| [0897](../tasks/0897-stay-fee-guest-pay-phase0.md) | phase 0: migration 0036/00006, kill switch, property toggle UI, host i18n | none |
| [0898](../tasks/0898-stay-fee-charge-computation.md) | `charge_for_reservation()` + same-obec rule in shared logic + tests | 0897 |
| [0900](../tasks/0900-stay-fee-guest-panel.md) | hub money card + rail picker, form estimate, residence order | 0898 |
| [0901](../tasks/0901-stay-fee-legal-notice-ruian.md) | legal-notice section + 6-language copy + guest RÚIAN route | 0897 |
| [0902](../tasks/0902-stay-fee-help-guide.md) | host help topic (`page_help('stay_fees')`) + guest-guide fact for the fee | 0897 |

**Help/legal prep already done in docs (2026-11-03):** ROPA row (no new personal
data, no payment state, Stripe/Revolut are the host's processors —
`docs/privacy/ROPA.md`), RETENTION row (config-only columns, no payment data —
`docs/privacy/RETENTION.md`), legal position §8 + open item 11 for counsel
(`docs/UbyHost_workplan/04_legal_positions.md`), counsel-draft copy in §10.

## 12. Open questions (not blocking)

1. Counsel: confirm the same-obec exemption rule + its register reason
   wording, and the `legal_notice_fee_*` copy (payee wording, "not tracked"
   wording, no hint of the residence rule).
2. `res_city` is free text — the same-obec match is exact-after-folding only;
   edge cases (Praha vs Prague vs Hlavní město Praha) go in the small alias
   map, everything else falls back to the host's manual decision. RÚIAN stays
   CZ-only (host property autofill); no EU-wide address API is needed, because
   only CZ residents can be exempt — see §4. A guest-facing RÚIAN suggest is
   deliberately not added (it would not leak the exemption, but it is scope
   creep; free text + folding is enough for a conservative match).
3. Pasted Revolut/Stripe links cannot enforce the exact amount (only the QR
   rail embeds it) — the panel shows the amount next to the link; flagged in
   the legal copy review.
