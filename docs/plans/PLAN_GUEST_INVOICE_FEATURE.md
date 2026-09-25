# PLAN — Native "vyžádat fakturu" (guest invoice for a completed stay) for UbyHost

> **What this is.** This is an implementation plan for Cursor. It covers a small native feature: a **one-off invoice for one completed stay**. Either a past guest requests it, or the host creates it on the guest's behalf. It is modelled on how Fakturoid behaves; the whole public site, the help centre and the Almanach were read for this plan.
>
> **What this is not.**
> - **No Fakturoid API, account, embed or dependency** of any kind.
> - No recurring invoices, proformas, reminders, bank matching or accounting export.
> - No foreign currency.
> - No editing of an issued document. A correction is always a new document.
> - No e-mail is sent unless the guest asked for it or the host clicks *Send*.
>
> This is not accounting software. It covers VAT only as far as a **plátce DPH** must show it on this one kind of document. It gives no tax advice. Everything below is file → function → schema → copy, followed by an ordered build checklist.

**Research date for every source:** 2026-09-23 (§15). **Scope:** the host's legal entity or entities, invoicing stays at their properties anywhere in Czechia. Nothing here is city-specific.

**Conventions:** as in the stay-fee plan.
- **⚠ FLAG** = must be confirmed by an accountant or lawyer; every flag is repeated in §14.
- Copy is `key`: EN / CS. Translators use `%`-formatting, so **write "12 %" as `12 %%`** in any string that is formatted with kwargs.
- Parity tests: `tests/test_host_i18n.py`, `tests/test_guest_navigation.py`, `tests/test_guest_mail.py::test_the_three_catalogues_stay_at_exact_parity`.

**Dependency on the stay-fee plan (`PLAN_POPLATEK_Z_POBYTU.md` v2):** this plan reuses the following.
- `App/app/payments.py` (`normalise_account`, `format_iban`, `ascii_upper`, `spayd`, `qr_png_bytes`), plus the `legal_entity.bank_account` / `iban` / `bic` columns and entity-form fields. See its §4, §5 and §8.
- `stay_fee.stay_summary()` for the optional stay-fee line.

If this plan is built first, do **stay-fee steps 1, 2 and 4** (DB columns, `payments.py`, entity bank account) before step 1 here. Skip the stay-fee line (§4.5 row 2) until `stay_fee.py` exists.

---

## 0. Rules for the implementing agent (read first)

You are implementing a finished design. Do not redesign it.

1. **Build Phase 1 completely, and only then Phase 2** (§13). Phase 1 = the host issues invoices from a stay. Phase 2 = guests can request them. Phase 1 must be usable and green on its own.
2. **One step per commit.** Run `.venv/bin/python -m pytest tests -q` from `App/` after every step, without `PYTHONPATH=App` (`AGENTS.md`). Never start the next step while tests are red.
3. **Use exactly the names in this plan**: files, functions, columns, routes, translation keys. Copy all user-facing strings **verbatim** from §10 into **both** `en` and `cs`.
4. All translators use `%`-formatting: a literal percent sign is `%%`.
5. **An issued invoice must never change.** Never write code that UPDATEs a content column of an issued invoice, and never re-render the PDF of an issued invoice: always serve `pdf_blob`. The SQLite triggers in §5 enforce this. If a trigger error appears in your tests, your code is wrong, not the trigger.
6. **Security.**
   - Host routes: `guard = auth.require_login(request)` first, and load rows only through `access.*`.
   - Every POST form: `<input type="hidden" name="_csrf" value="{{ csrf_token }}">`.
   - Public routes: exactly the rate limits and the identical-response rule in §3.2.
7. **If the repo does not match this plan**, stop and report instead of guessing. Examples: a missing function, or a different template block.
8. Light mode only. Use existing CSS variables and components. The invoice PDF follows §7 exactly (the reference file).

**Reference for `db.immediate()`** (add to `db.py` next to `cursor()`; used by `invoices.issue`):

```python
@contextmanager
def immediate():
    """Like cursor(), but takes the write lock before the first read (BEGIN IMMEDIATE)."""
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        try:
            yield cur
            cur.execute("COMMIT")
        except Exception:
            cur.execute("ROLLBACK")
            raise
    finally:
        conn.close()
```

## 0.5 UX walkthrough (target experience; every screen below implements one row)

**Principles.**
- Issuing takes **one screen and two clicks**: Preview (optional), then Issue.
- The guest never sees accounting words they don't need.
- Every irreversible action has a confirm dialog, using the existing `data-confirm` pattern (`static/app.js`).
- Company-only fields appear only when "for a company" is ticked.

**Host (desktop first)**

| # | Screen | What the host sees and does |
|---|---|---|
| H1 | Legal entities → edit | a new **"Invoices"** fieldset under the bank fields: VAT status (3 radios with one-line explanations), registry entry (prefilled sentence for tradesmen), optional number prefix, "continue numbering from", default payment term. An *ARES* button next to IČO fills the name, sídlo, DIČ and registry entry. |
| H2 | Stay detail → panel **Invoice** (after the stay-fee panel) | **Without a request:** a quiet *Issue invoice* button and a *Link for the guest* disclosure (copy field + *Send to guest e-mail*). **With an open request:** the request is highlighted like a stay-fee review row (buyer name, submitted date), with *Issue invoice* as the primary coral button and *Decline* as a quiet link. **After issue:** a list of documents (number · date · total · paid/unpaid) with *PDF* and a *More* disclosure for cancel/correct. |
| H3 | Issue form `/reservations/{rid}/invoice/new` | one page, top to bottom: **Customer** (prefilled from the request; a "For a company" checkbox reveals IČO/DIČ + ARES) → **Items** (accommodation price first and focused; the stay-fee line pre-ticked when the fee was marked paid; *+ Other item*) → **Payment** ("Already paid" **ticked by default** with "via Airbnb/Booking/…", since most stays are prepaid by a platform; unticked reveals the due date) → **Language**. The sticky footer shows "Next number: 2026-0008", *Preview* (opens the PDF in a new tab) and *Issue invoice* (coral, with a confirm dialog: "Issued invoices can't be changed"). Warnings (no IBAN, 15-day rule for payers) show inline at the top, in amber. |
| H4 | Invoice detail `/invoices/{id}` | a success flash "Invoice 2026-0008 issued." Primary action: *Send to customer* if an e-mail is known, else *Download PDF*. Secondary: *Mark as paid* (unpaid only) and *Cancel / Corrective document* (confirm dialog, reason required). |
| H5 | Sidebar → Records → **Invoices** | two tabs (**Requests** with a count badge, **Documents**), newest first, with a year filter |

**Guest (phone first)**

| # | Screen | What the guest sees |
|---|---|---|
| G1 | Stay page, after checkout (`stay.html`) | a quiet link at the bottom: "Need an invoice for this stay? →" |
| G2 | Request form `/invoice/r/{token}` (one page, **not** a wizard) | a stay summary card; **Billing details**: name, street, city, postcode, country, and a "For a company" checkbox revealing IČO (+ *Fill in from ARES*) and VAT ID; optionally how much was paid and via what; delivery "I'll download it here" (default) or "Send it to my e-mail" (the e-mail prefilled); *Send to host*. Browser autofill works (`autocomplete` attributes below). |
| G3 | Same URL after sending | a status card: "Your host has your request" + *Edit details*. After issue: "Invoice 2026-0008 is ready" + **Download PDF**. After decline: the host's reason. The guest can bookmark this one URL; it is the whole journey. |
| G4 | Public `/invoice` (lost link) | two fields (e-mail used for registration, arrival date) + an optional booking code → always the same "Check your e-mail" page |
| G5 | E-mails | "Fill in your billing details" (a button to G2); if the guest chose e-mail delivery, "Invoice 2026-0008" (a button to the download). No attachments. |

---

## 1. What Fakturoid does, and what UbyHost takes from it

| Fakturoid behaviour (source) | Take? | UbyHost decision |
|---|---|---|
| Only the customer, items and price are needed; everything else is prefilled ("Faktura pod minutu", vytvoření faktury) | **Yes** | The host confirms one screen: buyer (prefilled from the request), amount, "already paid?". Everything else comes from the entity and the stay. |
| "Povinné náležitosti faktury pohlídá robot" (homepage) | **Yes** | Server-side `invoice.validate_for_issue()` blocks issuing when a legally required field is missing for the entity's VAT status (§2). |
| Number suggested from "nejvyššího z posledních 10 faktur"; warning "číselná řada všech faktur ze zákona navazovat" (číselné řady) | **Partly** | No free-typed numbers. The sequence is atomic and gap-free (§6). The one-time *next number* override exists only to continue a series started elsewhere. |
| Recommended format `rok-číslo` (2022-001); month variables restart the series (tipy pro číslování) | **Yes** | `YYYY-NNNN`, yearly restart. The optional entity prefix (e.g. `UB`) avoids colliding with invoices the host issues in other tools. |
| A separate series per document type (číselné řady FAQ) | **No** | One series per entity for invoices **and** storno/ODD. Fakturoid also puts ODD "do stejné číselné řady jako klasické faktury". |
| VS = invoice number without dashes, max 10 digits, not mandatory (variabilní symbol) | **Yes** | `2026-0012` → VS `20260012` |
| QR only for CZ in CZK/EUR with an account + VS; SK uses PAY by square; message ≤ 60 chars, caps, no diacritics; **no due date inside the QR** (QR kód na faktuře) | **Yes** | QR only for CZK and unpaid invoices, reusing `payments.spayd`. No `DT`. |
| Issued invoices can be edited (zpětné změny) | **No** | UbyHost issues immutable documents (SQLite triggers + stored PDF hash). A correction is a new document (§6.3). Rationale: a PDF may already be with the guest; the tax/accounting duty is to keep what was issued. |
| Neplátce: storno invoice = duplicate with negative items, "Storno k faktuře číslo XXXX" (storno faktury) | **Yes** | `kind='storno'` |
| Plátce: may not cancel; must issue ODD with a reason; **one ODD per invoice** (opravný daňový doklad) | **Yes** | `kind='corrective'`, only a full reversal in v1, one per invoice, followed by an optional reissue |
| Webfaktura = a public link without a password; the customer sees history (webfaktura) | **Partly** | A signed, **expiring** download link. No history, no "viewed" tracking, no payment gateway. |
| 11 invoice languages (faktura v cizím jazyce) | **Partly** | `cs` and `en`. `en` prints English with Czech sub-labels. |
| Foreign currency with the ČNB rate (faktura v cizí měně) | **No** | CZK only (non-goal) |
| Airbnb article: "Neplátci DPH na fakturách pro hosty neuvádí DPH, plátci uvedou sazbu DPH 12 % za ubytování a 21 % za doplňkové služby"; the poplatek "na faktuře musí být uveden zvlášť s nulovou sazbou DPH"; "Když nejste plátci DPH a host nepožaduje doklad, stačí…" | **Yes** (with ⚠ FLAG-4) | The stay fee is a separate line **outside the VAT base** |
| Recurring invoices, reminders, bank matching, expenses, exports, API, MCP (faktury-online, manifest) | **No** | Non-goals (§11) |

---

## 2. Legal minimum for this document

The host's `legal_entity` gets a new `vat_status` ∈ `non_payer` (default) | `identified` (identifikovaná osoba — typical for Airbnb hosts under the threshold, per the Fakturoid Airbnb article) | `payer`.

| Content | non_payer / identified | payer (daňový doklad) | Source |
|---|---|---|---|
| Title | "Faktura" (never "Daňový doklad") | "Faktura – daňový doklad" | Fakturoid náležitosti: "pojem ‚Daňový doklad' se týká pouze plátců" |
| Seller name ("jméno/firma") and sídlo | **required** | required (§29(1)(a), (4): "obchodní firma nebo jméno, dodatek ke jménu, sídlo") | OZ §435(1); DPH §29 |
| Seller IČO | required if assigned | required if assigned | OZ §435(1) |
| Registry entry | tradesman: "Fyzická osoba zapsaná v živnostenském rejstříku"; company: "zapsaná v obchodním rejstříku vedeném {soud}, oddíl {x}, vložka {n}" | same | OZ §435(1); Fakturoid náležitosti |
| Seller DIČ | non_payer: omit. identified: **omit on the document** (⚠ FLAG-2) | **required** §29(1)(b) | DPH §29 |
| Buyer designation | name + address (a business buyer adds IČO) | §29(1)(c) + buyer DIČ if they have one (§29(1)(d), (3)(b)) | DPH §29 |
| Document number | required (evidence) | "evidenční číslo daňového dokladu" §29(1)(e) | DPH §29 |
| Subject and scope | "Ubytování …, {dates}, {nights} nocí, {persons} os." | §29(1)(f) | DPH §29 |
| Issue date | required | §29(1)(g) | DPH §29; ZoÚ §11(1)(d) |
| DUZP | **must not appear** (neplátce may not use "DUZP"/"DPH" markers; the voluntary line "Nejsem plátce DPH" is allowed) | §29(1)(h), if it differs from the issue date → always printed | DPH §29; Fakturoid náležitosti |
| Unit price without tax, tax base, rate, tax in CZK | n/a | §29(1)(i)–(l) | DPH §29 |
| Due date | optional; the default if omitted is 30 days (OZ §1963). UbyHost prints it only on unpaid invoices. | same | Fakturoid náležitosti |
| Signature/stamp | **not required** (ZoÚ §11(1)(f) is the *podpisový záznam* of the persons responsible for the accounting case, not the issuer's signature) | same | ZoÚ §11; Fakturoid náležitosti |
| Deadline to issue | none | **within 15 days** of the tax point (§28(8)) → a warning when later | DPH §28(8) |
| Retention | ZoÚ §31(2)(b): 5 years (accounting units); income-tax evidence per DŘ §148 lhůta | **10 years from the end of the tax period** (§35(2)) | §35, §31 |
| Correction | storno document (Fakturoid) | ODD per §45(1)(a)–(k): original number, own number, **reason**, differences in base / tax / total, the date under §42(3) | DPH §45 |

**Decision:** keep every document **10 years from the end of the year of issue**, for all VAT statuses. This is the longest rule, and the volume is tiny. ⚠ FLAG-8.

---

## 3. Trigger and access

### 3.1 Four ways in

| # | Who | Entry point | Authentication | Result |
|---|---|---|---|---|
| A | Host | Stay detail → panel **Faktura** → *Vystavit fakturu* | host session | `GET /reservations/{rid}/invoice/new` → issue form (§8) |
| B | Host → guest | Same panel → *Odkaz pro hosta* (copy field) and optional *Poslat hostovi e-mailem* (only if `reservation.guest_email` or the claim e-mail exists) | signed token, `purpose="host"` | The guest opens `/invoice/r/{token}` → request form |
| C | Guest who still has stay access | `templates/guest/stay.html` footer link "Potřebujete fakturu?", shown when `date_to ≤ today`, `apartment.invoice_requests_policy == 'on'` and the page rendered normally (PIN + claim cookie already passed) | existing guest session | `GET /l/{token}/{rid}/invoice` → mints a request token server-side → 303 to `/invoice/r/{token}` |
| D | Past guest who lost access | Public page **`/invoice`** (linked from the guest confirmation mail footer and from `guest/_host.html` "Need an invoice?") | none → **e-mail on file + arrival date**; a magic link is sent to the e-mail **already stored** | same generic answer every time |

Paths C and D exist because completed stays are deliberately unreachable from the apartment link once they are complete: see `_reservation_for_guest` ("Completed forms outside both windows stay reachable only on a device that already confirmed the claim"). **Do not widen that rule.**

### 3.2 Public request `/invoice` — anti-enumeration and rate limits

**Router:** new file `App/app/routes/invoice_public.py`, declared as `router = APIRouter(dependencies=[Depends(security.protect_guest_post)])`, included in `main.py` after `guest.router`.

**`GET /invoice?lang=cs|en`** → `templates/guest/invoice_request.html` (extends `guest/base.html`). Fields:
- `email` (type email, required);
- `arrival` (type date, required);
- `booking_code` (optional, max 20, "e.g. HMABC12345" — **only used to narrow matches, never required, never echoed**);
- Turnstile `data-action="invoice_request"`;
- `_csrf`.

**`POST /invoice`** → `invoice_public.request_link`:
1. `if rate_limit.blocked("invoice_request", rate_limit.client_key(request), 5, 3600)`: render the form with `t('invoice_req_too_many')` (429). This reveals nothing about data. Always call `rate_limit.record("invoice_request", key)` on POST.
2. `if not turnstile.verify(request, form.get("cf-turnstile-response"), "invoice_request")`: re-render with the existing guest key `t('security_check_failed')` (as `verify_pin` does). Pass `turnstile_site_key` / `require_turnstile=turnstile.required()` to the template, like `claim.html`.
3. Normalise `email = mail.normalise_email(form["email"])` and `arrival = validation.parse_iso_date(form["arrival"])`. If invalid, re-render with field errors. Field-format errors reveal nothing.
4. `email_key = sha256(email)`. Check `rate_limit.blocked("invoice_request_email", email_key, 3, 86400)` (then record). If blocked, **still show the generic success page** and do nothing. The count is invisible to an attacker.
5. Look up matches:
   ```sql
   SELECT r.* FROM reservation r
   JOIN apartment a ON a.id = r.apartment_id
   LEFT JOIN reservation_claim c ON c.reservation_id = r.id
   WHERE r.date_from = :arrival AND r.status = 'active' AND r.archived_at IS NULL
     AND r.date_to <= :today AND r.date_to >= :today_minus_365
     AND a.invoice_requests_policy = 'on' AND a.archived_at IS NULL
     AND (lower(r.guest_email) = :email OR lower(c.email) = :email)
   ```
   If `booking_code` is given, keep only rows whose `reservation_url` contains it (case-insensitive).
6. For each match (usually 0 or 1):
   ```text
   mail.enqueue(kind="invoice_request_link",
     idempotency_key=f"invoice_request_link:{rid}:{email_key[:16]}:{today}", …)
   ```
   The link is `/invoice/r/{token}`. At most one mail per stay per e-mail per day, even across attackers' retries.
7. **Always** render `templates/guest/invoice_request_sent.html` with `t('invoice_req_sent_body')`. Status 200 either way. No timing branch: the mail is only enqueued (the outbox worker sends later), so there is no SMTP call in the request.
8. If `mail.mail_enabled()` is False, the GET page shows `t('invoice_req_no_mail')` ("Ask your host directly") and the POST is disabled.

**What is never revealed:** whether a stay exists; whether the e-mail matches; which apartment; the host's name. The success page is identical for all cases.

### 3.3 Tokens

`App/app/invoice_links.py`:

```text
_REQ = URLSafeTimedSerializer(config.SECRET_KEY, salt="ubyhost-invoice-request")
_DL  = URLSafeTimedSerializer(config.SECRET_KEY, salt="ubyhost-invoice-download")
REQUEST_MAX_AGE = 7 * 86400          # guest-requested (path C/D)
HOST_LINK_MAX_AGE = 30 * 86400       # host-issued (path B)
DOWNLOAD_MAX_AGE = 30 * 86400

def request_token(reservation_id: int, email: str | None, purpose: str) -> str
    # payload {"r": rid, "e": sha256(email)[:16] or "", "p": "guest"|"host", "v": 1}
def read_request_token(token: str) -> dict | None      # checks max_age by purpose
def download_token(invoice_id: int, pdf_sha256: str) -> str   # {"i": id, "h": sha[:16]}
def read_download_token(token: str) -> int | None       # also re-checks the sha prefix vs the DB
```

A token is useless once the stay is no longer eligible (archived, deleted, or invoice requests switched off).

### 3.4 Guest request form `/invoice/r/{token}` (one page; one URL for the whole journey)

**`GET`** → `templates/guest/invoice_form.html` (extends `guest/base.html`; include `guest/_host.html` at the bottom like other guest pages). The page has **three states** on the same URL:

| State | Condition | Shows |
|---|---|---|
| form | no request yet, or the request is `open` and `?edit=1` | the form below |
| waiting | request `open` | a card "Your host has your request" + the buyer summary + *Edit details* (`?edit=1`) |
| ready | request `issued` | a card "Invoice %(number)s is ready" + **Download PDF** (primary `g-btn`, `/invoice/d/{download_token}`) |
| declined | request `declined` | the host's reason + the host contact (`_host.html`) |

**Form, top to bottom** (field order matters for autofill and thumbs):
1. **Stay summary card** (existing `g-card g-stay-summary` style): property public name (`_display_name`), dates, nights. No names of other people.
2. **Billing details card**:
   - `buyer_name` — `autocomplete="name"`, or `organization` when "for a company" is ticked (swap the attribute in JS);
   - `buyer_street` — `autocomplete="street-address"`;
   - `buyer_city` — `autocomplete="address-level2"`;
   - `buyer_zip` — `autocomplete="postal-code"`, `inputmode="text"`;
   - `buyer_country` — a select from `validation.country_codes()`, default = the lead guest's residence country if known, else `CZE`, `autocomplete="country"`;
   - checkbox **"For a company"** (`for_company`) reveals `buyer_ico` (`inputmode="numeric"`, `maxlength="8"`) with a *Fill in from ARES* `g-btn secondary slim` button (only when the country is CZE), and `buyer_dic`. Hidden fields are cleared server-side when the checkbox is off.
3. **Payment card (optional)**: `amount_paid_hint` (`inputmode="numeric"`), `paid_via` select (Airbnb / Booking.com / Bank transfer / Cash / Other).
4. **Delivery card**: radio `download` (default) / `email`. When `email` is chosen, show `delivery_email` (prefilled with the e-mail on file when the token carries one; `autocomplete="email"`).
5. `note` (≤ 300, optional, collapsed in a `<details>`).
6. Submit **Send to host** (`g-btn`).

JS (inline in the template, ≤ 30 lines, vanilla):
- toggle the company fields;
- toggle the delivery e-mail;
- the ARES button calls `fetch("/invoice/r/{token}/ares?ico=" + value)`, fills the fields on success, and shows `t('invoice_ares_failed')` on failure.

No other JS. The form must also work with JS off: all fields are visible, and the server ignores company fields unless `for_company` is set.

**`POST`** →
- validate (§4.2) → upsert **one open request per reservation + purpose-email hash** (unique partial index, §5);
- create the host alert `invoice_requested`;
- if `legal_entity.contact_email` is set, enqueue `invoice_request_host`, key `invoice_request_host:{request_id}`;
- redirect to the same URL (the waiting state).

On validation errors, re-render with the existing guest error pattern (`bad()`, `err_for()` helpers as in `form.html`), status 422.

Rate limit: `invoice_form` 20/h per client.

### 3.5 Host UI placement (sidebar IA unchanged apart from one item)

- **Sidebar**, `nav.records` group, after House book (and after Stay fee if present):

  ```html
  <a href="/invoices" class="{{ 'active' if nav == 'invoices' }}">{{ nav_icon('invoice') }}{{ t('nav.invoices') }}</a>
  ```

  The badge shows the count of open requests (`invoice_open_requests`, computed in `templating.render` per request, owner-scoped). New icon in `_components.html::nav_icon`, in the same 20×20 stroke style:

  ```html
  {% elif name == 'invoice' %}
    <svg class="nav-icon" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M5 2.5h10v15l-2.5-1.5-2.5 1.5-2.5-1.5L5 17.5v-15Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M7.5 7h5M7.5 10h5M7.5 13h3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
  ```
- **Stay detail** (`templates/reservation_detail.html`): `<section class="panel" id="invoice">` placed directly after the stay-fee panel `#stay-fee`, both inside the `#money` group — the slot UX_AUDIT C-16 [UX-81] reserved between the guest cards and `{% if submissions %}`, with `<h2>` copy "Payments" / "Platby". It shows:
  - open requests (buyer name, submitted at, *Vystavit*, *Odmítnout*);
  - issued documents (number, date, total, state, *PDF*, *Storno/ODD*);
  - *Vystavit fakturu*;
  - *Odkaz pro hosta* (copy field + *Poslat e-mailem*).
- **Apartment form**: toggle `invoice_requests_policy` (`off` default / `on`), in the `#communication` panel directly after the stay-fee settings block (after the `stay_fee_cash` checkbox), as a `<select>` copied from the `stay_fee_policy` select. Copy in §10.
- **Entities form**: `vat_status`, `registry_entry`, `invoice_prefix`, `invoice_next_number`, `invoice_due_days`, plus the bank fields shared with the stay-fee plan. Also *Načíst z ARES* for the seller.
- **Command palette**: `{"label": t("nav.invoices"), "url": "/invoices", "keywords": "faktura invoice doklad"}`.

---

## 4. Required fields → existing and missing data

### 4.1 Seller (from `legal_entity` via `apartment.legal_entity_id`; snapshot at issue)

| Printed field | Source today | Change |
|---|---|---|
| Name (firma/jméno) | `legal_entity.name` | — |
| Sídlo | `legal_entity.seat` (free text) | — (the issue gate requires it non-empty) |
| IČO | `legal_entity.ico` | Validate 8 digits + mod-11 when saving the entity (§4.2 algorithm) |
| DIČ | `legal_entity.dic` | Printed only when `vat_status == 'payer'` |
| Registry entry (OZ §435) | — | **new** `legal_entity.registry_entry TEXT`. The prefill is chosen in the entity form: *Živnostník* → "Fyzická osoba zapsaná v živnostenském rejstříku", or *Obchodní rejstřík*. ARES `dalsiUdaje[].spisovaZnacka` (e.g. `C 250448/MSPH`) → "Zapsáno v obchodním rejstříku vedeném Městským soudem v Praze, oddíl C, vložka 250448". Court-code map: `MSPH`→"Městským soudem v Praze", `KSBR`→"Krajským soudem v Brně", `KSOS`→"Krajským soudem v Ostravě", `KSPL`→"Krajským soudem v Plzni", `KSUL`→"Krajským soudem v Ústí nad Labem", `KSHK`→"Krajským soudem v Hradci Králové", `KSCB`→"Krajským soudem v Českých Budějovicích"; any other code → raw text. ⚠ FLAG-1 |
| VAT status | — | **new** `legal_entity.vat_status TEXT NOT NULL DEFAULT 'non_payer'` |
| Bank account / IBAN / BIC | `legal_entity.bank_account`, `iban`, `bic` (added by the stay-fee plan, §8) | — |
| Contact (e-mail, phone) | `contact_email`, `contact_phone` | printed in the footer |
| Numbering settings | — | **new** `invoice_prefix TEXT` (≤ 6, `[A-Z0-9]`), `invoice_next_number INTEGER`, `invoice_next_number_year INTEGER`, `invoice_due_days INTEGER NOT NULL DEFAULT 14` |

**Seller ARES lookup** (entities form button): `GET /entities/ares?ico=` returns JSON `{name, seat, dic, registry_entry}`. This fills the form client-side; the host saves.

### 4.2 Buyer (entered fresh by the guest or host; never taken from guest registration data)

The registration data is collected under the Police / stay-fee legal basis. Reusing it for invoicing would be a purpose change, so the buyer is always typed.

| Field | Column (`invoice_request` and `invoice.buyer_*`) | Rules |
|---|---|---|
| Name / company | `buyer_name` | required, ≤ 120 |
| Street + number | `buyer_street` | required, ≤ 120 |
| City | `buyer_city` | required, ≤ 60 |
| ZIP | `buyer_zip` | ≤ 12 |
| Country | `buyer_country` | ISO-3 from `validation.country_codes()`, default `CZE` |
| IČO | `buyer_ico` | optional; if `buyer_country == 'CZE'`: 8 digits, checksum weights 8,7,6,5,4,3,2 → `r = sum % 11`, check digit = `1 if r == 0 else 0 if r == 1 else 11 - r` |
| DIČ / VAT ID | `buyer_dic` | optional, `^[A-Z]{2}[0-9A-Z]{2,12}$` after removing spaces |
| E-mail | `buyer_email` | optional (required if `delivery == 'email'`) |

**Printable-character rule.** Every buyer field must consist only of characters U+0020–U+017F (Latin-1 + Latin Extended-A). That is what `housebook.FONT_REGULAR` (Bitstream Vera) renders. Otherwise show the error `t('invoice_err_latin')`.

**Buyer ARES lookup (guest).** `GET /invoice/r/{token}/ares?ico=`. It needs a valid request token and is rate-limited: `invoice_ares` 20/h per client plus 40/day per token. Server side, `App/app/ares.py::lookup(ico) -> dict | None`:
- `requests.get(f"https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/{ico}", timeout=3, headers={"Accept": "application/json"})`.
- Only after the IČO passes the checksum.
- Returns `{name: obchodniJmeno, street: f"{sidlo.nazevUlice or sidlo.nazevCastiObce} {cisloDomovni}{'/'+cisloOrientacni if any}", city: sidlo.nazevObce + (" " + nazevMestskehoObvodu if it differs), zip: str(sidlo.psc), country: 'CZE', dic: dic or ''}`.
- On any error or 404 it returns `None`, and the UI shows `t('invoice_ares_failed')`.
- No caching of personal data (companies only).
- **Egress:** confirm that production allows `ares.gov.cz:443` (see `docs/SECURITY.md` / `feed_fetch.py` pinning). If egress is restricted, the feature degrades to manual entry.

### 4.3 Numbering — per legal entity

**Why per entity, not per account or per apartment.** The invoice is issued by the *supplier*, i.e. the tax subject identified by IČO. That is `legal_entity`.
- Per account: two entities under one UbyHost login would share one series, so one supplier's numbers would have gaps filled by another supplier's documents. That is wrong for both.
- Per apartment: one supplier would run parallel series, which is legal but confuses accountants and gains nothing.

Format and state:
- Format: `{invoice_prefix}{YYYY}-{NNNN}`. NNNN is zero-padded to 4 and widens automatically past 9999. YYYY is the **issue** year, restarting yearly.
- VS = the digits of the number without the prefix: `YYYY` + `NNNN` (8 digits; ≤ 10 always).
- Sequence state: `invoice_sequence(legal_entity_id, year, last_no)`.
- One-time continuation: if the host already issued e.g. `2026-0007` elsewhere, they set `invoice_next_number=8` for `invoice_next_number_year=2026`. `allocate_number` uses `max(last_no, next_number − 1) + 1` and clears both fields in the same transaction. The UI refuses a value ≤ `last_no`.

### 4.4 Dates

| Field | Default | Editable by host at issue? |
|---|---|---|
| `issue_date` | today in Prague (`claim.prague_today()`) | no (issuing *is* the act) |
| `duzp` (payer only) | `reservation.date_to` (checkout). ⚠ FLAG-3: payment received earlier (e.g. an Airbnb payout) may move the tax point to the payment date (§29(1)(h) "den přijetí úplaty…"). | yes (date ≤ issue_date) |
| `due_date` | unpaid: `issue_date + legal_entity.invoice_due_days`; paid: none | yes |
| `paid_on` | if the host ticks *Already paid*: `date_to` | yes |
| Stay period (printed in the item text) | `reservation.date_from` – `date_to` | no |

**15-day warning (payer):** if `issue_date − duzp > 15 days`, show a warning (non-blocking) `t('invoice.warn_15_days')`. DPH §28(8).

### 4.5 Line items (minimal editing)

| # | Line | Quantity / unit | Price input | VAT (payer) | Shown when |
|---|---|---|---|---|---|
| 1 | `t('invoice.item.accommodation', name=apartment_public_name, from=…, to=…, nights=n, persons=p)` — e.g. "Ubytování – Byt Žižkov, 10. 9. 2026 – 14. 9. 2026, 4 noci, 2 os." | 1 × "pobyt" | **gross** CZK, entered by the host (prefilled from `amount_paid_hint` if the guest gave one). UbyHost has no price data. | 12 % (⚠ FLAG-4) | always |
| 2 | `t('invoice.item.stay_fee')` — "Poplatek z pobytu" | 1 | `stay_fee.stay_summary(reservation, apartment)["total_czk"]` (the host can edit the number in the form) | **outside the VAT base**: printed "mimo předmět DPH", excluded from the recap | the checkbox `include_stay_fee` is **on by default when the stay's fee is marked paid** (`reservation.stay_fee_paid_at`) and the total is > 0, off otherwise |
| 3 | optional *Jiná položka* (free text ≤ 80) | 1 | gross CZK | select 21 % / 12 % | host adds it (max 1 extra line in v1) |

`persons` = `reservation_progress(reservation)["expected"]` or the signed count. `nights` = `(date_to − date_from).days`.

**VAT arithmetic (payer), per line.** Use `Decimal`, `ROUND_HALF_UP`, in haléře:
- `tax = (gross × rate / (100 + rate)).quantize(0.01)`
- `base = gross − tax`
- unit price without tax = `base` (quantity 1)

The recap groups by rate: base, tax, gross. The total to pay is the sum of gross for all lines, including the stay fee. There is no rounding to whole crowns (payment is by transfer). ⚠ FLAG-5 (computing the tax from gross, per DPH §37 — not fetched in this research).

**Non-payer / identified:** amounts only. No rate, base or tax column. Footer "Nejsem plátce DPH." / "Not a VAT payer." (voluntary but helpful).

### 4.6 Payment block and QR (reuses `payments.py`)

- **Paid:** print `t('invoice.paid_note', date=paid_on, method=paid_via_label)`, e.g. "Uhrazeno 14. 9. 2026 prostřednictvím Airbnb — neplaťte." No QR, no due date.
- **Unpaid:** print the bank account (domestic format + IBAN), VS, due date and amount. QR = `payments.qr_png_bytes(payments.spayd(entity_iban, Decimal(total_haler) / 100, vs, f"FAKTURA {number}", bic))`, drawn with `pdf.drawImage(ImageReader(io.BytesIO(png)), x, y, 32*mm, 32*mm)` (`from reportlab.lib.utils import ImageReader`). Label "QR Platba" underneath. The quiet zone is already in the PNG.
- Do not use `AM` with haléře beyond 2 decimals.
- Show no QR if there is no IBAN (a warning at issue: `t('invoice.warn_no_iban')`).

---

## 5. Data model

Add all columns to `SCHEMA` and `db.ADDED_COLUMNS` (the `passport_photo_policy` pattern). Add the tables, indexes and triggers to `SCHEMA`.

```text
("legal_entity", "vat_status",               "TEXT NOT NULL DEFAULT 'non_payer'"),
("legal_entity", "registry_entry",           "TEXT"),
("legal_entity", "invoice_prefix",           "TEXT"),
("legal_entity", "invoice_next_number",      "INTEGER"),
("legal_entity", "invoice_next_number_year", "INTEGER"),
("legal_entity", "invoice_due_days",         "INTEGER NOT NULL DEFAULT 14"),
# bank_account / iban / bic come from the stay-fee plan; do NOT add them twice
("apartment",    "invoice_requests_policy",  "TEXT NOT NULL DEFAULT 'off'"),
```

```sql
CREATE TABLE IF NOT EXISTS invoice_sequence (
    legal_entity_id INTEGER NOT NULL REFERENCES legal_entity(id),
    year            INTEGER NOT NULL,
    last_no         INTEGER NOT NULL,
    PRIMARY KEY (legal_entity_id, year)
);

CREATE TABLE IF NOT EXISTS invoice_request (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    reservation_id   INTEGER NOT NULL REFERENCES reservation(id) ON DELETE CASCADE,
    apartment_id     INTEGER NOT NULL REFERENCES apartment(id),
    source           TEXT NOT NULL CHECK (source IN ('guest_public','guest_stay','host_link')),
    email_hash       TEXT NOT NULL DEFAULT '',          -- token "e"
    buyer_name TEXT, buyer_street TEXT, buyer_city TEXT, buyer_zip TEXT,
    buyer_country TEXT, buyer_ico TEXT, buyer_dic TEXT, buyer_email TEXT,
    amount_paid_hint INTEGER,
    paid_via         TEXT CHECK (paid_via IN ('airbnb','booking','direct_transfer','cash','other')),
    delivery         TEXT NOT NULL DEFAULT 'download' CHECK (delivery IN ('download','email')),
    delivery_email   TEXT,
    note             TEXT,
    lang             TEXT NOT NULL DEFAULT 'cs',
    state            TEXT NOT NULL DEFAULT 'open' CHECK (state IN ('open','issued','declined')),
    decline_reason   TEXT,
    invoice_id       INTEGER REFERENCES invoice(id),
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    handled_at       TEXT,
    handled_by       INTEGER REFERENCES user_account(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_invoice_request_open
    ON invoice_request (reservation_id, email_hash) WHERE state = 'open';

CREATE TABLE IF NOT EXISTS invoice (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    legal_entity_id      INTEGER NOT NULL REFERENCES legal_entity(id),   -- RESTRICT (default)
    apartment_id         INTEGER REFERENCES apartment(id),
    reservation_id       INTEGER REFERENCES reservation(id) ON DELETE SET NULL,
    request_id           INTEGER REFERENCES invoice_request(id) ON DELETE SET NULL,
    kind                 TEXT NOT NULL CHECK (kind IN ('invoice','storno','corrective')),
    corrects_invoice_id  INTEGER REFERENCES invoice(id),
    correction_reason    TEXT,
    correction_date      TEXT,                           -- §45(1)(k) / §42(3), payer only
    seq_year             INTEGER NOT NULL,
    seq_no               INTEGER NOT NULL,
    number               TEXT NOT NULL,
    vs                   TEXT NOT NULL,
    lang                 TEXT NOT NULL CHECK (lang IN ('cs','en')),
    currency             TEXT NOT NULL DEFAULT 'CZK' CHECK (currency = 'CZK'),
    vat_status           TEXT NOT NULL,                  -- snapshot of the entity at issue
    issue_date           TEXT NOT NULL,
    duzp                 TEXT,
    due_date             TEXT,
    paid_on              TEXT,
    paid_via             TEXT,
    seller_name TEXT NOT NULL, seller_seat TEXT NOT NULL, seller_ico TEXT, seller_dic TEXT,
    seller_registry TEXT, seller_bank_account TEXT, seller_iban TEXT, seller_bic TEXT,
    seller_email TEXT, seller_phone TEXT,
    buyer_name TEXT NOT NULL, buyer_street TEXT, buyer_city TEXT, buyer_zip TEXT,
    buyer_country TEXT, buyer_ico TEXT, buyer_dic TEXT, buyer_email TEXT,
    stay_from            TEXT, stay_to TEXT, stay_label TEXT,
    total_base_haler     INTEGER,                        -- payer only
    total_vat_haler      INTEGER,                        -- payer only
    total_haler          INTEGER NOT NULL,               -- amount payable (negative for storno/ODD)
    pdf_blob             BLOB,
    pdf_sha256           TEXT,
    issued_at            TEXT,
    issued_by            INTEGER REFERENCES user_account(id),
    -- mutable bookkeeping (not guarded):
    marked_paid_at       TEXT,
    emailed_at           TEXT,
    owner_user_id        INTEGER REFERENCES user_account(id),
    created_at           TEXT NOT NULL,
    UNIQUE (legal_entity_id, number),
    UNIQUE (legal_entity_id, seq_year, seq_no)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_invoice_one_correction
    ON invoice (corrects_invoice_id) WHERE corrects_invoice_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_invoice_reservation ON invoice (reservation_id);
CREATE INDEX IF NOT EXISTS idx_invoice_owner ON invoice (owner_user_id, issue_date);

CREATE TABLE IF NOT EXISTS invoice_item (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id   INTEGER NOT NULL REFERENCES invoice(id),
    position     INTEGER NOT NULL,
    kind         TEXT NOT NULL CHECK (kind IN ('accommodation','stay_fee','other')),
    description  TEXT NOT NULL,
    quantity     INTEGER NOT NULL DEFAULT 1,
    unit         TEXT NOT NULL DEFAULT '',
    vat_rate     INTEGER,                    -- 12 | 21 | NULL (non-payer, or outside VAT: stay_fee)
    base_haler   INTEGER,
    vat_haler    INTEGER,
    gross_haler  INTEGER NOT NULL,
    UNIQUE (invoice_id, position)
);

-- Immutability (content columns only; bookkeeping columns stay writable)
CREATE TRIGGER IF NOT EXISTS invoice_issued_guard
BEFORE UPDATE OF legal_entity_id, apartment_id, kind, corrects_invoice_id, correction_reason,
    correction_date, seq_year, seq_no, number, vs, lang, currency, vat_status, issue_date, duzp,
    due_date, paid_on, paid_via, seller_name, seller_seat, seller_ico, seller_dic, seller_registry,
    seller_bank_account, seller_iban, seller_bic, seller_email, seller_phone, buyer_name,
    buyer_street, buyer_city, buyer_zip, buyer_country, buyer_ico, buyer_dic, buyer_email,
    stay_from, stay_to, stay_label, total_base_haler, total_vat_haler, total_haler,
    pdf_blob, pdf_sha256, issued_at, issued_by
ON invoice
WHEN OLD.issued_at IS NOT NULL
BEGIN
    SELECT RAISE(ABORT, 'invoice is issued and immutable');
END;

CREATE TRIGGER IF NOT EXISTS invoice_delete_guard
BEFORE DELETE ON invoice
WHEN OLD.issued_at IS NOT NULL
 AND COALESCE((SELECT value FROM settings WHERE key = 'invoice_purge_unlock'), '') <> '1'
BEGIN
    SELECT RAISE(ABORT, 'invoice is issued and immutable');
END;

CREATE TRIGGER IF NOT EXISTS invoice_item_insert_guard
BEFORE INSERT ON invoice_item
WHEN (SELECT issued_at FROM invoice WHERE id = NEW.invoice_id) IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'invoice is issued and immutable'); END;

CREATE TRIGGER IF NOT EXISTS invoice_item_update_guard
BEFORE UPDATE ON invoice_item
WHEN (SELECT issued_at FROM invoice WHERE id = OLD.invoice_id) IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'invoice is issued and immutable'); END;

CREATE TRIGGER IF NOT EXISTS invoice_item_delete_guard
BEFORE DELETE ON invoice_item
WHEN (SELECT issued_at FROM invoice WHERE id = OLD.invoice_id) IS NOT NULL
 AND COALESCE((SELECT value FROM settings WHERE key = 'invoice_purge_unlock'), '') <> '1'
BEGIN SELECT RAISE(ABORT, 'invoice is issued and immutable'); END;
```

**Existing code that must respect these tables:**
- `routes/admin.py::delete_entity`: add a check before deleting: `SELECT COUNT(*) FROM invoice WHERE legal_entity_id = ?`. If > 0, `err=_flash(request, "flash.error.entity_has_invoices")` — a translated key, never an English literal (UX-34, `tests/test_flash_literals.py`). The FK default (NO ACTION) would also block it; the check gives a readable message. Add the EN + CS wording to `host_i18n.py` in the same commit.
- `update_entity` edits never touch issued invoices (snapshots). Say so in the entity form hint `entities.invoice.snapshot_hint`.
- Reservation deletion/archive: `reservation_id ON DELETE SET NULL` keeps the invoice. `stay_label` / `stay_from` / `stay_to` keep it readable.

---

## 6. Numbering safety, immutability, corrections, retention

### 6.1 Issuing under concurrency (normative)

New module `App/app/invoices.py`:

```text
def build_draft(reservation, entity, form, lang) -> Draft          # pure: validated snapshot + items + totals
def validate_for_issue(draft) -> list[Issue]                       # §2 gate per vat_status
def issue(draft, actor_user_id) -> int                             # returns invoice.id
def allocate_number(cur, entity_row, issue_year) -> tuple[int, int, str, str]   # (year, seq, number, vs)
def cancel(invoice_id, reason, correction_date, actor_user_id) -> int           # storno or ODD
def download_pdf(invoice_id) -> bytes                              # always the stored bytes
```

`issue()`:

```text
issues = validate_for_issue(draft); if errors -> raise
with db.immediate() as cur:                      # BEGIN IMMEDIATE: takes the write lock before reading the sequence
    entity = cur.execute("SELECT * FROM legal_entity WHERE id=?", …).fetchone()   # re-read inside the lock
    year, seq, number, vs = allocate_number(cur, entity, draft.issue_date.year)
    inv_id = INSERT invoice (… issued_at NULL, pdf_blob NULL …)
    INSERT invoice_item rows
    pdf = invoice_pdf.render(invoice_row_from(cur, inv_id), items, lang)          # reportlab, in-process, ~50 ms
    UPDATE invoice SET pdf_blob=?, pdf_sha256=?, issued_at=?, issued_by=? WHERE id=?   # NULL -> value is allowed by the trigger
    if draft.request_id: UPDATE invoice_request SET state='issued', invoice_id=?, handled_at=?, handled_by=?
db.audit("invoice_issued", f"id={inv_id} number={number} entity={entity.id} total={total_haler}")
```

`allocate_number(cur, entity, year)`:

```text
row = cur.execute("SELECT last_no FROM invoice_sequence WHERE legal_entity_id=? AND year=?", …).fetchone()
last = row["last_no"] if row else 0
if entity["invoice_next_number"] and entity["invoice_next_number_year"] == year:
    last = max(last, entity["invoice_next_number"] - 1)
    cur.execute("UPDATE legal_entity SET invoice_next_number=NULL, invoice_next_number_year=NULL WHERE id=?", …)
seq = last + 1
cur.execute("INSERT INTO invoice_sequence(legal_entity_id, year, last_no) VALUES (?,?,?) "
            "ON CONFLICT(legal_entity_id, year) DO UPDATE SET last_no = excluded.last_no", …)
width = max(4, len(str(seq)))
number = f"{entity['invoice_prefix'] or ''}{year}-{seq:0{width}d}"
vs = f"{year}{seq:0{width}d}"           # 8–10 digits; seq ≥ 1 000 000 is out of scope
```

Guarantees:
- **No duplicates.** `BEGIN IMMEDIATE` serialises writers (SQLite WAL allows one writer), and `UNIQUE (legal_entity_id, seq_year, seq_no)` / `UNIQUE (legal_entity_id, number)` are the backstop.
- **No gaps.** The number, the rows and the PDF commit together. Any exception rolls back all of them, and the number is never consumed.
- **Same PDF forever.** Downloads always serve `pdf_blob`, and `pdf_sha256` is re-checked on download (mismatch → 500 + `alerts.raise_alert("critical", "invoice_pdf_mismatch", f"Invoice {number}: stored PDF hash mismatch", dedupe_key=f"invoice_pdf_mismatch:{id}")`). Template changes later never change an issued document.
- `db.immediate()` is identical to `db.cursor()` except that it runs `cur.execute("BEGIN IMMEDIATE")`. `connect()` already sets `timeout=30`, so a second writer waits rather than failing.

**Preview (no number).** `POST /reservations/{rid}/invoice/preview` renders `invoice_pdf.render(..., preview=True)` from the unsaved form. It returns inline `application/pdf` with a diagonal watermark "NÁHLED – NEPLATNÝ DOKLAD / PREVIEW – NOT VALID" and number "—". It writes nothing and consumes nothing.

### 6.2 Immutability rules (summary for reviewers)

| What | Can change after issue? |
|---|---|
| Any printed field, the items, the totals, the PDF, the number | **Never** (triggers) |
| `marked_paid_at` (host marks an unpaid invoice as paid later) | yes; bookkeeping only. The PDF keeps showing the due date, as issued. |
| `emailed_at` | yes |
| `reservation_id`, `request_id` → NULL through FK actions | yes |
| Delete | only in the retention purge, with the unlock flag inside `db.immediate()` |

### 6.3 Corrections

`cancel(invoice_id, reason, correction_date, actor)` is available only for `kind='invoice'` rows with no existing correction (unique index):

| Entity `vat_status` **at the original's issue** (use the snapshot `invoice.vat_status`) | New document | Content |
|---|---|---|
| `non_payer`, `identified` | `kind='storno'`, the same series and the next number | Title "Storno faktury č. {orig}" / "Cancellation of invoice No. {orig}". Same seller/buyer snapshot, items copied with **negative** amounts. A "Důvod: {reason}" line. `paid_on` = today if the original was paid (refund situation) else NULL, and no QR. |
| `payer` | `kind='corrective'` (ODD) | Title "Opravný daňový doklad č. {new}". "k daňovému dokladu č. {orig}" (§45(1)(e)(f)). "Důvod opravy: {reason}" (g). Differences in base, VAT and total, all negative (h)(i)(j). "Den uskutečnění opravy (§ 42 odst. 3): {correction_date}" (k), defaulting to today. Seller and buyer DIČ (b)(d). |

- `reason` is required, 5–200 characters.
- After a correction, the UI offers **"Vystavit novou fakturu (předvyplnit)"**. It opens the issue form prefilled from the original's snapshot, and the new invoice gets a new number.
- Partial corrections (e.g. partial refunds) are not in v1: cancel and reissue.
- Audit `invoice_corrected`, detail `orig=… new=… kind=… reason=…`.
- ⚠ FLAG-6: a payer who became a payer after issuing a non-payer invoice. The rule above follows the snapshot, i.e. it issues a storno, which matches Fakturoid's advice to switch mode temporarily.

### 6.4 Retention

- Keep every `invoice` and `invoice_item` for **10 years from the end of the calendar year of `issue_date`** (DPH §35(2) for payers; conservative for everyone else). ⚠ FLAG-8.
- `invoices.purge_expired(today)`: set `invoice_purge_unlock='1'`, delete items then invoices where `issue_date < date(today.year − 10, 1, 1)`, reset the flag, and audit `invoice_retention_purge`. Wire it into `/settings/purge-expired` after the house-book purge. The first real deletions are in 2037.
- `invoice_request` rows in state `declined`: delete 1 year after `handled_at`. Rows in state `open` for more than 90 days: auto-decline with reason `expired` (scheduler, §9).
- Host retention is independent of guest-row retention. The invoice holds its own buyer snapshot, typed by the buyer.

---

## 7. PDF design (`App/app/invoice_pdf.py`) — branded, finished, tested

**The design is done.** Copy `docs/plans/invoice-design/invoice_pdf_reference.py` to `App/app/invoice_pdf.py`, then make the three edits listed in its docstring. The DejaVu fonts are **already committed** at `App/app/static/fonts/` (with `LICENSE-DejaVu.txt`); do not download fonts. Compare your output with the four sample PDFs in `docs/plans/invoice-design/`:

| Sample | Shows |
|---|---|
| `sample-neplatce-cs.pdf` | non-payer, Czech, paid via Airbnb, stay-fee line |
| `sample-platce-en.pdf` | VAT payer, English with the Czech document type, unpaid, VAT recap, QR Platba |
| `sample-storno-cs.pdf` | cancellation, negative lines, reason, "k dokladu č." |
| `sample-preview-cs.pdf` | preview watermark, no number |

Do not restyle. If something must change, change it in the reference file first, re-render, and compare.

### 7.1 Brand rules (why it looks like this)

- **The host is the hero.** The top-left shows the supplier's name at 15 pt, with the small label DODAVATEL / SUPPLIER. The UbyHost logo is **never** at the top: that would make UbyHost look like the issuer, which is misleading and a legal problem (OZ §435, §29 DPH "označení osoby, která uskutečňuje plnění").
- **UbyHost appears three ways only:**
  1. a 1.6 mm coral (`#D35445`, the mark colour from `docs/LOGO.md`) rule across the top edge;
  2. the coral document-type label above the number (FAKTURA / TAX INVOICE / STORNO FAKTURY);
  3. the **footer credit**: the mark only (`ubyhost-mark.png`, 3.6 mm, mark-only version as LOGO.md prescribes below ~40 px), then "Vystaveno v UbyHost – registrace hostů a faktury pro ubytovatele · ubyhost.com" (EN: "Issued with UbyHost – guest registration and invoicing for hosts · ubyhost.com"). It is 7 pt, `--ink-faint` grey, and the whole line is a clickable link to `https://ubyhost.com/?utm_source=invoice&utm_medium=pdf`.

  The credit is always present in v1. It is free distribution: every business customer who receives an invoice sees where it came from.
- Colours come from `tokens.css`: ink `#1B1F25`, secondary `#50504C`, muted `#73736E`, border `#DEDED9`, canvas cards `#F7F7F5`. The only other colour is the green "UHRAZENO" pill (`--green` on `--green-bg`). No gradients, no shadows, light only.
- **Font: DejaVu Sans, vendored.** ⚠ The Bitstream Vera font that `housebook.py` uses has **no glyphs for ě, ř, ů, ň, ť** (verified: "Odběratel" renders as "Odb□ratel"). So Vera must not be used here. See §7.3 for the existing house-book bug this uncovered.

### 7.2 Layout (A4 portrait, 18 mm margins, top to bottom)

1. The coral top rule.
2. **Header:** left — DODAVATEL label, the seller name, the sídlo, and "IČO … · DIČ …" (DIČ only for payers). Right — the coral document type (plus the Czech type in grey above it on `en` documents), the number at 20 pt, and "k dokladu č. …" for storno/ODD.
3. **Two cards:** left (56 % width, canvas fill) — ODBĚRATEL with the buyer name, address, country (omitted for CZ), IČO/DIČ. Right (outlined) — label/value rows: date of issue, DUZP (payer), due date (unpaid), VS, payment method.
4. **Stay line:** "POBYT Byt Žižkov · 10. 9. 2026 – 14. 9. 2026 · 4 noci · 2 os."
5. **Items table:** an ink rule on top, hairlines between rows, descriptions wrapped to 2 lines. Non-payer columns: Popis · Množství · Cena. Payer columns: Popis · Bez DPH · Sazba · DPH · Celkem. The stay fee shows "mimo DPH".
6. **VAT recap** (left, payer) and the **total box** (right, canvas): label, 17 pt amount, and the green "UHRAZENO {date}" pill when paid (invoices only; never on storno).
7. **Payment details + QR** (unpaid only): account, IBAN (grouped), BIC, VS, amount, and the 30 mm QR Platba with its caption.
8. **Notes:** the storno/ODD reason and the correction date; "Nejsem plátce DPH." for non-payers.
9. **Footer:** the registry sentence and host contact (7 pt), a hairline, then the UbyHost credit (left) and the page number (right).

Money is always in the Czech format, `8 400,00 Kč`, with no-break spaces. Dates are `24. 9. 2026`.

### 7.3 Found while designing: the existing house-book PDFs lose Czech letters

`housebook._register_fonts()` registers Vera and claims it "covers Latin Extended-A". It does not. The registration-form PDF (`registration_form_pdf`, title "Přihlašovací tiskopis cizince") and every guest name or address containing ě/ř/ů/ň/ť render with missing glyphs.

Fix it in a **separate commit before invoice step 4**:
- point `_register_fonts` at the committed `App/app/static/fonts/DejaVuSans.ttf` / `DejaVuSans-Bold.ttf`, keeping the Helvetica fallback;
- add a test that renders "Přihlašovací ěřůňť" and asserts that `pdfmetrics.getFont(FONT_REGULAR).face.charToGlyph` contains every character.

`ubyport_sample_pdf.py` already uses DejaVu from system paths. It can switch to the vendored copy too, so rendering is identical on macOS dev machines and Linux production.

## 8. Routes and handlers

### 8.1 Host (`App/app/routes/invoices.py`, `router = APIRouter(dependencies=[Depends(security.protect_host_post)])`, included in `main.py` after `admin.router`)

Every handler starts with `guard = auth.require_login(request)` and scopes by owner through `access.*` (entity via `access.entity`, reservation via the apartment owner).

| Method + path | Handler | Behaviour |
|---|---|---|
| `GET /invoices?year=&entity=&state=` | `invoices_list` | `templates/invoices.html`, `nav="invoices"`. Tab 1 "Žádosti" (open requests). Tab 2 "Doklady": number, date, customer, stay, total, kind, paid state, PDF link. CSV export is a **non-goal**. |
| `GET /reservations/{rid}/invoice/new?request={id}` | `invoice_new` | `templates/invoice_form.html`, laid out exactly as UX row H3 (§0.5): sections Customer → Items → Payment → Language, then a sticky footer `div.actions` with the hint `t('invoice.next_number', number=…)`, *Preview* (`<button class="btn" formaction="/reservations/{rid}/invoice/preview" formtarget="_blank">`) and *Issue invoice* (`<button class="btn accent primary" data-confirm data-confirm-message="{{ t('invoice.issue_confirm') }}">`). Prefill from the request if given. **Already paid** is ticked by default. The accommodation price input gets `autofocus`. If the apartment has no legal entity, show only an error panel with a link to `/entities`. Inline amber warnings at the top: 15-day (payer), no IBAN (only when unpaid), missing registry entry (blocks issuing). The "next number" is informational (computed without locking); the real number is assigned in `issue()`. |
| `POST /reservations/{rid}/invoice/preview` | `invoice_preview` | §6.1 preview; returns the PDF inline |
| `POST /reservations/{rid}/invoice` | `invoice_issue` | `build_draft` → `validate_for_issue` → `issue`. On issues, re-render with errors (422). On success, 303 → `/invoices/{id}?issued=1`. |
| `GET /invoices/{id}` | `invoice_detail` | Summary + PDF embed link + actions: *Stáhnout PDF*, *Označit jako zaplacené* (if unpaid), *Poslat hostovi* (if `buyer_email` or `request.delivery_email`), *Storno / Opravný doklad* |
| `GET /invoices/{id}.pdf` | `invoice_pdf_download` | `Response(pdf_blob, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="faktura-{number}.pdf"', "Cache-Control": "no-store"})`, like `guest_form_pdf` |
| `POST /invoices/{id}/paid` | `invoice_mark_paid` | sets `marked_paid_at`; audit `invoice_marked_paid` |
| `POST /invoices/{id}/send` | `invoice_send` | explicit host action → `mail.enqueue(kind="invoice_issued", idempotency_key=f"invoice_issued:{id}:{n}")`, where `n` = the count of previous sends (so a re-send is allowed). Sets `emailed_at`; audit `invoice_sent`. |
| `POST /invoices/{id}/cancel` | `invoice_cancel` | form `reason`, `correction_date` (payer) → `invoices.cancel` → 303 to the new document |
| `POST /invoice-requests/{id}/decline` | `invoice_request_decline` | `decline_reason` required (5–200). `state='declined'`. No mail: the guest sees the declined state and the reason on their request page. Audit `invoice_request_declined`. Resolve alert `invoice_requested:{id}`. |
| `POST /reservations/{rid}/invoice-link` | `invoice_link_create` | Returns the page with the copy field containing `config.PUBLIC_BASE_URL + "/invoice/r/" + invoice_links.request_token(rid, None, "host")`. The optional checkbox *Poslat na e-mail hosta* enqueues `invoice_request_link` to `reservation.guest_email` or the claim e-mail. Audit `invoice_link_created`. |
| `GET /entities/ares?ico=` | `entity_ares` | JSON (host only), §4.1 |

### 8.2 Guest / public (`routes/invoice_public.py`, `protect_guest_post`)

| Method + path | Handler | Notes |
|---|---|---|
| `GET /invoice` | `invoice_request_page` | §3.2 |
| `POST /invoice` | `request_link` | §3.2 |
| `GET /invoice/r/{token}` | `invoice_request_form` | §3.4. An invalid or expired token calls `routes/guest.py::_unavailable(request, lang, "invoice_link_expired", 404)` (import it). Add `"invoice_link_expired": ("invoice_link_expired_title", "invoice_link_expired_help")` to its `titles` dict. |
| `POST /invoice/r/{token}` | `invoice_request_save` | §3.4. Only while the request is `open` (after issue it is read-only). |
| `GET /invoice/r/{token}/ares?ico=` | `invoice_request_ares` | §4.2 |
| `GET /invoice/d/{token}` | `invoice_download` | `read_download_token` → serve `pdf_blob` (`Content-Disposition: attachment`, `Cache-Control: no-store`, `X-Robots-Tag: noindex`). Rate limit `invoice_download` 30/h per client. |
| `GET /l/{token}/{reservation_id}/invoice` | in `routes/guest.py`: `guest_invoice_entry` | runs the same guards as `stay_overview` (`_require_pin`, `_reservation_for_guest`); requires `date_to ≤ today` and the policy `on`. Mints `request_token(rid, reservation.guest_email or claim email or None, "guest")` → 303. |

`templates/guest/stay.html` footer, after the last `{% endif %}` before `{% endblock %}`:

```html
{% if invoice_available %}
  <p class="g-intro" style="margin-top:18px"><a href="/l/{{ token }}/{{ reservation.id }}/invoice?lang={{ lang }}">{{ t('invoice_need') }} &rarr;</a></p>
{% endif %}
```

`invoice_available` = `apartment["invoice_requests_policy"] == "on" and reservation["date_to"] <= today`, set in `stay_overview`.

---

## 9. Mail, alerts, scheduler

**`mail.KINDS`** gains `"invoice_request_link"`, `"invoice_request_host"` and `"invoice_issued"`. The builders go in `mail_notify.py`, following `build_claim_link` / `build_completion` (`_shell`, `_block_*`):

**Every new kind also lands in exactly one of `mail.GUEST_KINDS` / `mail.HOST_KINDS`** (UX-74). `invoice_request_link` and `invoice_issued` are guest mail, so their payloads are built with `mail_notify.guest_payload(apartment, content, lang)`, which sets Reply-To to the legal entity's contact address. A guest who answers the invoice mail is answering about their own stay, and must reach the host, never `support@`. `invoice_request_host` is host mail and takes no Reply-To. `tests/test_claim_mail.py` fails until `KINDS` is partitioned, so this cannot be forgotten; `mail.enqueue` also logs a warning when a guest kind goes out with no Reply-To at all.

| Kind | To | When | Body (blocks) | Secret handling |
|---|---|---|---|---|
| `invoice_request_link` | the e-mail **on file** (path D), or `reservation.guest_email` (path B, host click) | §3.2 step 6, or a host click | heading `invoice_mail_link_title`; paragraph with property name + dates; button `invoice_mail_link_button` → `/invoice/r/{token}`; note "valid 7 days" (30 for host links); footer via `_guest_footer_lines` | The token **is** a secret. Reuse the existing mechanism in `mail.py`: put `CLAIM_SECRET_MARKER` (`{{claim_secret}}`) in the body where the token belongs, and store the token encrypted under `payload[CLAIM_SECRET_KEY]` (`claim_secret_enc`, via `db.encrypt_secret`). `delivery_body` / `delivery_html` substitute it at send time. The outbox and the console log never hold a working link. |
| `invoice_request_host` | `legal_entity.contact_email` | a new request is saved | "Host X požádal o fakturu" + buyer name + stay + button to `/reservations/{rid}#invoice` | none |
| `invoice_issued` | `request.delivery_email` (guest chose e-mail) **or** a host click on *Poslat* | after issue (only if `delivery=='email'`) or on click | the money slot: one `_block_panel` (UX-73) with the invoice number and the total as its label/value rows, and "Download invoice" as its **one** coral button → `/invoice/d/{download_token}` (valid 30 days). The status slot stays buttonless, so the message keeps a single primary. **No attachment**: `mail.py` has no attachment support, and adding it is out of scope. | The download token goes through the same marker mechanism |

**Alerts:**
- New kind `invoice_requested` (reservation-linked). Add it to `alerts._TRANSLATED_ALERT_KINDS` and to the tuple in `_present_translated` that uses `notification.reason.{kind}`.
- Raise with `alerts.raise_alert("warning", "invoice_requested", "Invoice requested", dedupe_key=f"invoice_requested:{request_id}", apartment_id=…, reservation_id=…)`. Resolve with `alerts.resolve(dedupe_key)` on issue or decline.

**Scheduler:**
- Extend the existing `_job_deadlines` rather than adding a job: call `invoices.expire_requests()` (open for > 90 days → declined, reason `expired`) and `invoices.purge_declined()` (declined for > 1 year → delete).
- Log and alert via the existing `_job_failed("deadlines")`.

---

## 10. Copy

**Host (`host_i18n.STRINGS` / `_INTERFACE_STRINGS`)**

| Key | EN | CS |
|---|---|---|
| `nav.invoices` | Invoices | Faktury |
| `invoices.title` | Invoices | Faktury |
| `invoices.tab.requests` / `.documents` | Requests / Documents | Žádosti / Doklady |
| `invoices.empty` | No invoices yet. Issue one from a stay, or switch on invoice requests for a property. | Zatím žádné faktury. Vystavte ji u pobytu, nebo u nemovitosti zapněte žádosti o fakturu. |
| `invoice.panel.title` | Invoice | Faktura |
| `invoice.new` | Issue invoice | Vystavit fakturu |
| `invoice.preview` | Preview | Náhled |
| `invoice.issue` | Issue invoice | Vystavit fakturu |
| `invoice.next_number` | Next number: %(number)s | Další číslo: %(number)s |
| `invoice.section.customer` | Customer | Odběratel |
| `invoice.section.items` | Items | Položky |
| `invoice.section.payment` | Payment | Úhrada |
| `invoice.section.language` | Language | Jazyk |
| `invoice.for_company` | For a company | Na firmu |
| `invoice.issued_flash` | Invoice %(number)s issued. | Faktura %(number)s vystavena. |
| `invoice.more` | More | Další |
| `invoice.add_item` | + Other item | + Jiná položka |
| `invoice.issue_confirm` | Once issued, the invoice cannot be changed. Mistakes are fixed with a cancellation or corrective document. | Vystavenou fakturu nelze měnit. Chyby opravíte stornem nebo opravným dokladem. |
| `invoice.link` | Link for the guest | Odkaz pro hosta |
| `invoice.link_hint` | The guest fills in their billing details; you then issue the invoice. Valid 30 days. | Host vyplní fakturační údaje, vy pak fakturu vystavíte. Platí 30 dní. |
| `invoice.link_send` | Also send it to the guest's e-mail | Poslat také na e-mail hosta |
| `invoice.buyer` | Customer | Odběratel |
| `invoice.items` | Items | Položky |
| `invoice.item.accommodation` | Accommodation – %(name)s, %(from)s – %(to)s, %(nights)s nights, %(persons)s guests | Ubytování – %(name)s, %(from)s – %(to)s, %(nights)s nocí, %(persons)s os. |
| `invoice.item.stay_fee` | Local stay fee | Poplatek z pobytu |
| `invoice.item.stay_fee_include` | Include the stay fee collected (%(amount)s Kč) | Zahrnout vybraný poplatek z pobytu (%(amount)s Kč) |
| `invoice.item.other` | Other item | Jiná položka |
| `invoice.price_gross` | Price incl. VAT (Kč) | Cena vč. DPH (Kč) |
| `invoice.price` | Price (Kč) | Cena (Kč) |
| `invoice.vat_rate` | VAT rate | Sazba DPH |
| `invoice.vat_12` / `.vat_21` | 12 %% / 21 %% | 12 %% / 21 %% |
| `invoice.already_paid` | Already paid | Již uhrazeno |
| `invoice.paid_via` | Paid via | Způsob úhrady |
| `invoice.paid_via.airbnb` / `.booking` / `.direct_transfer` / `.cash` / `.other` | Airbnb / Booking.com / Bank transfer / Cash / Other | Airbnb / Booking.com / Převodem / Hotově / Jinak |
| `invoice.duzp` | Tax point (DUZP) | Datum uskutečnění zdanitelného plnění |
| `invoice.due` | Due date | Datum splatnosti |
| `invoice.lang` | Invoice language | Jazyk faktury |
| `invoice.lang.cs` / `.en` | Czech / English (with Czech labels) | Česky / Anglicky (s českými popisky) |
| `invoice.warn_15_days` | As a VAT payer you must issue the tax document within 15 days of the tax point (§28(8) VAT Act). | Jako plátce DPH musíte daňový doklad vystavit do 15 dnů od DUZP (§ 28 odst. 8 zákona o DPH). |
| `invoice.warn_no_iban` | The legal entity has no bank account, so the invoice will have no QR code. | Subjekt nemá bankovní účet, faktura proto nebude mít QR kód. |
| `invoice.err.no_entity` | Assign a legal entity to this property first. | Nejdřív nemovitosti přiřaďte subjekt. |
| `invoice.err.seller_seat` | The legal entity needs a registered address (sídlo). | Subjekt musí mít vyplněné sídlo. |
| `invoice.err.registry` | Add the registry entry to the legal entity (e.g. "Fyzická osoba zapsaná v živnostenském rejstříku"). | Doplňte u subjektu údaj o zápisu v rejstříku (např. „Fyzická osoba zapsaná v živnostenském rejstříku“). |
| `invoice.err.seller_dic` | A VAT payer must have a VAT number (DIČ). | Plátce DPH musí mít DIČ. |
| `invoice.err.amount` | Enter the accommodation price (a whole or decimal amount in Kč, above 0). | Zadejte cenu ubytování (v Kč, větší než 0). |
| `invoice.cancel` | Cancel invoice | Stornovat fakturu |
| `invoice.corrective` | Issue corrective tax document | Vystavit opravný daňový doklad |
| `invoice.cancel_reason` | Reason (printed on the document) | Důvod (bude uveden na dokladu) |
| `invoice.correction_date` | Date of the correction (§42(3)) | Den uskutečnění opravy (§ 42 odst. 3) |
| `invoice.reissue` | Issue a new invoice (prefilled) | Vystavit novou fakturu (předvyplnit) |
| `invoice.mark_paid` | Mark as paid | Označit jako zaplacené |
| `invoice.send` | Send to the customer's e-mail | Poslat na e-mail odběratele |
| `invoice.request.decline` | Decline request | Odmítnout žádost |
| `invoice.request.decline_reason` | Reason shown to the guest | Důvod, který uvidí host |
| `apartment.form.invoice_policy.label` | Invoice requests from guests | Žádosti hostů o fakturu |
| `apartment.form.invoice_policy.off` | Off (default) — only you can issue invoices | Vypnuto (výchozí) — faktury vystavujete jen vy |
| `apartment.form.invoice_policy.on` | On — past guests can request an invoice | Zapnuto — hosté mohou po pobytu požádat o fakturu |
| `apartment.form.invoice_policy.hint` | Guests only fill in billing details. You confirm the amount and issue the invoice. | Hosté vyplní jen fakturační údaje. Částku potvrdíte a fakturu vystavíte vy. |
| `entities.vat_status.label` | VAT status | Postavení k DPH |
| `entities.vat_status.non_payer` / `.identified` / `.payer` | Not a VAT payer / Identified person (e.g. Airbnb commission) / VAT payer | Neplátce DPH / Identifikovaná osoba (např. kvůli provizi Airbnb) / Plátce DPH |
| `entities.registry.label` | Registry entry printed on invoices | Údaj o zápisu v rejstříku na fakturách |
| `entities.registry.trade` | Fyzická osoba zapsaná v živnostenském rejstříku | Fyzická osoba zapsaná v živnostenském rejstříku |
| `entities.invoice_prefix.label` | Invoice number prefix (optional) | Předpona čísla faktury (nepovinné) |
| `entities.invoice_next.label` | Continue numbering from (one-time) | Pokračovat v číslování od (jednorázově) |
| `entities.invoice_next.hint` | Use this if you already issued invoices this year in another tool. The next UbyHost invoice gets this number. | Použijte, pokud jste letos už fakturovali jinde. Další faktura z UbyHost dostane toto číslo. |
| `entities.invoice_due.label` | Default payment term (days) | Výchozí splatnost (dny) |
| `entities.invoice.snapshot_hint` | Changes apply to new invoices only; issued invoices keep the details they were issued with. | Změny platí jen pro nové faktury; vystavené faktury si ponechají původní údaje. |
| `entities.ares` | Load from ARES | Načíst z ARES |
| `notification.reason.invoice_requested` | A guest asked for an invoice. | Host požádal o fakturu. |

**Guest (`i18n.STRINGS`)**

| Key | EN | CS |
|---|---|---|
| `invoice_need` | Need an invoice for this stay? | Potřebujete za pobyt fakturu? |
| `invoice_req_title` | Request an invoice | Žádost o fakturu |
| `invoice_req_intro` | Enter the e-mail you used when registering for the stay and your arrival date. If they match a completed stay, we'll send you a link to fill in your billing details. | Zadejte e-mail, který jste použili při registraci k pobytu, a datum příjezdu. Pokud odpovídají ukončenému pobytu, pošleme vám odkaz k vyplnění fakturačních údajů. |
| `invoice_req_email` / `invoice_req_arrival` / `invoice_req_code` | E-mail / Arrival date / Booking code (optional) | E-mail / Datum příjezdu / Kód rezervace (nepovinné) |
| `invoice_req_submit` | Send me the link | Poslat odkaz |
| `invoice_req_sent_title` | Check your e-mail | Zkontrolujte e-mail |
| `invoice_req_sent_body` | If we found a completed stay with these details, we've sent a link to that e-mail address. It can take a few minutes. | Pokud jsme našli ukončený pobyt s těmito údaji, poslali jsme na tento e-mail odkaz. Může to trvat několik minut. |
| `invoice_req_too_many` | Too many attempts. Please try again in an hour. | Příliš mnoho pokusů. Zkuste to prosím za hodinu. |
| `invoice_req_no_mail` | Online requests are not available. Please ask your host directly. | Online žádost není k dispozici. Obraťte se prosím přímo na ubytovatele. |
| `invoice_form_title` | Billing details | Fakturační údaje |
| `invoice_for_company` | For a company | Na firmu |
| `invoice_payment_title` | Payment (optional) | Platba (nepovinné) |
| `invoice_edit` | Edit details | Upravit údaje |
| `invoice_waiting_title` | Your host has your request | Ubytovatel má vaši žádost |
| `invoice_buyer_name` / `_street` / `_city` / `_zip` / `_country` / `_ico` / `_dic` / `_email` | Name or company / Street and number / City / Postcode / Country / Company ID (IČO) / VAT ID / E-mail | Jméno nebo firma / Ulice a číslo / Obec / PSČ / Stát / IČO / DIČ / E-mail |
| `invoice_ares_button` | Fill in from ARES | Doplnit z ARES |
| `invoice_ares_failed` | We couldn't load the company from ARES. Please fill in the details yourself. | Firmu se nepodařilo načíst z ARES. Vyplňte prosím údaje ručně. |
| `invoice_amount_hint` | How much you paid for the accommodation (optional) | Kolik jste za ubytování zaplatili (nepovinné) |
| `invoice_paid_via` | Paid via | Způsob platby |
| `invoice_delivery` | How do you want to receive it? | Jak chcete fakturu dostat? |
| `invoice_delivery_download` | I'll download it here | Stáhnu si ji zde |
| `invoice_delivery_email` | Send it to my e-mail | Poslat na e-mail |
| `invoice_note` | Note for the host (optional) | Poznámka pro ubytovatele (nepovinné) |
| `invoice_form_submit` | Send to host | Odeslat ubytovateli |
| `invoice_state_open` | Your host has your request and will issue the invoice. You can still change the details. | Ubytovatel má vaši žádost a fakturu vystaví. Údaje můžete ještě změnit. |
| `invoice_state_issued` | Your invoice %(number)s is ready. | Vaše faktura %(number)s je připravena. |
| `invoice_download` | Download invoice (PDF) | Stáhnout fakturu (PDF) |
| `invoice_state_declined` | Your host declined the request: %(reason)s | Ubytovatel žádost odmítl: %(reason)s |
| `invoice_err_latin` | Please use Latin letters (as on a Czech or EU invoice). | Použijte prosím latinku. |
| `invoice_err_ico` | That company ID (IČO) is not valid. | IČO není platné. |
| `invoice_link_expired_title` | This link has expired | Platnost odkazu vypršela |
| `invoice_link_expired_help` | Request a new invoice link at /invoice, or ask your host. | O nový odkaz požádejte na /invoice, nebo se obraťte na ubytovatele. |
| `invoice_mail_link_subject` | Invoice for your stay at %(property)s | Faktura za pobyt – %(property)s |
| `invoice_mail_link_title` | Fill in your billing details | Vyplňte fakturační údaje |
| `invoice_mail_link_button` | Fill in details | Vyplnit údaje |
| `invoice_mail_issued_subject` | Invoice %(number)s | Faktura %(number)s |
| `invoice_mail_issued_button` | Download invoice | Stáhnout fakturu |
| `invoice_mail_link_expiry` | The link is valid for %(days)s days. | Odkaz platí %(days)s dní. |

---

## 11. Explicit non-goals

1. **No Fakturoid**: no API calls, no account, no import or export, no embed, no MCP. Fakturoid behaviour is a reference only.
2. **No recurring invoices, proformas/zálohovky, quotes, delivery notes, reminders, or payment-gateway links.**
3. **No accounting export** (ISDOC, Pohoda XML, CSV of the ledger). The host downloads PDFs.
4. **Minimal editing**: no drafts saved server-side (the open request *is* the draft), no free numbering, no editing after issue, at most 3 lines, no discounts, no quantities other than 1.
5. **No auto-send.** Mail goes only when the guest chose e-mail delivery, or the host clicks *Poslat*.
6. **No foreign currency, no OSS/MOSS, no reverse-charge scenarios, no EET.**
7. **No bank matching.** The host marks an invoice paid.
8. **No invoice for stays not completed** (`date_to > today`) on the guest paths. The host path allows any stay (e.g. an advance) ⚠ FLAG-7.

---

## 12. Tests (`App/tests/`)

| File | Cases |
|---|---|
| `test_invoice_numbering.py` | first invoice `2026-0001`, VS `20260001`; prefix; yearly restart; one-time continuation (8 → `2026-0008`, fields cleared, value ≤ last refused); **20 threads issuing concurrently → 20 distinct consecutive numbers, no gaps**; an exception during PDF render → number not consumed |
| `test_invoice_immutability.py` | UPDATE of `buyer_name` / `total_haler` / `pdf_blob` on an issued row raises; `marked_paid_at` update OK; item insert/update/delete on an issued invoice raises; delete raises without the unlock; the purge deletes with the unlock only for invoices older than 10 full years |
| `test_invoice_vat.py` | payer 4 000 Kč gross at 12 % → tax 428.57, base 3 571.43; the recap groups by rate; the stay-fee line is excluded from the base/VAT; non-payer: the drawn text contains no "DPH" except "Nejsem plátce DPH", no "DUZP" and no "daňový doklad". Collect the text by monkeypatching `Canvas.drawString`/`drawRightString` in `invoice_pdf`; do not add a PDF-parsing dependency. |
| `test_invoice_corrections.py` | non-payer storno: negative items, same series, title; payer ODD: §45 fields present; a second correction refused by the unique index; reissue prefill |
| `test_invoice_ux.py` | the issue form has "Already paid" checked by default, the accommodation input has `autofocus`, the Preview button has `formtarget="_blank"`, and the Issue button has `data-confirm`; after issue the response redirects to `/invoices/{id}` with the issued flash; the stay panel highlights an open request and shows *Issue invoice* as primary; the guest request URL renders the form → waiting → ready → declined states in turn; company fields are ignored unless `for_company` is set; the form works without JS (all inputs present in the HTML) |
| `test_invoice_public.py` | identical response body for match / no match / wrong e-mail / rate-limited-by-email; the IP limit shows the too-many message; a mail is enqueued only on a match; one mail per day per stay (idempotency); `booking_code` narrows but is not required; a stay with `date_to > today` doesn't match; policy `off` doesn't match |
| `test_invoice_tokens.py` | expired request token → 404 page; tampered token → 404; download token with a stale sha prefix → 404; a host token lives 30 days, a guest token 7 |
| `test_invoice_ares.py` | IČO checksum vectors (`04656679` valid); `lookup` maps the saved fixture JSON (the Fakturoid s.r.o. response) to the fields; timeout → None (mock `requests.get`) |
| `test_invoice_policy.py` | `invoice_requests_policy` defaults `off`; sanitised; the stay page link shows only when `on` and completed |
| i18n / mail parity | existing parity tests + `KINDS` builders |

---

## 13. Build this in this order (one commit per step; tests green after each)

### Phase 1 — host issues invoices (usable on its own)

| # | Step | Files | Done when |
|---|---|---|---|
| 1 | `db.immediate()`, columns and tables from §5 (not the `invoice_requests_policy` column yet), indexes, triggers | `db.py` | a fresh DB has the tables; an UPDATE of `buyer_name` on a row with `issued_at` set raises |
| 2 | Entity invoice settings: `vat_status` select, `registry_entry`, `invoice_prefix`, `invoice_next_number` (+year), `invoice_due_days`; IČO checksum; `delete_entity` guard | `routes/admin.py` (`ENTITY_FIELDS` + create/update), `templates/entities.html`, §10 `entities.*` keys | saving an entity with IČO `04656679` works; `12345678` shows an error; an entity with invoices can't be deleted |
| 3 | `invoices.py`: `build_draft`, VAT maths, `validate_for_issue` | `invoices.py`, `tests/test_invoice_vat.py` (arithmetic) | 4 000 Kč at 12 % → 428.57 / 3 571.43 |
| 3b | Fix the house-book font (§7.3); the fonts are already in `App/app/static/fonts/` | `housebook.py`, `tests/test_pdf_fonts.py` | the glyph test passes |
| 4 | `invoice_pdf.py` = the reference file + 3 edits (§7) | `invoice_pdf.py` | the four sample invoices re-render identically in layout; `render(..., preview=True)` starts with `b"%PDF"`; the footer link annotation points to ubyhost.com |
| 5 | `issue` + `allocate_number` | `invoices.py`, `tests/test_invoice_numbering.py`, `tests/test_invoice_immutability.py` | the 20-thread test gives 20 consecutive numbers; a PDF failure consumes no number |
| 6 | Host routes and pages: list, new/preview/issue, detail, PDF download, mark paid; stay panel `#invoice` (without the guest-link parts); sidebar item + icon + palette | `routes/invoices.py`, `main.py`, `templates/invoices.html`, `invoice_form.html`, `invoice_detail.html`, `reservation_detail.html`, `base.html`, `_components.html`, §10 host keys | the host can issue, download and mark paid in the browser |
| 7 | Corrections (`cancel`) + reissue prefill | `invoices.py`, `routes/invoices.py`, `tests/test_invoice_corrections.py` | storno/ODD documents render; a second correction is refused |
| 8 | *Send to customer* (host click only) | `mail.py` `KINDS` += `invoice_issued`, `mail_notify.py` builder, `invoice_links.py` (download token only), `GET /invoice/d/{token}` in `routes/invoice_public.py` | the mail contains a working download link; the outbox body contains the marker, not the token |
| 9 | Retention purge wired into `/settings/purge-expired` | `invoices.py`, `routes/admin.py` | a test with a 2014 invoice deletes it; a 2016 one stays (when today = 2026) |

### Phase 2 — guests request invoices

| # | Step | Files | Done when |
|---|---|---|---|
| 10 | `apartment.invoice_requests_policy` toggle (mirror of `stay_fee_policy`) | `db.py`, `_apartment_payload`, `apartment_form.html`, §10 keys, `demo.py` | default `off` |
| 11 | Request tokens + host "link for guest" (copy field + optional send) | `invoice_links.py`, `routes/invoices.py`, mail kind `invoice_request_link`, `tests/test_invoice_tokens.py` | expired/tampered tokens → 404 page |
| 12 | Guest request form `/invoice/r/{token}` + stay-page entry `/l/{token}/{rid}/invoice` + host alert + `invoice_request_host` mail | `routes/invoice_public.py`, `routes/guest.py`, templates `guest/invoice_form.html`, `stay.html` footer link, `alerts.py` | a guest can submit details and later download the issued invoice |
| 13 | Public `/invoice` page with rate limits + Turnstile + identical responses | `routes/invoice_public.py`, `guest/invoice_request.html`, `guest/invoice_request_sent.html`, `tests/test_invoice_public.py` | all `test_invoice_public.py` cases pass |
| 14 | ARES lookups (seller in the entity form, buyer in the guest form) | `ares.py`, the two routes, `tests/test_invoice_ares.py` | the fixture maps correctly; a timeout returns None |
| 15 | Request expiry/cleanup in `_job_deadlines` | `invoices.py`, `scheduler.py` | open > 90 days → declined |
| 16 | Docs + manual check | `App/README.md`, `docs/DESIGN.md` | guest pages at 375 px in EN/CS; host desktop; light mode; the invoice QR scans in a Czech banking app |
| 17 | Accountant sign-off on §14 before switching `invoice_requests_policy` on for real properties | — | — |

## 14. Needs a lawyer / accountant to confirm

1. **FLAG-1** — The registry-entry wording and court-code mapping (OZ §435(1)); whether a non-business private host renting without a trade licence can use this at all.
2. **FLAG-2** — Identifikovaná osoba: omit the DIČ on guest invoices, and print "Nejsem plátce DPH (identifikovaná osoba)"?
3. **FLAG-3** — The DUZP default (checkout day) vs the date the platform payment was received (§29(1)(h)); how Airbnb payouts affect the tax point for payers.
4. **FLAG-4** — 12 % for accommodation. Treatment of the stay fee on a payer's document ("mimo předmět DPH" vs Fakturoid's "nulová sazba"). The rate for cleaning or other extras.
5. **FLAG-5** — Tax computed top-down from gross with per-line rounding (§37 not fetched).
6. **FLAG-6** — Storno vs ODD when the entity's VAT status changed between issue and correction.
7. **FLAG-7** — Invoices issued by the host before the stay ends (advance payments / "daňový doklad k přijaté platbě" not supported).
8. **FLAG-8** — A 10-year retention for all statuses (DPH §35(2); ZoÚ §31(2)(b) 5 years), and the start point "end of the year of issue" vs "end of the tax period in which the supply occurred".
9. The amount invoiced for platform bookings: the guest's total paid to the platform, or the accommodation price net of the platform's guest fee.
10. Whether a CS-labelled bilingual document is acceptable for EN-speaking foreign business buyers (DŘ allows the tax authority to request a translation).
11. GDPR: the buyer snapshot is kept for 10 years under Art. 6(1)(c); the public request flow uses the stored e-mail only to send the link.

---

## 15. Sources (all retrieved 2026-09-23)

| # | What | URL |
|---|---|---|
| F1 | Fakturoid homepage (product claims: "Faktura pod minutu", "Povinné náležitosti faktury pohlídá robot") | https://www.fakturoid.cz/ |
| F2 | Fakturoid manifest (product philosophy: simple, automatic, not accounting) | https://www.fakturoid.cz/manifest |
| F3 | Fakturoid — Faktury online (feature list) | https://www.fakturoid.cz/faktury-online |
| F4 | Support — Faktury (index) | https://www.fakturoid.cz/podpora/faktury |
| F5 | Support — Náležitosti faktury | https://www.fakturoid.cz/podpora/faktury/nalezitosti-faktury |
| F6 | Support — Vytvoření faktury | https://www.fakturoid.cz/podpora/faktury/vytvoreni-faktury |
| F7 | Support — Číselné řady ("nejvyššího z posledních 10 faktur"; "ze zákona navazovat"; series per type) | https://www.fakturoid.cz/podpora/nastaveni/ciselne-rady |
| F8 | Support — Tipy pro číslování (`rok-číslo`, proforma `1-rok-číslo`) | https://www.fakturoid.cz/podpora/nastaveni/tipy-pro-cislovani |
| F9 | Support — Variabilní symbol (dashes removed, ≤10 digits, not mandatory) | https://www.fakturoid.cz/podpora/faktury/variabilni-symbol |
| F10 | Support — QR kód na faktuře | https://www.fakturoid.cz/podpora/faktury/qr-kod-na-fakture |
| F11 | Support — Zpětné změny faktur | https://www.fakturoid.cz/podpora/faktury/zpetne-zmeny-faktur |
| F12 | Support — Opravný daňový doklad (reason required; same series; one per invoice) | https://www.fakturoid.cz/podpora/faktury/opravny-danovy-doklad |
| F13 | Support — Storno faktury (non-payer; negative items; "Storno k faktuře číslo") | https://www.fakturoid.cz/podpora/faktury/storno-faktury |
| F14 | Support — Webfaktura | https://www.fakturoid.cz/podpora/faktury/webfaktura |
| F15 | Support — Faktura v cizím jazyce (11 languages) | https://www.fakturoid.cz/podpora/faktury/faktura-v-cizim-jazyce |
| F16 | Support — Faktura v cizí měně | https://www.fakturoid.cz/podpora/faktury/faktura-v-cizi-mene |
| F17 | Support — DPH na faktuře | https://www.fakturoid.cz/podpora/faktury/dph-na-fakture |
| F18 | Almanach — Náležitosti faktury (non-payer rules; "neplátce DPH" voluntary; §1963 OZ 30 days; ZoÚ §11(f) explained) | https://www.fakturoid.cz/almanach/zacatky-podnikani/nalezitosti-faktury |
| F19 | Almanach — Jak fakturovat pronájem Airbnb (12 %/21 %; fee separate; identified person) | https://www.fakturoid.cz/almanach/zacatky-podnikani/jak-fakturovat-pronajem-airbnb |
| L1 | Zákon o DPH §28 (15-day rule, odst. 8) | https://www.pracepropravniky.cz/zakony/zakon-o-dani-z-pridane-hodnoty-zakon-o-dph/paragraf-28/ |
| L2 | Zákon o DPH §29 (náležitosti, označení) | https://www.pracepropravniky.cz/zakony/zakon-o-dani-z-pridane-hodnoty-zakon-o-dph/paragraf-29/ |
| L3 | Zákon o DPH §35 (10 years) | https://www.pracepropravniky.cz/zakony/zakon-o-dani-z-pridane-hodnoty-zakon-o-dph/paragraf-35/ |
| L4 | Zákon o DPH §45 (ODD fields a–k) | https://www.pracepropravniky.cz/zakony/zakon-o-dani-z-pridane-hodnoty-zakon-o-dph/paragraf-45/ |
| L5 | Zákon o účetnictví §11 (účetní doklad a–f) | https://www.pracepropravniky.cz/zakony/zakon-o-ucetnictvi-uplne-zneni/paragraf-11/ |
| L6 | Zákon o účetnictví §31 (5 years; secondary summary) | https://www.dauc.cz/clanky/5144/uchovavani-dokladu-danovymi-subjekty |
| L7 | OZ §435 (obchodní listiny; secondary sources) | https://www.akhsp.cz/novinky/povinnosti-souvisejici-s-podnikanim-informace-uvadene-na-obchodnich-listinach |
| L8 | Poplatek z pobytu is outside the DPH base (Q&A) | https://www.dauc.cz/detail-otazky/14719/ubytovani-a-poplatky |
| T1 | ARES REST API — ekonomické subjekty (live response for IČO 04656679) | https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/04656679 |
| T2 | QR Platba — SPAYD specification | https://qr-platba.cz/pro-vyvojare/specifikace-formatu/ |
| Repo | `App/app/{db,mail,mail_notify,housebook,alerts,scheduler,rate_limit,turnstile,security,claim,validation}.py`, `routes/{guest,admin,admin_accounts}.py`, templates `guest/stay.html`, `guest/claim.html`, `reservation_detail.html`, `entities.html`, `apartment_form.html`, `base.html`, `_components.html`; `docs/DESIGN.md`, `AGENTS.md` | read-only checkout of `jsfpechar-ops/jsfpecharoperations` |
