# Invoices only for stays (not a general invoicing tool)

Status: owner-approved 2026-10-08. Briefs [0019](../tasks/0019-stay-invoice-rules.md) (backend) and [0020](../tasks/0020-stay-invoice-pages.md) (pages) ready; 0021 (alert) after 0020. The briefs win where they differ from this plan.

## 1. Problem

The invoice builder (`App/app/invoices.py`, `App/app/routes/invoices.py`) is free-form. The module docstring says it outright: "The invoice is NOT tied to a stay". Every line takes free text, a quantity, a unit and a price, up to 4 lines and 10M CZK each. A host can invoice consulting, car sales or anything else, so UbyHost works as a free Fakturoid. That is not the product: support load, reputational and tax-adjacent risk, and no link to the stay/UbyPort data that is the point of the app.

## 2. Owner decisions (2026-10-08)

| # | Decision |
|---|---|
| D1 | Every new invoice belongs to exactly one stay (`reservation_id` required). No blank invoice. |
| D2 | A stay the host doesn't have in UbyHost (walk-in, cash) is created by the host first, with the existing manual stay form (`POST /reservations`, `source='manual'`: property + dates). No new path. |
| D3 | Hard limit per stay: one active invoice. A new one only after the first is cancelled (storno/ODD), and at most 3 invoices ever per stay. |
| D4 | Line 1 is the accommodation line, built from the stay: fixed wording, nights = quantity, host types only the price. Lines 2–4 are extras from a fixed list. Extras are capped (§5). |
| D5 | Buyer fields stay editable (a company pays for the guest's business trip). The guest's e-mail is pre-filled when the stay has one. |
| D6 | No multi-stay invoice. |
| D7 | Existing standalone invoices: read-only, still listed, downloadable, sendable and cancellable. Never edited or back-linked. |
| D8 | The stay-fee remittance tool is not touched. |
| D9 | Admin alert for hosts whose invoicing looks out of line with their stays (§7). Separate brief after D1–D4 ship. |

## 3. Where things are (checked in code at 2f4c107)

- `invoice` table already has `reservation_id`, `stay_from`, `stay_to`, `stay_label` (`App/app/db.py:~420–470`). `_invoice_columns` already writes them (`invoices.py:336–380`). Nothing fills them today.
- `invoice_item.kind` exists, CHECK `('accommodation','stay_fee','other')`. The stay line is stored as `accommodation`, the stay fee as `stay_fee`, every other extra as `other`; the exact extra kind lives only in the draft. No table rebuild.
- `idx_invoice_reservation` already exists: **no migration**.
- `invoice_pdf.py:206` already prints `stay_label` under the header, so the PDF shows the stay once the label is filled.
- `routes/invoices.py:480 _stay_property_name()` already looks up the property from `reservation_id`.
- Manual stays: `routes/admin.py:1505 POST /reservations` creates `source='manual'` rows. `access.reservation(request, id)` (`App/app/access.py:92`) is the owner-scoped lookup.
- Corrections copy the original's items and `reservation_id` (`invoices.py:462–515`), so a storno of a legacy invoice has `reservation_id = NULL`. That is fine: the stay rule only applies to `kind = 'invoice'`.
- Known issues in this area: K-I01 (double submit gives two numbers) is fixed as a side effect of D3. K-I02..K-I06 stay as they are.

## 4. Flow

1. Stay detail page (`reservation_detail.html`) gets one action: **Vystavit fakturu / Issue invoice** → `GET /invoices/new?reservation_id=N`. If the stay already has an active invoice, the action links to that invoice instead.
2. `GET /invoices/new` without `reservation_id` shows a stay picker: a plain `<form method="get">` with a `<select>` of the host's eligible stays (§5.1), newest check-in first, plus a link "Stay not in the list? Add it" → the manual stay form. No JavaScript needed.
3. With a valid `reservation_id`, the form shows the accommodation line already built (§5.2), up to 3 extra rows (§5.3), buyer, payment and note as today. The `reservation_id` travels as a hidden field to preview and issue.
4. `POST /invoices/preview` and `POST /invoices` re-check everything server-side. Any hidden-field or quantity tampering is ignored or refused; the form values are never trusted for the stay line.
5. `/invoices` list: no "New invoice" blank button. The button opens the picker. Legacy rows show as today.

## 5. Rules (server-side, in `invoices.py`)

### 5.1 Eligible stay

- `access.reservation(request, id)` returns it (same owner/workspace); otherwise 404.
- `status` is not `cancelled` (archived stays are fine: a host often invoices after archiving).
- Nights = `date_to − date_from`, at least 1.
- Window: `date_to ≥ today − 400 days` and `date_from ≤ today + 365 days` (today in Europe/Prague). Old stays need nothing new; very old or far-future stays are a typo or abuse.
- When the stay's property has `apartment.legal_entity_id`, the invoice must use that entity (pre-selected, other choices refused). When it is NULL, any of the host's entities, as today.

### 5.2 Accommodation line (kind `stay`)

- Description, fixed: `Ubytování – {property}, {dd.mm.yyyy} – {dd.mm.yyyy} ({n} noci)`; en `Accommodation – …  ({n} nights)`. `{property}` = `uby_name` or `internal_name` (same as `_stay_property_name`).
- Posted description, quantity and unit for line 1 are ignored.
- The host types the total price for the stay. Quantity 1, unit `pobyt`/`stay`; the nights are in the wording (`(3 noci)`). No per-night mode: simpler form, no rounding.
- Price must be > 0. VAT rate selectable for payers as today (accommodation is 12 % in CZ; default 12).
- `stay_from`, `stay_to`, `stay_label` (= the description without the prefix) are written to the invoice row, and DUZP defaults to `date_to` (still editable).

### 5.3 Extras (lines 2–4)

Fixed list (`EXTRA_KINDS` in `invoices.py`; labels in `host_i18n.py`, printed text in cs/en):

| kind | cs | en |
|---|---|---|
| `cleaning` | Úklid | Cleaning |
| `stay_fee` | Poplatek z pobytu | Local stay fee |
| `breakfast` | Snídaně | Breakfast |
| `parking` | Parkování | Parking |
| `pet` | Domácí zvíře | Pet |
| `extra_bed` | Přistýlka | Extra bed |
| `late_checkout` | Pozdní odjezd | Late check-out |
| `other` | free text, max 60 characters | free text, max 60 characters |

- At most one `other` line.
- Quantity 1–99, price > 0.
- **Cap (constants, easy to change):** all extras together ≤ 100 % of the accommodation line (gross); the `other` line alone ≤ 30 % of the accommodation line. Breaking a cap is a validation error with the limit in the message, not a silent change.

### 5.4 Per-stay limit (D3)

Inside the same transaction that allocates the number (`allocate_number`, `invoices.py:310`):

- Count `kind = 'invoice'` rows with this `reservation_id` that have no storno/corrective pointing at them. If ≥ 1 → refuse with a link to the existing invoice.
- Count all `kind = 'invoice'` rows with this `reservation_id`. If ≥ 3 → refuse ("This stay already has 3 invoices").
- The check and the insert run in one write transaction, so a double click yields one invoice and one error (fixes K-I01).
- No trigger: the rule lives in Python with tests, and legacy rows stay valid. "Stay required" is enforced in the routes (issue and preview); `build_draft(stay=None)` keeps the old path for corrections and old tests.

### 5.5 What doesn't change

Numbering, VAT maths, PDF layout (beyond filling `stay_label`), immutability trigger, retention (no new personal-data field: buyer fields already exist and are in `retention.py`), mail sending, download tokens, corrections.

## 6. Answers to owner questions

- **Old PDF versions:** there are none. A PDF is rendered once at issue and stored on the invoice row (`invoice.pdf_blob` + `pdf_sha256`). The DB trigger `invoice_issued_guard` stops it from changing. "Preview" PDFs are rendered on request and never stored. A cancellation creates a **new** invoice (storno/ODD) with its own PDF. The original stays, because the law wants both. Both are visible in `/invoices` (state "cancelled" and filter "correction") and on each invoice's detail page. Size is about 5–30 KB each, kept 10 years (`invoices.purge_expired`, decision 2026-10-08). With the 3-per-stay cap a stay holds at most 3 originals + 3 stornos.
- **Why both a hard limit and an alert:** the limit (D3) stops repeat invoices on one stay. It can't see a host who makes many manual stays just to invoice them. The alert (§7) catches that pattern without blocking honest hosts.

## 7. Admin alert (brief 0021, later)

Once a day, per host, over the last 30 days: flag when `invoices_issued > 2 × stays_with_check_in` **or** `manual stays created > 20` **or** any invoice total > 100,000 CZK. Show a row in the existing admin alerts (`App/app/alerts.py`), no mail to the host, no block. Thresholds are constants. Written after 0019 is merged, so it counts real stay-linked rows.

## 8. Risks

| Risk | Answer |
|---|---|
| Honest host with no stay in the app | Manual stay form, linked from the picker (D2). |
| Existing tests post free-form invoices | Fixtures add a reservation; legacy behaviour is tested via a row with `reservation_id = NULL` inserted directly. |
| Stay fee under VAT | Municipal fee, outside VAT: rate forced to 0 for payers (owner, 2026-10-08). |
| Host cancels and re-issues to cycle | Capped at 3 invoices per stay. |
| Copy duplication | One explanation lives in the picker ("Invoices are issued for a stay"); the button says the rest. |

## 9. Open questions

None. (Q1 stay fee VAT: answered 2026-10-08, 0 %.)

## 10. Briefs

1. `0019-stay-invoice-rules`: backend rules in `invoices.py` + tests. No page change.
2. `0020-stay-invoice-pages`: picker, form, stay button, fixtures, browser test, screenshots.
3. `0021-invoice-abuse-alert`: §7 (brief written after 0020 is merged).
