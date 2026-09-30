# PLAN — Poplatek z pobytu (host remittance) · v1

> **Status: PLANNING — owner review before any code.** Ready to implement once approved.
>
> **What this is.** A host-only, per-property calculator and PDF generator for the
> Czech *poplatek z pobytu* (local stay fee, zákon č. 565/1990 Sb.). The host sets
> the rate and municipality payment details once, plus a small set of
> reusable **template** fields (the úřad letterhead and a signature). Each month
> UbyHost counts the liable and exempt **lůžkodny** (bed-days) and the total, and
> renders a one-page **"Měsíční hlášení k místnímu poplatku z pobytu"** PDF ready
> to send to the úřad. A separate CSV matches the §3g evidenční kniha columns.
>
> **What this is not.**
> - **Not** the guest-facing stay-fee plan (no QR, no guest payment card, no guest
>   fee display). That plan (`PLAN_POPLATEK_Z_POBYTU.md`) stays on hold.
> - **Not** an electronic filing. UbyHost never submits to a council, never touches
>   datové schránky, never processes or checks any payment.
> - **Not** a replica of every municipality's form (each obec prints its own). It
>   produces the standard monthly hlášení — the three figures plus identity and
>   payment details — which is what hosts actually send or type into a portal.
> - **Not** a compliance guarantee. Same stance as UbyPort: the tool assists.
>
> **Optional by design.** The stay fee is an opt-in extra, never a required setup
> step. Nothing renders anywhere until the host sets a rate on a property (`rate >
> 0`). It is **not** part of onboarding and there is no toggle or nag to turn it on —
> the host discovers it later under Records → Poplatek z pobytu. A host who ignores
> it is completely unaffected.

Research date for all sources: **2026-09-29** (§2).

---

## 0. Rules for the implementing agent (read first)

Mirror `PLAN_POPLATEK_Z_POBYTU.md` §0 and the invoice builder.

1. **One step per commit**, in §13 order. Run tests from `App/`:
   `.venv/bin/python -m pytest tests -q` (no `PYTHONPATH=App` — see `AGENTS.md`).
   Do not start the next step while tests are red.
2. **Use exactly the names given** (files, functions, columns, routes, i18n keys).
   Do not add extra fields or "nice to have" options.
3. **Copy every user-facing string verbatim** from §12 into **both** `en` and `cs`
   (host UI). The PDF document itself is Czech-only (it is a Czech government form).
4. **Security.** Every host route starts with `guard = auth.require_login(request)`
   and loads rows through `access.*` (owner-scoped). Every POST includes the
   `_csrf` hidden input. Never mark host-typed text `|safe`.
5. **Light-mode only.** Reuse existing CSS variables (`--g-ink`, `--g-muted`,
   `--g-line`, `--g-surface`, `--g-accent`).
6. **If the code in the repo does not match what this plan describes**, stop and
   report the mismatch. Do not guess.
7. **Deploy to staging first**; every change goes through a PR the owner reviews
   and merges. Production deploy is manual-only.

---

## 1. The document we generate (the "hlášení")

This is the target PDF, mirroring the operator's real Praha 3 form
(`K13_08_26_Mesicni_hlaseni_k_mistnimu_poplatku_z_pobytu.pdf`).

| # | Field (Czech, verbatim) | Source | Editable |
|---|---|---|---|
| 1 | Úřad letterhead: office name (multi-line) + address + contact line (tel, e-mail, č. účtu, datová schránka) | `apartment.stay_fee_authority_*` | yes — **template** |
| 2 | Title: "Měsíční hlášení k místnímu poplatku z pobytu za období \<month\>" | computed | no |
| 3 | "Jméno a příjmení plátce, obchodní firma, název" | `legal_entity.name` | yes — template |
| 4 | "Variabilní symbol" | `apartment.stay_fee_vs` | yes — template |
| 5 | "Počet lůžkodnů osob, které podléhají poplatku" | computed | yes (override) |
| 6 | "Počet lůžkodnů osob, které jsou od poplatku osvobozeny:" | computed | yes (override) |
| 7 | "CELKOVÁ ČÁSTKA POPLATKU odváděná na účet \<obec\>:" | computed | yes (override) |
| 8 | "Lůžkoden = osoba x počet nocí" (definition note) | fixed text | no |
| 9 | "DATUM: \<date\>" + "PODPIS, RAZÍTKO" | computed date + entity signature | yes — template |
| 10 | Footer instruction (datová schránka, pošta, e-mail s el. podpisem, osobně; do 15 dnů) | `apartment.stay_fee_authority_*` | yes — template |

**Template vs computed.** Fields 1, 3, 4, 9, 10 are the **template** — the host fills
them once and UbyHost reuses them every period. Fields 5, 6, 7 are **computed**
fresh each period but overridable. Only the period (2) and the date (9) change
month to month automatically. After the template is set, the whole feature is
**fully automatic**: the host just opens the period and downloads the PDF.

### 1.1 Layout (top to bottom — match the render exactly)

The page is A4 portrait, white, with a **6 px coral rule** pinned to the very top
(edge to edge). Everything sits in a single column with ~52 px side padding.

1. **Header row** (flex, space-between):
   - **Left — the úřad (addressee).** A muted uppercase label `SPRÁVCE POPLATKU`,
     then the office name in **bold ~19 px** ("Městská část Praha 3"), then the
     department + address in muted ~11.5 px, then the contact line
     (tel · e-mail · č. účtu) in muted ~10.5 px.
   - **Right — the document label.** `MĚSÍČNÍ HLÁŠENÍ` in **coral, uppercase,
     bold ~11 px**, then "k místnímu poplatku z pobytu · za období" in muted
     ~10.5 px, then the period **"Srpen 2026" in bold ~30 px**.
2. **Form panel** — a single light-grey (`--canvas`) rounded panel holding five
   label:value rows separated by hairlines. Each row: the Czech label on the left
   (ink-secondary ~12 px), the value on the right (bold ~14 px). The last row is
   the **total**: label in bold uppercase, value **bold ~24 px**. Under it, the
   muted note **"Lůžkoden = osoba × počet nocí"**.
3. **Signature row** — `DATUM: 12. 9. 2026` (left) and `PODPIS, RAZÍTKO` (right),
   ~12 px.
4. **Footer instruction** — the datová schránka / pošta / e-mail / 15 dnů text in
   muted ~10 px, wrapped, with a hairline above it.
5. **UbyHost footer** — a hairline, then the UbyHost mark + "Vystaveno v UbyHost –
   registrace hostů a faktury pro ubytovatele · ubyhost.com" in faint ~10 px, and
   "Strana 1/1" on the right.

The render to match is `/tmp/opencode/hlahseni-web.jpg` (Praha 3) and
`hlahseni-brno.jpg` (Brno — same layout, úřad + rate + total swapped).

---

## 2. Legal notes that shaped the design (cited from zákon č. 565/1990 Sb.)

- **Poplatek z pobytu** is one of seven local fees a municipality *may* introduce
  by *obecně závazná vyhláška* (OZV) (§1). Not every obec has it.
- **Poplatník** (who is liable): any person **not registered as resident in that
  obec** (§3, §16c). "Registered" = trvalý pobyt (Czechs) or přechodný pobyt
  >3 months / trvalý pobyt / asylum (foreigners). A person registered in the same
  obec owes nothing.
- **Předmět** (scope): úplatný (paid) pobyt ≤ **60 consecutive calendar days** at
  one provider (§3a). Longer stays, detention and hospital stays (except spa) are
  out of scope (§3a(2)). **A stay over 60 days is *not subject* — this is a scope
  limit (§3a), not an exemption (§3b).** The 60-day clock is per provider.
- **Základ poplatku** (base): *"počet započatých dnů pobytu, s výjimkou dne
  počátku pobytu"* (§3c). The operator's own municipal form resolves the practical
  count with the note **"Lůžkoden = osoba x počet nocí"** — i.e. the base is
  **person-nights** (nights), not "nights − 1". This is the value this plan uses
  (`person_days = (checkout − checkin)` nights). See §6.
- **Sazba** (rate): max **50 Kč** per person per day (§3d). Set by the obec; the
  host types it.
- **Výpočet** (formula): `base × rate` (§3e).
- **Plátce** (provider): collects from the guest and remits to the obec (§3f).
- **Osvobození** (exemptions — §3b(1)): exempt are persons who are:
  - (a) **nevidomá** (blind), **závislá na pomoci jiné osoby** (dependent on
    another person's care), **držitel průkazu ZTP/P** and their **průvodce**;
  - (b) **mladší 18 let** (under 18);
  - (c) **hospitalizovaná** (in hospital, except spa);
  - (d) **pečující o děti** on a children's camp or similar event;
  - (e) **sezónní pracovník**;
  - (f) in a **school/institutional facility**, **social-services facility**,
    **emergency shelter**, or performing **rescue/cleanup work**.
  - (§3b(2)) **příslušník bezpečnostního sboru / voják / státní zaměstnanec** in
    state-owned facilities on duty.
  Municipalities may add further exemptions in their OZV (§14(3)(a)) → the host
  override covers these. Under-18 and over-60 are the only ones UbyHost computes
  automatically; everything else is the host's decision (§7).
- **Evidenční kniha** (§3g): the provider must keep an evidence book per facility,
  in paper or electronic form, with for each person:
  (a) stay start and end, (b) name and address of residence, (c) date of birth,
  (d) ID document number and type (9 listed types), (e) amount collected **or**
  reason for exemption. Kept **6 years** (§3g(4)). This is the CSV column list (§10).
- **Ohlašovací povinnost** (§14a): one-time registration with the obec's *správce
  poplatku* (identity, bank accounts, assessment data); changes within 15 days.
  **UbyHost does not automate this.**
- **Remittance mechanism:** bank transfer to the obec's account with the
  council-assigned **variabilní symbol** (*poplatnické číslo*). Example: Praha 3 →
  account `19-2000781379/0800`. **No digital signature is required on the periodic
  remittance** — the transfer with the correct VS *is* the filing. The signature
  on the hlášení is for completeness, not a legal requirement.
- **Cadence is per-obec**: monthly (Praha, by the 15th) vs quarterly (Brno,
  Náchod, many smaller obce) vs "no fee at all". The host picks monthly or
  quarterly **per property**. A stay counts in the month/quarter of its checkout.
- **Penalties (§247a daňový řád):** up to **500 000 Kč** for failing to file the
  ohlášení, report changes, or keep the evidence book. Late payment can be
  increased up to **triple** (§11c).
- **Future risk:** MMR is preparing **eTurista**, a central accommodation/guest
  registry (~2027), which may centralize some fee reporting. This tool is a
  stopgap/companion. Revisit when the eTurista law lands.

---

## 3. What already exists (do not rebuild)

| Existing | File | Used for |
|---|---|---|
| Host-only invoice section | `routes/invoices.py`, `templates/invoices.html`, `invoice_form.html`, `invoice_detail.html`, `invoice_settings.html` | the "section like Invoices" pattern: nav, list, detail, settings, PDF download |
| Invoice PDF renderer | `App/app/invoice_pdf.py` | the PDF renderer to extend for the hlášení |
| Bank-account helpers + QR | plan `PLAN_POPLATEK_Z_POBYTU.md` §5 (`payments.py`: `normalise_account`, `format_iban`, `spayd`, `qr_png_bytes`) — not yet in the repo | validating the council account + building the QR Platba for the host to pay |
| CSV style | `housebook.housebook_csv` (`;` separator, UTF-8 BOM) | the fee CSV |
| Signed-form check | `reporting.guest_has_signature(guest)` | who is counted |
| Age/date maths | `validation.normalise_birth_date`, `validation.parse_iso_date` (`age_on` does **not** exist — add it in step 2) | under-18 rule and nights |
| Signature-at-rest pattern | `guest.signature_png` / `guest.signature_png_enc` | encrypting the host's stored signature |
| Sidebar nav | `templates/base.html` (group `nav.records`), `templates/_components.html::nav_icon` | the new **Poplatek z pobytu** item |

**Confirmed in the repo:** the `stay_fee_*` columns from `PLAN_POPLATEK_Z_POBYTU.md`
were **never added** (checked `App/app/db.py`). Only the invoice `legal_entity`
fields (`bank_account`, `iban`, `bic`) exist. So this plan defines a clean host-only
schema with no collision with the half-implemented guest feature.

---

## 4. Domain model (the fee decision)

One concept drives everything: per signed guest, a **fee decision** that resolves to
exactly one of three outcomes.

| Outcome | When | Liable nights | Exempt nights |
|---|---|---|---|
| **liable** | signed, adult on arrival, stay ≤ 60 days, no host override | `nights` | 0 |
| **exempt** | under 18 on arrival, OR host set `fee_host_decision = 'exempt'` | 0 | `nights` |
| **not subject** | stay > 60 days (§3a) | 0 | 0 (not counted at all) |

A host **charge** override (`fee_host_decision = 'charge'`) forces *liable* even for
a minor (e.g. an adult booking for a child). The automatic rules handle under-18 and
over-60; every other §3b exemption (ZTP/P, blind, dependent, local resident, etc.)
is a host decision with a stored reason. There is **no guest-facing input** — see §7.

---

## 5. Database changes (`App/app/db.py`)

Add each column **twice** (in `CREATE TABLE` and in `ADDED_COLUMNS`), like the
invoice fields.

### 5.1 `apartment` — the per-property template (obec is per property)

| Column | Declaration | Meaning |
|---|---|---|
| `stay_fee_rate_czk` | `INTEGER NOT NULL DEFAULT 0` | rate per person-night; 0 = feature off |
| `stay_fee_cadence` | `TEXT NOT NULL DEFAULT 'monthly'` | `monthly` / `quarterly` |
| `stay_fee_council_account` | `TEXT` | council's account as typed (Czech `prefix-number/bank` or IBAN) |
| `stay_fee_council_iban` | `TEXT` | derived by `payments.normalise_account` |
| `stay_fee_vs` | `TEXT` | council-assigned variabilní symbol (poplatnické číslo) |
| `stay_fee_authority_name` | `TEXT` | the úřad office name (multi-line) — the addressee |
| `stay_fee_authority_address` | `TEXT` | the úřad address |
| `stay_fee_authority_contact` | `TEXT` | the úřad contact line (tel, e-mail, č. účtu, datová schránka) |

### 5.2 `legal_entity` — the plátce identity + signature (shared across properties)

| Column | Declaration | Meaning |
|---|---|---|
| `signature_png_enc` | `TEXT` | host's uploaded signature image, encrypted at rest (mirror `guest.signature_png_enc`) |
| `signature_name` | `TEXT` | typed-name fallback when no image is uploaded (e.g. "Josef Pechar") |

The payer name on the hlášení is `legal_entity.name` (already exists).

### 5.3 `guest` — the host's exemption decision

| Column | Declaration | Meaning |
|---|---|---|
| `fee_host_decision` | `TEXT` | `NULL` (auto-rule) / `exempt` / `charge` |
| `fee_host_reason` | `TEXT` | free text ≤ 120, required when decision is `exempt` |

No other tables. There is **no `fee_return` table and no status tracking** — this is
a calculator: the figures and PDF are computed and rendered on demand from live
guest data plus the template, and nothing is persisted.

---

## 6. Calculation core — new module `App/app/stay_fee.py`

```python
"""Místní poplatek z pobytu: host-declared rate, per-period remittance figures."""
from datetime import date
from typing import Any, Optional

from . import db, reporting, validation

MAX_RATE_CZK = 50        # zákon 565/1990 §3d
MAX_CALENDAR_DAYS = 60   # §3a
ADULT_AGE = 18           # §3b(1)(b)


def is_active(apartment) -> bool:
    return bool(apartment) and int(apartment["stay_fee_rate_czk"] or 0) > 0


def period_bounds(apartment, month: date) -> tuple[date, date]:
    """Return (start, end) inclusive for the apartment's cadence containing month."""
    cadence = (apartment.get("stay_fee_cadence") or "monthly")
    if cadence == "quarterly":
        q = (month.month - 1) // 3
        start = date(month.year, q * 3 + 1, 1)
        end_month = q * 3 + 3
        end = (date(month.year, 12, 31) if end_month == 12
               else date(month.year, end_month + 1, 1) - date.resolution)
    else:
        start = date(month.year, month.month, 1)
        end = (date(month.year, 12, 31) if month.month == 12
               else date(month.year, month.month + 1, 1) - date.resolution)
    return start, end


def person_days(guest, reservation) -> int:
    """Fee base: number of nights. "Lůžkoden = osoba x počet nocí" (§2)."""
    start = validation.parse_iso_date(guest["stay_from"] or reservation["date_from"])
    end = validation.parse_iso_date(guest["stay_to"] or reservation["date_to"])
    if not start or not end:
        return 0
    return max((end - start).days, 0)


def conservative_birth(raw) -> Optional[date]:
    """Earliest possible birthday, so an unknown day/month never makes someone a minor."""
    digits = validation.normalise_birth_date(raw)
    if len(digits) != 8 or not digits.isdigit():
        return None
    day, month, year = int(digits[:2]), int(digits[2:4]), int(digits[4:])
    if year == 0:
        return None
    try:
        return date(year, month or 1, day or 1)
    except ValueError:
        return None


def person_fee(guest, reservation, rate: int) -> dict[str, Any]:
    nights = person_days(guest, reservation)
    start = validation.parse_iso_date(guest["stay_from"] or reservation["date_from"])
    decision = guest.get("fee_host_decision")
    if decision == "exempt":
        liable, exempt = 0, nights
    elif decision == "charge":
        liable, exempt = nights, 0
    elif nights > MAX_CALENDAR_DAYS:
        liable, exempt = 0, 0           # NOT SUBJECT at all (§3a), not exempt
    else:
        birth = conservative_birth(guest["birth_date"])
        minor = bool(birth and start and validation.age_on(birth, start) < ADULT_AGE)
        liable, exempt = (0, nights) if minor else (nights, 0)
    return {"liable_days": liable, "exempt_days": exempt, "amount_czk": liable * rate}


def period_summary(apartment, month: date) -> Optional[dict]:
    """Aggregate every signed guest whose stay overlaps the period."""
    if not is_active(apartment):
        return None
    start, end = period_bounds(apartment, month)
    rate = int(apartment["stay_fee_rate_czk"])
    # Query reservations of this apartment overlapping [start, end], then signed
    # guests, then sum person_fee(...). Return liable_days, exempt_days, total_czk.
    ...
```

Worked examples (rate 50; put in `tests/test_stay_fee.py`):

| # | Guest dates | Birth | Host decision | Result |
|---|---|---|---|---|
| E1 | 2026-09-10 → 09-14 (4 nights) | adult | — | 4 liable, 200 Kč |
| E2 | 2026-09-10 → 09-14 | 17 on arrival | — | 0 liable, 4 exempt (§3b(1)(b)) |
| E3 | 2026-06-01 → 08-01 (61 nights) | adult | — | not subject (0/0, §3a) |
| E4 | 2026-06-01 → 07-31 (60 nights) | adult | — | liable (60 is the inclusive ceiling) |
| E5 | 2026-09-10 → 09-14 | adult | `exempt` | 0 liable, 4 exempt |
| E6 | 2026-09-10 → 09-14 | 17 on arrival | `charge` | 4 liable, 0 exempt (host override) |

> The base is **nights** (E1 = 4 × 50 = 200), matching the operator's form note
> "Lůžkoden = osoba x počet nocí". This is the correction vs the on-hold guest plan
> (which used nights − 1).

---

## 7. Exemptions are host-only (no guest input)

No guest-facing checkbox or claim row. A self-serve "exempt" field is an abuse
magnet, and the law places the decision (and the evidence duty, §3g) on the host.

On the stay detail page, in the **Poplatek z pobytu** panel: every counted guest
row shows an **Exempt** action. Choosing it opens a required reason input (≤120
chars) and posts to `POST /stay-fees/guest-decision` with `guest_id` and
`decision=exempt`. A guest marked exempt can be returned to *charge* (clears the
reason) with the same route, `decision=charge`.

- `fee_host_decision = NULL` → the automatic rule applies.
- `fee_host_decision = 'exempt'` → 0 liable; reason stored and surfaced in the CSV
  as the §3g(2)(e) "reason for exemption".
- `fee_host_decision = 'charge'` → host forces liable (overrides under-18).

The buttons use the same POST pattern as other host actions on the stay page
(`_csrf`, redirect back).

### 7.1 Local-resident hint (soft, never auto-exempt)

A guest **přihlášen** in the property's obec is not a poplatník at all (§3, §16c),
but UbyHost's `res_city` is a self-declared address, not proof of registration, and
"where you live" ≠ "where you're registered". So UbyHost never auto-exempts on it.

Optional hint on the stay page: when a guest's declared `res_city` equals the
property's `addr_obec`, render a muted note: *"Guest's declared city matches this
property's municipality. Verify their registration against their ID before
exempting."* The host then marks **Exempt** with reason "local resident" only after
checking the ID.

---

## 8. Template + on-demand PDF + signature

### 8.1 The template is filled once, reused every month

The template fields live on the property (`stay_fee_authority_*`, `stay_fee_vs`,
`stay_fee_council_account`) and the legal entity (`name`, `signature_*`). The host
edits them in the property panel (§9) and the entity form (§9). After that, nothing
is re-entered month to month.

### 8.2 The PDF is prepared on demand, never pre-generated

Nothing is rendered ahead of time. The list (§9) shows live figures (cheap sums).
When the host clicks **Download PDF**, UbyHost renders the single A4 page from the
live figures plus the template and streams it. Nothing is persisted — re-downloading
re-computes from the current guest data. This is the same pattern the invoices
already use (`invoice_pdf.render` on demand).

### 8.3 Signature — entity-level only

The hlášení ends with **DATUM** and **PODPIS, RAZÍTKO**. The signature is stored
**once per legal entity** and reused on every hlášení:

1. **Stored signature** (default): the host uploads an image once on the legal
   entity (`signature_png_enc`). Every hlášení auto-places it above the line.
2. **Typed name** (fallback): if no image, UbyHost prints `signature_name`
   (e.g. "Josef Pechar") above the line.

No per-document override in v1 — one signature per entity is enough. The signature
is a completeness nicety, not a legal requirement (§2). The footer instruction line
already tells the host to send e-mail "POUZE S PŘILOŽENÝM ELEKTRONICKÝM PODPISEM",
so UbyHost never signs anything on the host's behalf.

---

## 9. Routes and screens (mirror the invoice section)

New file `App/app/routes/stay_fees.py`, registered after `admin.router`
(alongside `invoices.router`).

### 9.1 Routes

| Route | Purpose |
|---|---|
| `GET /stay-fees` | list: per property (rate > 0) the month's liable/exempt/total + actions |
| `GET /stay-fees?month=YYYY-MM` | scope the list to a month |
| `GET /stay-fees/{apartment_id}?month=YYYY-MM` | detail: figures + payment panel (council account, VS, QR Platba) + PDF/CSV actions |
| `GET /stay-fees/{apartment_id}/pdf?month=YYYY-MM` | **on-demand** render, streams the PDF |
| `GET /stay-fees/{apartment_id}/csv?month=YYYY-MM` | guest-level CSV (evidenční kniha) |
| `POST /stay-fees/guest-decision` | host sets `fee_host_decision` on a guest (§7) |

Every action is on-demand and stateless — no status is stored, nothing is frozen.

**Period display.** A monthly property shows the calendar month ("Srpen 2026"); a
quarterly property shows the quarter ("Q3 2026"). A stay counts in the period of its
checkout.

**List layout.** A sticky `.page-header` (eyebrow "Records", h1 "Poplatek z
pobytu", a one-line lede) with a **month chip selector** in the actions slot
(Červenec / **Srpen** / Září 2026). Below it, one `.panel.tight` + `.table-cards`
table: **Property · Období · Lůžkodny podléhající · Osvobozené · Celkem · action**.
Each row is a `.clickable-row` (the whole row opens the detail). The property cell
shows the name (bold) + "Praha 3 · sazba 50 Kč" (muted). The action cell is a blue
`pill` "Zobrazit". A muted footnote: "Only properties with a rate set appear here…".
Match `/tmp/opencode/stay-fees-list.jpg`.

### 9.2 Sidebar

`templates/base.html`, `nav.records` group, after **Invoices**:

```
Reports · House book · Invoices · Poplatek z pobytu
```

New `nav_icon('coins')` — two overlapping circles in the existing 1.5px stroke
family. `nav` value is `stay_fees`.

### 9.3 Property panel — `#stay-fee-settings`

In `apartment_form.html`, a new `section-nav` link **"Poplatek z pobytu"** between
**Guest link** and **Calendars**, opening a panel with:

- rate (number 0–50), cadence (select monthly/quarterly)
- council account (text, validated with `payments.normalise_account`)
- variabilní symbol (text)
- úřad name (textarea), úřad address (text), úřad contact line (text)

Hint under rate: "0 = off" / the obec decree line. A muted warning (same pattern as
the existing no-IBAN warning) shows when rate > 0 but VS or council account are
empty. Saved by the page's existing **Save changes** button.

**Copy from another property.** A host with several properties in one obec would
otherwise retype the same rate, VS and úřad. So the panel gets a copy control.

- In `routes/admin.py::apartment_detail`, add to the render context the host's other
  properties that already have `stay_fee_rate_czk > 0`:
  `"fee_template_peers": [...]`, each entry
  `{id, internal_name, rate_czk, cadence, council_account, vs,
    authority_name, authority_address, authority_contact}`.
- In `apartment_form.html`, inside `#stay-fee-settings`, render only when
  `fee_template_peers` is non-empty:

  ```html
  <div class="field">
    <label for="fee-copy-from">{{ t('apartment.form.stay_fee.copy_label') }}</label>
    <select id="fee-copy-from">
      <option value="">…</option>
      {% for p in fee_template_peers %}
      <option value="{{ p.id }}"
              data-rate="{{ p.rate_czk }}" data-cadence="{{ p.cadence }}"
              data-account="{{ p.council_account or '' }}" data-vs="{{ p.vs or '' }}"
              data-authority-name="{{ p.authority_name or '' }}"
              data-authority-address="{{ p.authority_address or '' }}"
              data-authority-contact="{{ p.authority_contact or '' }}">{{ p.internal_name }}</option>
      {% endfor %}
    </select>
    <button type="button" class="btn small" id="fee-copy-apply">{{ t('apartment.form.stay_fee.copy_button') }}</button>
    <div class="hint">{{ t('apartment.form.stay_fee.copy_hint') }}</div>
  </div>
  ```

- A small handler in `app.js` on `#fee-copy-apply` reads the selected `<option>`'s
  `data-*` and sets the form fields (`stay_fee_rate_czk`, `stay_fee_cadence`,
  `stay_fee_council_account`, `stay_fee_vs`,
  `stay_fee_authority_name`, `stay_fee_authority_address`,
  `stay_fee_authority_contact`). It writes nothing server-side until the host hits
  **Save changes**. The multi-line úřad name is carried as a string into the
  textarea.

### 9.4 Entity form — signature

In `entities.html`, add a signature block (upload an image, or type a name). The
image is encrypted at rest via the `guest.signature_png_enc` pattern.

### 9.5 Stay detail — the `#money` slot

The empty/guarded `#money` group on `reservation_detail.html` gets the fee panel:
a compact per-guest list, each row with the **Exempt** action (§7), guests with an
unresolved decision highlighted, the stay total, and an "Open in Poplatky" link.

### 9.6 Stay-fee detail — payment panel + QR Platba

Clicking a property's month on the list opens a detail view (`/stay-fees/{id}`).
Besides the figures and the Download PDF / CSV actions, it shows a **payment panel**
so the host can actually remit the fee. **This panel is host-facing only — it is a
convenience for the host to pay the council, and nothing in it ever appears on the
hlášení PDF** (which stays faithful to the form):

- **Council account** (copyable), **IBAN** (copyable), **variabilní symbol** (copyable).
- A **QR Platba** (SPAYD) image built from
  `payments.spayd(council_iban, total_czk, vs, "POPLATEK Z POBYTU <vs>")` +
  `payments.qr_png_bytes(...)`. The host scans it in their own banking app to pay the
  council directly.

The account, IBAN and VS all come from the host's own inputs (`stay_fee_council_*`,
`stay_fee_vs`), so the QR is meaningful only once those are set. The QR needs
`stay_fee_council_iban`, which `payments.normalise_account` derives from the typed
council account (and rejects a malformed account before any QR is produced).

**Detail layout.** A `.back-link` ("← Zpět na přehled"), then a `.page-header`
(eyebrow "Poplatek z pobytu", h1 "Apartmán Vinohrady — Srpen 2026", lede) with
**Stáhnout CSV** and **Stáhnout PDF** (primary) in the actions. Below it a
`.detail-hero` metrics strip (four tiles): **Lůžkodny podléhající 83** ·
**Osvobozené lůžkodny 30** · **Celková částka 4 150 Kč** · **Variabilní symbol
1234567890**. Then a section heading **"Platba úřadu"** with a green pill
"Připraveno k zaplacení", and a payment panel: council account / IBAN / VS rows
(each a `.copyrow` with a readonly input + a "Kopírovat" button), then a QR block
(`qr-platba.png` + the SPAYD payload as muted text). A muted footnote: "Tyto
platební údaje zadává hostitel sám…". Match `/tmp/opencode/stay-fees-detail.jpg`.

---

## 10. CSV export (the evidenční kniha)

Columns matching §3g(2) exactly (mirror `housebook.housebook_csv` style: `;`
separator, UTF-8 BOM):

- (a) stay from · stay to
- (b) guest name · address of residence
- (c) date of birth
- (d) document type · document number
- (e) fee amount (Kč) **or** reason for exemption

Plus helper columns: property name · period · rate · VS · council account.

The host keeps this CSV for 6 years as their electronic evidenční kniha (§3g(4)).

---

## 11. Owner decisions (resolved 29 Sep 2026)

- **Copy from another property** — added (§9.3).
- **Signature** — entity-level only, no per-document override (§8.3).
- **Cadence** — monthly and quarterly, per property (§2, §5.1).
- **Tracking** — none. Pure calculator: compute → download. No status, no remitted
  state, no frozen snapshots (§5.3, §9.1).
- **ZTP/P / local-resident proof** — host responsibility; UbyHost never asks for a
  card scan (§7).

---

## 12. i18n keys (host UI — EN / CS, parity-tested; the PDF is Czech-only)

### Host section (sidebar, list, actions)

| Key | EN | CS |
|---|---|---|
| `nav.stay_fees` | Poplatek z pobytu | Poplatek z pobytu |
| `stay_fees.title` | Poplatek z pobytu | Poplatek z pobytu |
| `stay_fees.lede` | Monthly municipal stay-fee totals for your properties. | Měsíční přehled poplatku z pobytu pro vaše nemovitosti. |
| `stay_fees.liable_days` | Liable bed-days | Lůžkodny podléhající poplatku |
| `stay_fees.exempt_days` | Exempt bed-days | Osvobozené lůžkodny |
| `stay_fees.total` | Total | Celkem |
| `stay_fees.download_pdf` | Download PDF | Stáhnout PDF |
| `stay_fees.download_csv` | Download CSV | Stáhnout CSV |
| `stay_fees.no_rate` | Set a rate to enable the stay fee for this property. | Nastavte sazbu pro aktivaci poplatku u této nemovitosti. |

### Property panel (`apartment_form.html`)

| Key | EN | CS |
|---|---|---|
| `apartment.form.stay_fee.heading` | Poplatek z pobytu | Poplatek z pobytu |
| `apartment.form.stay_fee.rate_label` | Rate per person per night (Kč) | Sazba za osobu a noc (Kč) |
| `apartment.form.stay_fee.cadence_label` | Remittance period | Období odvodu |
| `apartment.form.stay_fee.cadence.monthly` | Monthly | Měsíčně |
| `apartment.form.stay_fee.cadence.quarterly` | Quarterly | Čtvrtletně |
| `apartment.form.stay_fee.account_label` | Council account | Účet obce |
| `apartment.form.stay_fee.vs_label` | Variabilní symbol (from the council) | Variabilní symbol (od obce) |
| `apartment.form.stay_fee.authority_name_label` | Municipality office name | Název úřadu |
| `apartment.form.stay_fee.authority_address_label` | Municipality office address | Adresa úřadu |
| `apartment.form.stay_fee.authority_contact_label` | Office contact line (tel, e-mail, account) | Kontaktní údaje úřadu (tel., e-mail, účet) |
| `apartment.form.stay_fee.missing_warn` | Set a variabilní symbol and council account to generate the hlášení. | Pro vygenerování hlášení zadejte variabilní symbol a účet obce. |

### Host stay page — exemption decision

| Key | EN | CS |
|---|---|---|
| `stay_fee.decision.exempt` | Exempt | Osvobodit |
| `stay_fee.decision.charge` | Charge | Zpoplatnit |
| `stay_fee.decision.reason_label` | Reason (required) | Důvod (povinné) |

### Entity form — signature

| Key | EN | CS |
|---|---|---|
| `entity.signature_label` | Signature (image or typed name) | Podpis (obrázek nebo jméno) |
| `entity.signature_name_label` | Typed name (fallback) | Jméno (náhrada za podpis) |

---

## 13. Implementation order (one commit per step)

1. **DB** — add the `apartment.stay_fee_*`, `legal_entity.signature_*`, and
   `guest.fee_host_*` columns (§5).
2. **`validation.age_on`** — the small helper the under-18 rule needs (does not
   exist in the repo today).
3. **`payments.py`** — land `normalise_account`, `format_iban`, `spayd`,
   `qr_png_bytes` from `PLAN_POPLATEK_Z_POBYTU.md` §5 with `tests/test_payments.py`.
4. **`stay_fee.py`** — the calculation core (§6) with `tests/test_stay_fee.py`
   (the E1–E6 table).
5. **Property panel** — `apartment_form.html` `#stay-fee-settings` (incl.
   copy-from-another) + payload handling in `routes/admin.py`.
6. **Entity signature** — `entities.html` signature block + encrypted storage.
7. **Host decision panel** — `reservation_detail.html` exempt action +
   `POST /stay-fees/guest-decision` (§7).
8. **Section shell** — sidebar `nav.stay_fees`, `routes/stay_fees.py` list route,
   `templates/stay_fees.html`.
9. **Detail + payment panel** — `/stay-fees/{id}` detail view: figures + copyable
   council account / IBAN / VS + QR Platba (§9.6).
10. **PDF** — extend `invoice_pdf.py` with the hlášení renderer (§1),
    `/stay-fees/{id}.pdf` on demand.
11. **CSV** — `/stay-fees/{id}.csv` matching §3g columns (§10).
12. **i18n + parity tests** — every §12 key in `en` and `cs`.

---

## 14. Explicit non-goals for v1

- No guest-facing fee amount, QR code, or payment collection (that is the on-hold
  `PLAN_POPLATEK_Z_POBYTU.md`, and it stays on hold). The **host-facing** QR Platba
  for paying the council (§9.6) is in scope.
- No electronic filing into any obec portal, no datová schránka integration.
- No bank-API or payment verification.
- No municipality-specific form replica (the hlášení is the standard three-figure
  summary, not a clone of any one obec's paper form).
- No status or "remitted" tracking at all — the tool computes and downloads, nothing
  is recorded.
- No per-document signature override (one entity-level signature only, §8.3).
- No guarantee of the host's legal compliance (tool assists only).
