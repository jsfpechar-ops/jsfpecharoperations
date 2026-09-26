# PLAN — Standalone invoice builder for UbyHost (v2, as built)

> **What this is.** A host-only invoicing tool. The host opens **Invoices → New
> invoice** and builds a document from scratch: pick the supplier (operator),
> fill in the customer, and add **any number of line items** (description,
> quantity, unit, unit price, VAT rate 0 / 12 / 21 %). UbyHost numbers it, renders
> the PDF, and stores it immutably.
>
> **The invoice is NOT connected to a stay.** There is no reservation link, no
> "issue from a stay", no automatic amounts. It is a free-form generator for the
> host.
>
> **What this is not.**
> - No guest access at all: no guest request flow, no public request page, no
>   request tokens. A guest only ever receives a download link the host chose to
>   e-mail them.
> - No recurring invoices, proformas, reminders, quotes or accounting export.
> - No foreign currency (CZK only).
> - No editing of an issued document. A correction is always a new document
>   (storno for non-payers, ODD for payers).
> - No Fakturoid API, account or dependency.

**Status:** implemented and merged. Host-only Phase 1 = the whole feature.
**Rule of record:** the form is deliberately flexible (no line limit, VAT 0/12/21);
earlier drafts limited it to 3 lines and VAT 12/21 only — ignore those.

---

## 0. Non-negotiables (read first)

1. **Standalone.** Never re-attach an invoice to a reservation, apartment or stay
   fee. `invoice.reservation_id` / `apartment_id` stay NULL.
2. **Unlimited line items.** The form posts parallel arrays
   (`item_description[]`, `item_quantity[]`, `item_unit[]`, `item_unit_price[]`,
   `item_vat_rate[]`). Parse them with `form.getlist`.
3. **VAT is 0 / 12 / 21 %**, chosen per line. For a **payer**, the unit price is
   **without VAT**; VAT is added on top per line. For a **non-payer**, there is no
   VAT at all (amounts only).
4. **An issued invoice never changes.** Content columns are frozen by SQLite
   triggers; downloads always serve the stored `pdf_blob`.
5. **Host-only.** Every route starts with `auth.require_login`; every row is
   scoped through `access.*` / `owner_user_id`. The one public route is the
   signed download link.
6. **Deploy to staging first**, not production.
7. Light mode only; reuse existing CSS, no new chips or cluttered tables.

---

## 1. How it works (one page)

| Topic | Decision |
|---|---|
| Entry point | Sidebar → Records → **Invoices** (`/invoices`). "New invoice" → `/invoices/new`. |
| Supplier | The chosen `legal_entity` (operator); its details are snapshotted into the invoice at issue. |
| Customer | Typed fresh: name, street, city, postcode, country, IČO, DIČ, e-mail. Never taken from guest registration data. |
| Line items | Any number. Each: description, quantity, unit, unit price, VAT rate. |
| Amounts | Payer: `base = qty × unit_price`, `vat = base × rate/100`, `gross = base + vat`. Non-payer: `gross = qty × unit_price`, no VAT. All in haléře. |
| Number | Per **legal entity**, `{prefix}{YYYY}-{NNNN}`, yearly restart, gap-free (see §4). |
| VS | `{YYYY}{NNNN}` (digits of the number). |
| Lifecycle | Issue → (optional) mark paid, (optional) send to customer, (optional) correct with storno/ODD. |
| Payment | UbyHost never processes money. The PDF shows the operator's IBAN + QR Platba; the host marks paid. |
| Corrections | Mirrors the original's snapshot with negative amounts. |
| Retention | 10 years from the end of the issue year (conservative for all VAT statuses). |

---

## 2. Legal minimum for this document

The operator's `legal_entity.vat_status` ∈ `non_payer` (default) | `identified` | `payer`.

**All invoices must show:** document number; supplier name + seat + IČO (+ registry
entry); customer name + address (+ IČO/DIČ if given); subject and scope (line
description, quantity or unit price); the total; the issue date; the payment
details and VS.

**A payer additionally (daňový doklad):** supplier DIČ; customer DIČ if they have
one; DUZP if it differs from the issue date; per line the unit price without tax,
the VAT base, the rate and the VAT amount in CZK; a VAT recap grouped by rate.
The title becomes "Faktura – daňový doklad".

**Non-payer:** amounts only, no rate/base/VAT columns; footer "Nejsem plátce DPH.".

These are enforced by `invoices.validate_for_issue()`, which blocks issuing when a
required seller/customer field or at least one line item is missing.

### Flags that still want a lawyer/accountant
- **FLAG-1** — registry-entry wording; whether a private (non-živnost) host can
  issue an invoice at all.
- **FLAG-4** — VAT treatment of a stay fee on a payer's document (in the standalone
  model the stay fee is just another line; the host picks its rate).
- **FLAG-8** — 10-year retention for all statuses (ZoÚ §31 is 5 years; VAT payers
  §35(2) is 10). The 10-year choice is deliberately conservative.
- Payer edge cases: DUZP vs platform payout date, top-up from net, storno vs ODD
  after a status change, advance payments.

---

## 3. Data model (`App/app/db.py`)

`legal_entity` gains: `vat_status TEXT NOT NULL DEFAULT 'non_payer'`,
`registry_entry TEXT`, `invoice_prefix TEXT`, `invoice_next_number INTEGER`,
`invoice_next_number_year INTEGER`, `invoice_due_days INTEGER NOT NULL DEFAULT 14`.
(Bank fields `bank_account` / `iban` / `bic` come from the stay-fee work.)

Tables:

- `invoice_sequence(legal_entity_id, year, last_no)` — the numbering counter.
- `invoice` — the snapshot. `reservation_id` / `apartment_id` / `stay_*` are
  nullable and stay NULL. Content columns are guarded by triggers
  (`invoice_issued_guard`, `invoice_delete_guard`); bookkeeping columns
  (`marked_paid_at`, `emailed_at`) stay writable. Unique on `(legal_entity_id,
  number)` and `(legal_entity_id, seq_year, seq_no)`; unique partial index on
  `corrects_invoice_id`.
- `invoice_item` — `kind`, `description`, `quantity`, `unit`, `vat_rate`,
  `base_haler`, `vat_haler`, `gross_haler`; frozen by triggers once the invoice is
  issued.

---

## 4. Numbering, immutability, corrections, retention (`App/app/invoices.py`)

**Numbering** — `allocate_number(cur, entity, year)` runs inside
`db.immediate()` (BEGIN IMMEDIATE), so writers serialise and the number, rows and
PDF commit together (no gaps, no duplicates). One-time continuation: a host who
already issued this year elsewhere sets `invoice_next_number` for
`invoice_next_number_year`; it is used once and cleared.

**Issue** — `issue(draft, actor)` validates, allocates, inserts the invoice +
items, renders the PDF, stores `pdf_blob` + `pdf_sha256`, sets `issued_at`. A
render failure rolls the whole thing back, so the number is not consumed.

**Corrections** — `cancel(invoice_id, reason, correction_date, actor, today)`:
non-payer → `kind='storno'`; payer → `kind='corrective'` (ODD) with the §45 fields.
Items and totals are copied with negative amounts; one correction per invoice
(unique index).

**Retention** — `purge_expired(today, owner_user_id)` deletes invoices with
`issue_date` before `(today.year − 10)-01-01`, unlocking the delete guard for the
operation only. Wired into `POST /settings/purge-expired`.

---

## 5. PDF (`App/app/invoice_pdf.py`)

Copied from `docs/plans/invoice-design/invoice_pdf_reference.py` (three path
edits). The host is the hero; UbyHost appears only as the coral top rule, the
coral document-type label and the footer credit. DejaVu Sans (vendored) renders
Czech.

Payer item rows show **description + `{qty} {unit} × {unit price}`**, then
**Bez DPH · Sazba · DPH · Celkem**, with a VAT recap grouped by rate. Non-payer
rows show **Popis · Množství · Cena**. Preview mode draws a diagonal watermark and
the number "—". The stored bytes are never re-rendered.

---

## 6. Routes (`App/app/routes/invoices.py`)

Host routes (login required, owner-scoped):

| Method + path | Purpose |
|---|---|
| `GET /invoices` | list (with a "New invoice" button) |
| `GET /invoices/new` | the builder form |
| `POST /invoices/preview` | render an unsaved draft to a PDF (inline, watermark) |
| `POST /invoices` | validate + issue → 303 to the detail |
| `GET /invoices/{id}` | detail (items + actions) |
| `GET /invoices/{id}.pdf` | stored PDF |
| `POST /invoices/{id}/paid` | mark paid |
| `POST /invoices/{id}/send` | e-mail the customer a download link |
| `POST /invoices/{id}/cancel` | storno / ODD |

Public:

| `GET /invoice/d/{token}` | signed, 30-day download link (rate-limited) |

---

## 7. The builder form (`templates/invoice_form.html`)

Supplier select, customer block, an items table with **Add line / Remove**, a
payment block (already paid, paid via, due date, DUZP), an invoice-language picker
(cs/en), and an optional note. Vanilla JS clones a template row for "Add line";
the form works with JS off (one row is present server-side). The footer shows the
next number, **Preview** (`formtarget="_blank"`) and **Issue** (confirm dialog).

---

## 8. Send to customer (`mail_notify.build_invoice_issued`, `invoice_links.py`)

Only the host triggers it. It builds a money panel with the number and total and
one coral "Download invoice" button whose URL embeds a signed token
(`invoice_links.download_token`, 30 days; carries a prefix of the stored PDF hash).
The token is queued via `mail.CLAIM_SECRET_MARKER` and stored encrypted; the
outbox never holds a working link. `invoice_issued` is a guest mail kind, so
Reply-To is the operator.

---

## 9. Stay fee (separate feature, for context)

The stay fee is **off by default**: `stay_fee_policy` defaults to `off` and the
rate defaults to 0, so nothing renders until a host opts in per property. See
`PLAN_POPLATEK_Z_POBYTU.md`. It is independent of this invoice tool.

---

## 10. Tests (`App/tests/`)

| File | Covers |
|---|---|
| `test_invoice_vat.py` | `vat_parts`, the free-form draft, 0% rate, unlimited items, the issue gate |
| `test_invoice_numbering.py` | `2026-0001`, prefix, yearly restart, one-time continuation, 20 concurrent issues with no gaps, a PDF failure consumes no number |
| `test_invoice_corrections.py` | storno negative lines; ODD §45 fields; one correction per invoice; short reason refused |
| `test_invoice_immutability.py` | content updates/delete/items raise on issued rows; bookkeeping allowed; purge only past 10 full years |
| `test_invoice_pdf.py` | renders non-payer / payer / preview / storno / ODD; PDF magic; UbyHost credit |
| `test_invoice_entity.py` | IČO checksum; entity invoice settings; delete guard |
| `test_invoice_ux.py` | builder form; issue + PDF download; mark paid; send + download token; no-operator error |

---

## 11. Sign-off status (researched 2026-09-26, official sources)

Confirmed: 12% / 21% VAT rates and the VAT rates table; the 15-day rule (§28(8));
§29(1) invoice elements; §35(2) 10-year retention; OZ §435 registry entry.
Still open: FLAG-1 (private host), FLAG-8 (retention window), and the payer edge
cases above. All are account/lawyer questions, not code blockers.

## 12. Sources

- Zákon č. 235/2004 Sb., o DPH (§28, §29, §35, §45, §47) — e-Sbírka.
- Zákon č. 563/1991 Sb., o účetnictví (§11, §31).
- Zákon č. 89/2012 Sb., občanský zákoník (§435).
- qr-platba.cz — SPAYD 1.0 (QR Platba).
- ARES REST API (IČO validation reference).
