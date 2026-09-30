# PLAN — Poplatek z pobytu (host remittance) · v2

> **Status: APPROVED — ready to implement (owner decisions of 30 Sep 2026).**
> v2 of this file. It keeps v1's product (hlášení PDF, list, detail with QR
> Platba, per-property template, entity signature, monthly/quarterly cadence) and
> fixes what did not match the code, the law or the owner's decisions. The
> changes are listed in §0.1.
>
> **What this is.** A host-only, per-property calculator and PDF generator for
> the Czech *poplatek z pobytu* (zákon č. 565/1990 Sb.). The host sets the rate
> and the council details once. Each period UbyHost counts the liable and exempt
> **lůžkodny** (person-nights) of signed guests, shows the total with a QR Platba
> for paying the council, and renders a one-page **hlášení** PDF on demand. A CSV
> matches the §3g evidenční kniha.
>
> **What this is not.**
> - It is guest-invisible: no guest screen, e-mail, form field or legal text changes.
> - It files nothing electronically, has no datová schránka integration, and does not check payments.
> - It does not replicate each municipality's own form, and it guarantees nothing about compliance.
>
> **Optional by design.** Nothing renders anywhere until a property's rate is
> above 0. It is not part of onboarding, and there is no nag to turn it on.
>
> **Audience:** the implementing agent (Cursor). If the repo does not match
> what this plan says, **stop and report**. Do not guess.

---

## 0. Rules for the implementing agent (read first, obey always)

1. **One step = one branch = one pull request**, in §13 order. Never commit to, push to or merge into `main`. The owner reviews and merges. Production deploy is manual and not your job. Deploy staging only when the owner says so.
2. **Tests after every step**, from `App/`: `.venv/bin/python -m pytest tests -q`, on **Python 3.12** (as CI). Do not prefix with `PYTHONPATH=App` (`AGENTS.md`).
3. **Baseline first (step 0).** Record which tests already fail on `main` before you change anything. The plan's author saw 22 failures in `test_dashboard_queue_copy.py`, `test_flash_next_step.py`, `test_pin_rotation_flash.py` and `test_status_colours.py`, on Python 3.10, where `test_soap.py` also doesn't import. A step is green when **no test fails that was not in the baseline** and every new test passes.
4. **Use exactly the names given** (files, functions, columns, routes, i18n keys, CSS classes). No extra fields or "nice to have" options.
5. **Copy every user-facing host string verbatim** from §12 into **both** `en` and `cs`. `tests/test_host_i18n.py::test_english_and_czech_carry_the_same_keys` enforces parity. Formatting is `%(name)s`. The PDF and the CSV are Czech-only, and their text lives in `stay_fee.py` / `stay_fee_remittance_pdf.py`.
6. **Flash messages go through `_flash(request, key, **params)`**, never a literal (`tests/test_flash_literals.py`).
7. **Security on every host route:**
   - `guard = auth.require_login(request)`; `if guard: return guard`.
   - Load rows through `access.*` (owner-scoped).
   - Every POST carries `<input type="hidden" name="_csrf" value="{{ csrf_token }}">`.
   - The router is `APIRouter(dependencies=[Depends(security.protect_host_post)])`, like `routes/invoices.py`.
   - Never mark host-typed text `|safe`.
8. **Host CSS only.** Host pages use `var(--ink)`, `var(--muted)`, `var(--line)`, `var(--brand)`, `var(--canvas)` and the existing classes: `page-header`, `panel tight`, `table-cards`, `clickable-row`, `row-primary-link`, `pill blue|green|amber`, `chips`/`chip`/`chip on`, `stay-metrics detail-hero`/`detail-metric`/`metric-label`/`metric-value`, `copyrow`, `btn`, `btn accent primary`. The `--g-*` variables are **guest** tokens: never use them here. Light mode only. **One coral primary button per screen.**
9. **Public repo:** no real names, IČO, addresses, account numbers of real people, databases or keys in code, tests or docs. Council accounts and addresses of public offices, as in the mockups, are public data and fine.
10. **Do not touch:**
    - Anything guest-facing: `routes/guest.py`, `templates/guest/*`, `static/guest*`, `static/signature.js`, `static/ticket.js`, `mail_notify.py`, `claim.py` (reading `claim.prague_today()` is fine).
    - `reservation_detail.html`. **There is no stay-page fee panel**; its empty `#money` slot stays empty.
    - UbyPort sending, the house book, invoices.
    - `docs/POPLATEK_Z_POBYTU.md`, which the owner maintains.

### 0.1 What changed from v1 (and why)

| # | v1 said | v2 does | Why |
|---|---|---|---|
| 1 | A stay counts in the period of its **checkout**, while `period_summary` summed every stay **overlapping** the period | **Each night counts in the period its date falls in** | Owner decision. Praha 1: *"na konci měsíce je nutné spočítat dny a přiřadit je do správného měsíce"*. The v1 code double-counted cross-month stays |
| 2 | Out of scope when `nights > 60` | Out of scope when **`nights + 1 > 60`** (61+ calendar days) | Owner decision; §3a reads "nejvýše 60 po sobě jdoucích kalendářních dnů". On the lawyer list |
| 3 | Fee panel with Exempt on the **stay detail page** (§9.5, step 7) | Exempt/Charge lives on the **stay-fee detail page** `/stay-fees/{id}`. `reservation_detail.html` is untouched | Owner decision: no per-stay panel |
| 4 | One PDF **per property** | One hlášení **per legal entity + VS + cadence**. Properties sharing a VS are summed; the detail page says which are included | Owner decision. One payer files one hlášení per VS |
| 5 | "`payments.py` … not yet in the repo" (step 3 builds it) | `payments.py` **exists** with tests. Step 3 is removed | It shipped with invoices |
| 6 | `apartment.get(...)`, `guest.get(...)` | Plain `row["col"]` | `sqlite3.Row` has no `.get()` and would crash |
| 7 | CSS vars `--g-ink`, `--g-muted`… | Host tokens (§0 rule 8) | `--g-*` are guest tokens |
| 8 | Routes `/stay-fees/{id}/pdf` in §9 but `/stay-fees/{id}.pdf` in §13 | `/stay-fees/{id}/pdf` and `/stay-fees/{id}/csv` everywhere | The plan contradicted itself |
| 9 | §3g CSV needs a document type, but no column existed | `guest.doc_type`: derived (CZE → OP, else passport), editable on the **host** guest form | §3g(2)(d) |
| 10 | `fee_host_decision` / `fee_host_reason` presented as new | They share names with the **reverted 26 Sep build (AR-55)**. A one-time reset clears them | Old databases may hold guest-typed claims, possibly disability data |
| 11 | The PDF label and the footer instruction came from "`stay_fee_authority_*`" | Two explicit columns: `stay_fee_payee` ("MČ Praha 3", "města Brna") and `stay_fee_instruction` | The mockup prints both. No existing column held them |
| 12 | Mockups at `/tmp/opencode/*.jpg`; the real Praha 3 PDF | The repo files `docs/plans/stay-fee-remittance/*.jpg/.html` | The `/tmp` paths do not exist |
| 13 | Mockup `stay-fee-document*.html`: the footer "Strana 1/1" used `class="page"` | Renamed to `pageno`; the JPGs are re-rendered | The page-sized white box covered half of both JPGs |
| 14 | Brno mockup: "Měsíční hlášení / Srpen 2026 / 1 743 Kč" with Praha 3's data box `eqkbt8g` | "Čtvrtletní hlášení / 3. čtvrtletí 2026 / 840 Kč" (40 × 21), with a neutral data-box text | It contradicted the list mockup (Brno = quarterly, 840 Kč) |
| 15 | "Base is nights, a correction vs nights − 1" | Nights (unchanged). The claim is removed | The old plan also counted nights |
| 16 | "The bank transfer with the correct VS *is* the filing" | Removed. The host sends the hlášení **and** pays | Praha 1 / Praha 3 ask for the hlášení itself (data box, post, signed e-mail) |
| 17 | `charge` "for an adult booking for a child" | `charge` = correction when the birth date is wrong. It never charges a real minor, and it never overrides "not subject" | Under-18s are exempt by law |
| 18 | CSV rows didn't say which guests | Signed guests on active stays, not archived. GDPR-restricted guests count in the totals with their identity blanked | Consistent with the house book and Art. 18 |
| 19 | i18n §12 covered ~25 keys | §12 covers **every** host string shown in the mockups and flows | Parity alone doesn't catch literals in templates |
| 22 | The PDF was a copy of the office-style HTML mockup | The PDF is the owner's **Invoice companion** design (`stay-fee-remittance-design/`), fed with this plan's data. The HTML mockups stay as a content reference | Owner decision, 30 Sep |
| 21 | Panel placed "between Guest link and Calendars" | The panel goes inside the form, after `#communication`, before Notes. The nav link still sits between the two | `#calendars` is outside `</form>` (`apartment_form.html` ~line 406); fields there would not save |
| 20 | Free-text exemption reason, unguided | Still free text ≤ 120. The hint says "state the ground, not health details" | Data minimisation (GDPR Art. 5(1)(c)); lawyer list |

---

## 1. The document we generate (the "hlášení")

**Design: "Invoice companion"**, the owner's selected PDF design (30 Sep 2026).

- The design spec is `docs/plans/stay-fee-remittance-design/DESIGN.md`, the owner's file: **do not edit it**.
- The reference output is `docs/plans/stay-fee-remittance-design/sample-invoice-companion.pdf`, regenerated with `build_sample.py` from fictional data.
- **The renderer is already written** as `App/app/stay_fee_remittance_pdf.py` in the core patch (§13 step 1). It is the owner's kit renderer, adapted to this plan's data (see below). Only change it if a test proves a mismatch.
- The HTML mockups `stay-fee-remittance/stay-fee-document*.html/.jpg` are kept as a **content** reference (which facts the office expects). They are **not** the visual design.

Anatomy, top to bottom (as in DESIGN.md):

| # | Block | Content | Source |
|---|---|---|---|
| 1 | Top rule | 1.6 mm coral line across A4 | fixed |
| 2 | Identity header, left | `PLÁTCE POPLATKU`, then the payer name (bold 13 pt, wraps), then "IČO … · VS …" (the IČO is omitted when empty) | `legal_entity.name`, `ico`; `apartment.stay_fee_vs` |
| 2 | Identity header, right | `HLÁŠENÍ K MÍSTNÍMU` (quarterly: `ČTVRTLETNÍ HLÁŠENÍ K MÍSTNÍMU`), then **poplatku z pobytu**, then "za srpen 2026" / "za 3. čtvrtletí 2026" (nominative month) | computed |
| 3 | Recipient card (soft) | `PŘÍJEMCE · SPRÁVCE POPLATKU`, then the office name (bold), then the address and contact lines (the card grows with the text) | `apartment.stay_fee_authority_name` / `_address` / `_contact` |
| 3 | Period card (outlined) | `OBDOBÍ / VYHOTOVENO`: "1. 8. 2026 – 31. 8. 2026", then the download date | computed |
| — | Payer lines | the payer seat and contact e-mail, when set | `legal_entity.seat`, `contact_email` |
| 4 | Calculation table | `VÝPOČET ZA ZAŘÍZENÍ`: one row per property in the report group, with name + address, **LŮŽKODNY K POPLATKU**, **SAZBA**, **POPLATEK**. The header repeats on continuation pages | `stay_fee.hlaseni()` rows |
| 5 | Result | `SOUHRN`: "83 lůžkodnů podléhá poplatku" / "30 lůžkodnů osvobozeno" / "Lůžkoden = osoba × počet nocí". The soft total box **CELKEM K ODVODU NA ÚČET \<payee\>** (fallback "OBCI"), e.g. **4 150 Kč** | computed; `apartment.stay_fee_payee` |
| 6 | Exempt reasons | `OSVOBOZENÉ OSOBY`: aggregate rows only, "Mladší 18 let — 6 os. · 22 lůžkodnů" and "Osvobozeno ubytovatelem (důvod v evidenční knize) — …". **No names and no free-text reasons on the PDF** (those stay in the CSV) | computed |
| 7 | Confirmation | `ZA PLÁTCE`, "Datum: …", "Podpis, razítko / elektronické podání", with the signature image or typed name on the line. Then the office's sending instruction in small muted text | `legal_entity.signature_*`, `apartment.stay_fee_instruction` |
| 8 | Footer | UbyHost mark, **UbyHost**, "Vytvořeno v UbyHost", "Strana N" | fixed |

- **Zero period:** the table says "V tomto období nevznikla povinnost odvést poplatek." and the total is 0 Kč. The report is still produced.
- **Validation (in the renderer):**
  - It refuses a missing payer, recipient or VS.
  - It refuses a period that isn't one full calendar month (or one full calendar quarter for quarterly).
  - It refuses negative figures, or a row where nights × rate ≠ amount.
  - It refuses totals that don't match the rows, and exempt nights that don't match the reasons.

**Report object** (built by `stay_fee.hlaseni(group, issued_on)`):

```python
{
  "payer_name", "payer_seat", "payer_ico", "payer_contact", "vs",
  "recipient_name", "recipient_address", "recipient_contact",
  "payee", "instruction", "cadence": "monthly" | "quarterly",
  "period_start": "YYYY-MM-DD", "period_end": "YYYY-MM-DD", "issued_on": "YYYY-MM-DD",
  "rows": [{"property_name", "property_address", "liable_nights", "rate_czk", "amount_czk"}],
  "liable_nights": int, "exempt_nights": int, "total_czk": int,
  "not_charged": [{"reason": str, "count": int, "nights": int}],
  "signature_png": "data:image/...;base64,..." | "", "signature_name": str,
}
```

There are no free-number overrides. The figures are always the sum of the guest lines, so the PDF, the detail page and the CSV can never disagree. To change a figure, the host changes a guest's decision (§7).

---

## 2. Legal notes that shaped the design (zákon č. 565/1990 Sb.; sources in §16)

- **The poplatník** is a person **not registered** in that obec (§3, §16c). The **předmět** is a paid stay of **at most 60 consecutive calendar days** at one provider (§3a). A longer stay is *not subject*: a scope limit, not an exemption.
- **Base:** "počet započatých dnů pobytu, s výjimkou dne počátku pobytu" (§3c). The councils' form note "Lůžkoden = osoba × počet nocí" gives the same number: **nights**.
- **Allocation:** each **night** goes to the month (or quarter) of its date. A stay from 30 Aug to 3 Sep is 2 nights in August and 2 in September. Praha 1 instructs providers to assign days to the correct month.
- **Rate:** at most **50 Kč** (§3d), set by the obec's decree. The formula is base × rate (§3e).
- **Exempt (§3b):**
  - (1)(a) blind people, people dependent on another's care, ZTP/P holders and their companions;
  - (b) under 18;
  - (c) hospitalised (not spa);
  - (d) carers at children's camps;
  - (e) seasonal workers;
  - (f) certain institutional, social-services and rescue cases;
  - (2) security forces, soldiers or state employees on duty in state facilities.
  - Municipalities may add more (§14(3)(a)).
  - UbyHost computes **under 18** by itself. Everything else, including "registered in this obec", is the host's decision with a stated reason (§7).
- **Evidenční kniha (§3g):** stay start and end; name and address; date of birth; ID number and **type**; the fee **or** the reason for exemption. It is kept **6 years**. The CSV (§10) carries these columns. Guest records are already purged 6 years after checkout (`housebook.retention_cutoff`).
- **Ohlášení (§14a):** a one-time registration with the správce poplatku. **Not automated.**
- **Hlášení and payment:** the timing and form are per obec. Praha offices want the monthly hlášení by the 15th of the next month, sent by data box, post, e-mail with an electronic signature, or in person, **and** the payment to the council account with the assigned VS. Some obce use quarterly periods. The host picks the cadence per property. **A zero period still needs a hlášení** (Praha 3 guidance).
- **Penalties:** up to 500 000 Kč for breaching registration or record-keeping duties (daňový řád §247a). Late payment can be raised up to threefold (§11(3) zákona o místních poplatcích).
- **Future:** MMR's planned eTurista registry (~2027) may centralise this. Revisit then.

---

## 3. What already exists (verified at `cf5dd4e`)

| Existing | Where | Used for |
|---|---|---|
| Invoice section pattern | `routes/invoices.py` (own router, `_back`/`_flash`/`_form_str` from `admin_helpers`), `templates/invoices.html`, `invoice_detail.html`, `main.py` `include_router` | list + detail + downloads |
| **`payments.py`** (`normalise_account`, `format_iban`, `ascii_upper`, `spayd`, `qr_png_bytes`, `qr_data_uri`) + `tests/test_payments.py` | `App/app/payments.py` | council-account validation and QR Platba. **Do not rewrite** |
| Fonts DejaVu Sans + UbyHost mark | `App/app/static/fonts/`, `App/app/static/ubyhost-mark.png` | the PDF |
| CSV style (`;`, UTF-8 BOM) | `housebook.housebook_csv` | `stay_fee.register_csv` (already in the patch) |
| Signed-form check | `reporting.guest_has_signature` | who counts |
| Encrypted fields | `db.encrypt_field` / `db.decrypt_field` | the entity signature |
| Upload handling reference | `passport_photos.py` + the passport upload in `routes/guest.py` (read only, for the pattern) | the signature upload |
| Sidebar "Records" group | `templates/base.html` (`/submissions`, `/housebook`, `/invoices`) | new item after Invoices |
| Icons | `templates/_components.html::nav_icon` | new `coins` icon |
| Command palette | `routes/api.py` (`GET /api/command-palette`, the `nav.invoices` item) | new item |
| Property form | `templates/apartment_form.html` (section-nav; panel `#communication`; then `#calendars`), `routes/admin.py::_apartment_payload`, `_save_apartment_form`, `apartment_detail` | the fee panel |
| Host guest form | `templates/guest_form_admin.html` (the `doc_number` field), `routes/admin.py::_guest_payload` | `doc_type` |
| Entity form | `templates/entities.html` (create form `action="/entities"`, edit form `action="/entities/{id}"`), `routes/admin.py::create_entity` / `update_entity`, `_entity_details_payload` | signature |
| DSR export | `dsr.guest_export` exports every guest column | new guest columns covered automatically |

**Leftovers:** a database that ran the reverted 26 Sep build (commits `3178f93`…`97477f3`, reverted in `73762cf`) may already contain `guest.fee_host_decision`, `fee_host_reason`, `fee_claim`, `doc_type`, `reservation.stay_fee_*` and `apartment.stay_fee_rate_czk`. The core patch clears them once (§5.4).

---

## 4. Domain model (the fee decision)

For each signed guest and each period, `stay_fee.guest_period` returns exactly one status:

| Status | When | Liable nights | Exempt nights |
|---|---|---|---|
| **not_subject** | the whole stay is `nights + 1 > 60` (§3a). Checked **first**; no decision changes it | 0 | 0 (not reported at all) |
| **exempt** | host `exempt` (reason required), **or** under 18 on the arrival day with no host decision | 0 | nights in period |
| **liable** | otherwise, including host `charge` (corrects a wrong birth date) | nights in period | 0 |

A guest's decision applies to the whole stay, in every period it touches.

---

## 5. Database changes (in the core patch; listed for review)

Each column is in `SCHEMA` **and** `ADDED_COLUMNS`.

### 5.1 `apartment` — the per-property template

| Column | Declaration | Meaning |
|---|---|---|
| `stay_fee_rate_czk` | `INTEGER NOT NULL DEFAULT 0` | rate per person-night; 0 = off |
| `stay_fee_cadence` | `TEXT NOT NULL DEFAULT 'monthly'` | `monthly` / `quarterly` |
| `stay_fee_council_account` | `TEXT` | the council account as typed (Czech `prefix-number/bank` or IBAN) |
| `stay_fee_council_iban` | `TEXT` | derived by `payments.normalise_account` |
| `stay_fee_vs` | `TEXT` | the council-assigned variabilní symbol; digits only, ≤ 10 |
| `stay_fee_authority_name` | `TEXT` | the office name, can be multi-line |
| `stay_fee_authority_address` | `TEXT` | the office department + address, can be multi-line |
| `stay_fee_authority_contact` | `TEXT` | the contact line (tel · e-mail · č. účtu), can be multi-line |
| `stay_fee_payee` | `TEXT` | "na účet …" text, e.g. `MČ Praha 3`, `města Brna`; empty → "obce" |
| `stay_fee_instruction` | `TEXT` | the office's sending instruction printed in the footer; optional |

### 5.2 `legal_entity` — the signature

| Column | Declaration | Meaning |
|---|---|---|
| `signature_png_enc` | `TEXT` | `db.encrypt_field(<data:image/png|jpeg;base64,…>)` |
| `signature_name` | `TEXT` | typed-name fallback |

### 5.3 `guest`

| Column | Declaration | Meaning |
|---|---|---|
| `doc_type` | `TEXT` | one of `validation.DOC_TYPES`; NULL = derive |
| `fee_host_decision` | `TEXT` | NULL / `exempt` / `charge` |
| `fee_host_reason` | `TEXT` | ≤ 120 characters, required for `exempt` |

### 5.4 One-time reset

`db._reset_reverted_stay_fee(conn)` runs from `init_db` once (settings key `stay_fee_remittance_reset_done`). It:

- sets every `apartment.stay_fee_rate_czk = 0`;
- sets `guest.doc_type`, `fee_host_decision` and `fee_host_reason` to NULL;
- NULLs the reverted build's leftover columns (`guest.fee_claim`, `reservation.stay_fee_rate_czk`, `stay_fee_paid_at`, `stay_fee_paid_amount_czk`, `apartment.stay_fee_payment_link`) **if they exist**.

After that it never runs again.

`validation.py` gains `DOC_TYPES` (9 codes) and `age_on(birth, when)`. No new tables. Nothing about periods is stored: every figure is computed on demand.

---

## 6. Calculation core — `App/app/stay_fee.py` (in the core patch)

**Public API** (tested in `tests/test_stay_fee.py`, 40 tests):

| Function | Returns |
|---|---|
| `is_active(apartment)`, `clamp_rate(raw)`, `cadence_of(apartment)` | helpers |
| `default_doc_type(nationality)`, `doc_type_of(guest)` | `op` / `pas` / the stored code |
| `parse_month("YYYY-MM") -> date|None`, `month_key(d)`, `shift_month(d, n)`, `previous_month(today)` | month maths |
| `period_bounds(cadence, month) -> (first, last)` | the monthly or quarterly period containing `month` |
| `period_label_cs(cadence, month)` | `"Srpen 2026"` / `"3. čtvrtletí 2026"` |
| `period_complete(cadence, month, today)` | `last < today` |
| `nights_in(start, end, first, last)` | nights with `start ≤ n < end` inside the period |
| `guest_period(guest, reservation, first, last)` | `{guest_id, stay_from, stay_to, nights, liable_nights, exempt_nights, status, auto_minor, decision, reason}` or None |
| `property_period(apartment, month)` | `{apartment, cadence, first, last, label, rate_czk, lines[], liable_nights, exempt_nights, total_czk}`. Each line also has `reservation_id`, `name`, `restricted`, `amount_czk` |
| `owner_periods(owner_user_id, month)` | the list page's rows (properties with rate > 0, not archived) |
| `vs_of(apartment)` | the VS, digits only |
| `report_group(apartment, month)` | the hlášení the property belongs to: `{anchor, vs, cadence, first, last, label, periods[], liable_nights, exempt_nights, total_czk}` |
| `report_issues(group, today)` | blocking keys: `stay_fees.issue.period_running`, `.no_vs`, `.no_authority`, `.no_payer` |
| `payment_details(group)` | `{account, iban, iban_display, vs, spayd, qr}`, or None without a council IBAN |
| `property_address(apartment)` | "Slezská 12, 13000 Praha 3" |
| `hlaseni(group, issued_on)` | the report object `stay_fee_remittance_pdf.render` takes (§1) |
| `register_rows(period)`, `register_csv(rows)`, `REGISTER_COLUMNS` | the §3g CSV |

**Worked examples** (rate 50; all in the test file):

| # | Stay | Birth | Decision | Period | Result |
|---|---|---|---|---|---|
| E1 | 10.–14. 9. | adult | — | Sep | 4 liable, 200 Kč |
| E2 | 10.–14. 9. | 17 on arrival | — | Sep | 4 exempt |
| E3 | 10.–14. 9. | 18 on arrival | — | Sep | 4 liable |
| E4 | 30. 8.–3. 9. | adult | — | Aug / Sep | 2 / 2 liable |
| E5 | 1. 8.–29. 9. (59 nights) | adult | — | Sep | 28 liable |
| E6 | 1. 8.–30. 9. (60 nights = 61 days) | adult | any | Sep | not subject (0/0) |
| E7 | 10.–14. 9. | adult | `exempt` "ZTP/P" | Sep | 4 exempt |
| E8 | 10.–14. 9. | 17 on arrival | `charge` | Sep | 4 liable |
| E9 | quarterly, 10.–12. 7. + 28. 9.–2. 10. | adult | — | Q3 | 2 + 3 = 5 liable |

---

## 7. Exemptions are host-only, on the stay-fee detail page

There is no guest input. On `/stay-fees/{apartment_id}?month=…`, the **guest list** shows every counted line: name (links to `/reservations/{reservation_id}`), dates, nights in the period, status, amount. Each row has a small decision form:

```html
<form method="post" action="/stay-fees/guest-decision" class="fee-decision">
  <input type="hidden" name="_csrf" value="{{ csrf_token }}">
  <input type="hidden" name="guest_id" value="{{ line.guest_id }}">
  <input type="hidden" name="apartment_id" value="{{ apartment.id }}">
  <input type="hidden" name="month" value="{{ month }}">
  <input type="text" name="reason" maxlength="120" value="{{ line.reason }}"
         placeholder="{{ t('stay_fees.decision.reason_placeholder') }}"
         aria-label="{{ t('stay_fees.decision.reason_label') }}">
  <button class="btn small" type="submit" name="decision" value="exempt">{{ t('stay_fees.decision.exempt') }}</button>
  <button class="btn small" type="submit" name="decision" value="charge">{{ t('stay_fees.decision.charge') }}</button>
  {% if line.decision %}<button class="btn small" type="submit" name="decision" value="">{{ t('stay_fees.decision.auto') }}</button>{% endif %}
</form>
```

- *Exempt* comes first, so Enter in the reason field submits *Exempt*.
- The form is inside a closed `<details>` (summary `stay_fees.decision.change`) except for rows that need review: **under 18 (automatic)** and **local-resident hint** rows are open.
- `not_subject` rows show `stay_fees.status.not_subject` and no form.
- **Local-resident hint:** show `stay_fees.hint.local_resident` in muted text when the guest's `res_country` is CZE and their `res_city` (casefolded, diacritics stripped) equals the property's `addr_obec`, compared the same way. It never changes the figures by itself.
- `POST /stay-fees/guest-decision`, handler `stay_fee_guest_decision`:
  - `guard` first. `guest = access.guest(request, guest_id)`; if missing → `err flash.error.no_such_guest`.
  - `decision` not in (`""`, `exempt`, `charge`) → treat as `""`. `reason = _form_str(form, "reason")[:120].strip()`.
  - `exempt` with `len(reason) < 3` → `err flash.stay_fees.reason_required`.
  - `db.update("guest", guest_id, {"fee_host_decision": decision or None, "fee_host_reason": (reason if decision == "exempt" else None), "updated_at": db.utcnow()})`.
  - `db.audit("stay_fee_decision", f"guest_id={guest_id} decision={decision or 'auto'}")`. **Do not put the reason in the audit row** (data minimisation).
  - Redirect to `/stay-fees/{apartment_id}?month={month}#guests` with `msg flash.stay_fees.saved`. Validate `apartment_id` through `access.apartment`; if that fails, fall back to `/stay-fees`.

---

## 8. Template, on-demand PDF, signature

### 8.1 The template is filled once

The property fields (§5.1) and the entity (`name`, signature) are entered once. Each period is automatic.

### 8.2 The PDF is rendered on demand

`GET /stay-fees/{apartment_id}/pdf?month=YYYY-MM`:

1. `guard`; `apartment = access.apartment(...)`; missing or rate 0 → `err flash.error.no_such_apartment` to `/stay-fees`.
2. `month = stay_fee.parse_month(...)`, else the default month (§9.1).
3. `group = stay_fee.report_group(apartment, month)`; `issues = stay_fee.report_issues(group, claim.prague_today())`. If there are issues, redirect to the detail page with `err flash.stay_fees.report_blocked`.
4. `pdf = stay_fee_remittance_pdf.render(stay_fee.hlaseni(group, claim.prague_today()))`. On `ValueError`, same redirect.
5. `db.audit("stay_fee_pdf", f"apartment_id={apartment['id']} period={key} total={group['total_czk']}")`.
6. `Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="hlaseni-poplatek-z-pobytu-{key}-{group["vs"]}.pdf"'})`. `key` is `YYYY-MM`, or `YYYY-Qn` for quarterly.

Nothing is stored. A re-download recomputes from current data.

### 8.3 Signature, entity-level

In `entities.html`, add a signature block to **both** the create and the edit form, after the contact fields:

- A file input `signature_file` (`accept="image/png,image/jpeg"`), a checkbox `signature_remove`, and a text input `signature_name` (maxlength 80).
- The two forms get `enctype="multipart/form-data"`.
- When a signature is stored, show a small preview (`<img>` of the decrypted data URI, max-height 48 px) plus the remove checkbox.

In `routes/admin.py`, add `_signature_payload(form) -> Optional[dict]` and call it from `create_entity` / `update_entity` after `_entity_details_payload`:

- Read `form.get("signature_file")`. If it's an `UploadFile` with a filename, read at most **300 KB + 1**. More than 300 KB or not PNG/JPEG (check the magic bytes `\x89PNG` / `\xff\xd8\xff`) → `err flash.entities.signature_invalid`, nothing saved. Otherwise `payload["signature_png_enc"] = db.encrypt_field(f"data:image/{png|jpeg};base64,{b64}")`.
- `signature_remove` ticked → `payload["signature_png_enc"] = None`.
- `"signature_name" in form` → `payload["signature_name"] = _form_str(form, "signature_name")[:80].strip() or None`.

The PDF uses the image when present, else the typed name, else nothing.

---

## 9. Routes and screens (mirror the invoice section)

New `App/app/routes/stay_fees.py`, `router = APIRouter(dependencies=[Depends(security.protect_host_post)])`, included in `main.py` directly after `invoices.router`.

### 9.1 Routes

| Method + path | Handler | Purpose |
|---|---|---|
| `GET /stay-fees?month=YYYY-MM` | `stay_fees_list` | list page (§9.2) |
| `GET /stay-fees/{apartment_id}?month=YYYY-MM` | `stay_fee_detail` | detail page (§9.6) |
| `GET /stay-fees/{apartment_id}/pdf?month=YYYY-MM` | `stay_fee_pdf_download` | §8.2 |
| `GET /stay-fees/{apartment_id}/csv?month=YYYY-MM` | `stay_fee_csv_download` | §10 |
| `POST /stay-fees/guest-decision` | `stay_fee_guest_decision` | §7 |

**Default month:** the previous calendar month (`stay_fee.previous_month(claim.prague_today())`). A `month` after the current month redirects to the default. For a quarterly property, any month selects its quarter.

### 9.2 List page (`templates/stay_fees.html`, match `stay-fees-list.jpg`)

- `{% extends "base.html" %}{% set nav = 'stay_fees' %}`. `page_header(t('stay_fees.title'), t('stay_fees.lede'), eyebrow=t('nav.records'), actions=<chips>)`.
- **Chips:** the current month and the two before it, e.g. `Červenec 2026 · Srpen 2026 · Září 2026`, as `<a class="chip{{ ' on' if selected }}" href="?month=…">`, labelled with `t('month.N') ~ ' ' ~ year`. Before them, one `<a class="chip" href="?month=<3 months earlier>">&larr;</a>` for older months. Selected = the requested month.
- **Table** (`panel tight` + `table-cards`), columns: `stay_fees.col.property`, `.period`, `.liable`, `.exempt`, `.total`, and an empty action column. One `clickable-row` per `owner_periods` entry, with `data-href="/stay-fees/{id}?month=…"`:
  - property cell: `row-primary-link` name + `small muted` "`{addr_obec}` · `t('stay_fees.rate_line', rate=…)`";
  - period cell: for monthly, the chosen month's label (`t('month.N')` + year); for quarterly, `t('stay_fees.quarter', n=…, year=…)`;
  - the numbers in `num` cells, the total bold;
  - the action cell: `<span class="pill blue">{{ t('stay_fees.open') }}</span>`, or `pill amber` `stay_fees.needs_setup` when `report_issues` has anything other than `period_running`.
- The footnote `stay_fees.footnote` (small muted).
- **Empty state** (no property with rate > 0): `panel empty` with `stay_fees.empty_title`, `stay_fees.empty`, and `<a class="btn" href="/apartments">{{ t('stay_fees.empty_action') }}</a>`. No coral button on this page.

### 9.3 Sidebar, icon, palette

- `base.html`, after the `/invoices` link: `<a href="/stay-fees" class="{{ 'active' if nav == 'stay_fees' }}">{{ nav_icon('coins') }}{{ t('nav.stay_fees') }}</a>`
- `_components.html::nav_icon`, before `{% endif %}`:

```html
  {% elif name == 'coins' %}
    <svg class="nav-icon" viewBox="0 0 20 20" fill="none" aria-hidden="true"><circle cx="8" cy="8.5" r="4.75" stroke="currentColor" stroke-width="1.5"/><path d="M11.6 6.1a4.75 4.75 0 1 1-2.1 9.2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
```

- `routes/api.py`, after the `nav.invoices` item: `{"label": t("nav.stay_fees"), "group": t("command.group.pages"), "url": "/stay-fees", "keywords": "poplatek z pobytu hlaseni city tax"},`

### 9.4 Property panel `#stay-fee-settings` (`apartment_form.html`, edit mode only)

- Section-nav: in the `{% if editing %}` branch, add `<a href="#stay-fee-settings">{{ t('apartment.form.nav.stay_fee') }}</a>` **between** the `#communication` and `#calendars` links.
- The panel `<div class="panel" id="stay-fee-settings">` goes **inside the `<form>`**, directly after the closing `</div>` of `<div class="panel" id="communication">` and before the Notes panel (`<h2 …>{{ t('apartment.form.notes.title') }}</h2>`). **Not** next to `#calendars`: that heading sits *after* `</form>`, so fields placed there would never be saved.
- It has `h2 apartment.form.stay_fee.heading` and the lede `apartment.form.stay_fee.lede`, then the fields in this order. Each is a `.field`, with label and hint keys from §12.2:

| Name | Input |
|---|---|
| `stay_fee_rate_czk` | `number` 0–50 step 1 |
| `stay_fee_cadence` | select `monthly` / `quarterly` |
| `stay_fee_vs` | text, `inputmode="numeric"`, maxlength 10 |
| `stay_fee_council_account` | text, maxlength 40 |
| `stay_fee_authority_name` | textarea, 2 rows, maxlength 200 |
| `stay_fee_authority_address` | textarea, 2 rows, maxlength 200 |
| `stay_fee_authority_contact` | textarea, 2 rows, maxlength 200 |
| `stay_fee_payee` | text, maxlength 60 |
| `stay_fee_instruction` | textarea, 3 rows, maxlength 500 |

- **Warning:** when rate > 0 and any of VS, account or authority name is empty, show `<p class="small warn-text">{{ t('apartment.form.stay_fee.missing_warn') }}</p>`.
- When rate > 0, add a link `<a href="/stay-fees/{{ apartment.id }}">{{ t('apartment.form.stay_fee.open_overview') }} &rarr;</a>`.
- **Copy from another property:** exactly v1's markup and behaviour (keys `apartment.form.stay_fee.copy_label` / `copy_button` / `copy_hint`), with two extra `data-payee` and `data-instruction` attributes and fields. The context key is `fee_template_peers`: the host's **other** non-archived properties with rate > 0, from `access.apartments(request)`. The JS handler goes in `static/app.js` on `#fee-copy-apply`. It only fills inputs; **Save changes** persists.
- Saved by the page's existing **Save changes**; no second submit.

**`routes/admin.py::_apartment_payload`**, directly after the passport-policy lines:

```python
if "stay_fee_rate_czk" in form:
    payload["stay_fee_rate_czk"] = stay_fee.clamp_rate(_form_str(form, "stay_fee_rate_czk", "0"))
    cadence = _form_str(form, "stay_fee_cadence", "monthly")
    payload["stay_fee_cadence"] = cadence if cadence in stay_fee.CADENCES else "monthly"
    payload["stay_fee_vs"] = "".join(ch for ch in _form_str(form, "stay_fee_vs") if ch.isdigit())[:10] or None
    for key, limit in (("stay_fee_authority_name", 200), ("stay_fee_authority_address", 200),
                       ("stay_fee_authority_contact", 200), ("stay_fee_payee", 60),
                       ("stay_fee_instruction", 500)):
        payload[key] = _form_str(form, key)[:limit].strip() or None
    payload["_stay_fee_account_raw"] = _form_str(form, "stay_fee_council_account")
```

**`_save_apartment_form`**: before the `db.update("apartment", apartment_id, payload)` line:

```python
raw_account = payload.pop("_stay_fee_account_raw", None)
if raw_account is not None:
    if raw_account.strip():
        try:
            payload["stay_fee_council_account"], payload["stay_fee_council_iban"] = (
                payments.normalise_account(raw_account))
        except ValueError:
            return _back(f"/apartments/{apartment_id}#stay-fee-settings",
                         err=_flash(request, "flash.stay_fees.account_invalid"))
    else:
        payload["stay_fee_council_account"] = payload["stay_fee_council_iban"] = None
```

The create route (`apartment_create`) must also `payload.pop("_stay_fee_account_raw", None)`, although the create form never posts the fields. Add `stay_fee` to the `from .. import (...)` block (`payments` and `claim` are already imported).

### 9.5 Host guest form: document type

Add a select `doc_type` directly above `doc_number` in `guest_form_admin.html`, copying the `nationality` field's markup:

- Options come from the `doc_types` context (`validation.DOC_TYPES`), labelled `t('guest.doc_type.' ~ code)`.
- Preselect the stored value, else `op` for a CZE guest, else `pas`.
- Pass `doc_types` in every render of that template, including the 422 paths (`grep -n guest_form_admin.html App/app/routes/*.py`).
- In `_guest_payload`: `doc_type = _form_str(form, "doc_type"); payload["doc_type"] = doc_type if doc_type in validation.DOC_TYPES else None`.
- The guest's own form is not touched.

### 9.6 Detail page (`templates/stay_fee_detail.html`, match `stay-fees-detail.jpg`)

Context: `apartment`, `month`, `period = property_period(apartment, month)`, `group = report_group(...)`, `issues = report_issues(group, today)`, `pay = payment_details(group)`, `others` (the other `group.periods` names), and `key`.

1. `<a class="back-link" href="/stay-fees?month=…">&larr; {{ t('stay_fees.back') }}</a>`.
2. `page_header`:
   - eyebrow `nav.stay_fees`; h1 `{{ apartment.internal_name }} — {{ period label }}`; lede `stay_fees.detail_lede`.
   - Actions: `<a class="btn" href="…/csv?month=…">{{ t('stay_fees.download_csv') }}</a>`, then **either** `<a class="btn accent primary" href="…/pdf?month=…">{{ t('stay_fees.download_pdf') }}</a>` (no issues) **or** `<button class="btn" disabled>{{ t('stay_fees.download_pdf') }}</button>`.
3. **Issues:** one `<p class="warn-text small">` per key, with a link to `/apartments/{id}#stay-fee-settings` (vs / authority) or `/entities` (payer). `period_running` has no link.
4. **Group note** when `others`: `<p class="small muted">{{ t('stay_fees.group_note', names=', '.join(others)) }}</p>`. The metrics and PDF are the **group's**; the guest list below is **this property's**.
5. **Metrics** (`stay-metrics detail-hero`, four `detail-metric`):
   - `stay_fees.metric.liable` = `group.liable_nights`
   - `stay_fees.metric.exempt` = `group.exempt_nights`
   - `stay_fees.metric.total` = `format_czk(group.total_czk)`
   - `stay_fees.metric.vs` = `group.vs or '—'`
6. **Payment** (`<section id="payment">`): `h2 stay_fees.payment.title` + pill.
   - The pill is `green stay_fees.payment.ready` when `pay and pay.qr`, otherwise `amber stay_fees.payment.incomplete`.
   - When `pay`, three `.copyrow`s (readonly `mono` input + `copy_button(id)` macro, as `apartment_form.html` uses): council account, IBAN (`pay.iban`, no spaces), VS. Hint `stay_fees.payment.vs_hint`.
   - Then, when `pay.qr`, a QR block: `<img src="{{ pay.qr }}" width="176" height="176" alt="{{ t('stay_fees.payment.qr_alt') }}">`, heading `QR Platba`, text `stay_fees.payment.qr_help` (amount, formatted), and `pay.spayd` in muted mono.
   - The footnote is `stay_fees.payment.footnote`. The payment panel **never** appears on the PDF.
7. **Guests** (`<section id="guests">`): `h2 stay_fees.guests.title` and a list per §7, or `stay_fees.guests.empty`.

CSS to append to `static/app.css`:

```css
.fee-lines { list-style: none; margin: 8px 0 0; padding: 0; }
.fee-line { display: flex; flex-wrap: wrap; gap: 6px 14px; align-items: baseline; padding: 12px 0; border-top: 1px solid var(--line); }
.fee-line:first-child { border-top: 0; }
.fee-line .fee-amount { margin-left: auto; font-weight: 600; font-variant-numeric: tabular-nums; }
.fee-decision { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.fee-decision input[type="text"] { flex: 1 1 220px; }
.fee-qr { display: flex; gap: 16px; align-items: flex-start; margin-top: 14px; }
.fee-qr img { border: 1px solid var(--line); border-radius: 8px; background: #fff; }
```

---

## 10. CSV export (the evidenční kniha)

`GET /stay-fees/{apartment_id}/csv?month=…`:

- `guard`, then `access.apartment`.
- `rows = stay_fee.register_rows(stay_fee.property_period(apartment, month))`.
- `db.audit("stay_fee_csv", f"apartment_id=… period=… rows=…")`.
- `Response(stay_fee.register_csv(rows), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="evidencni-kniha-{key}-{apartment_id}.csv"'})`.
- Allowed for a running period.

The columns (`REGISTER_COLUMNS`, already in the patch) are: Zařízení · Období · Den počátku pobytu · Den konce pobytu · Příjmení · Jméno · Adresa místa přihlášení / v zahraničí · Datum narození · Druh průkazu · Číslo průkazu · Nocí v období · Sazba (Kč) · Poplatek (Kč) · Důvod osvobození · Variabilní symbol · Účet obce.

- Under-18 rows get "mladší 18 let". Not-subject rows get "pobyt delší než 60 dnů (není předmětem poplatku)".
- A doc number of `INPASS` → "zapsán v dokladu rodiče".
- Restricted guests (Art. 18): the name and identity columns are blank and `Příjmení` = "zpracování omezeno (čl. 18 GDPR)".
- The host keeps the CSV for 6 years (§3g(4)).

---

## 11. Owner decisions

| Date | Decision |
|---|---|
| 29 Sep | Copy from another property: yes. Signature: entity-level only. Cadence: monthly + quarterly per property. Tracking: none. ZTP/P and local-resident proof: host responsibility |
| 30 Sep | **No stay-page panel**; decisions live on the stay-fee detail page |
| 30 Sep | **Nights are split by period** (the night's date) |
| 30 Sep | **One hlášení per legal entity + VS + cadence** |
| 30 Sep | **60 days = calendar days** (`nights + 1 > 60` → not subject) |
| 30 Sep | Host-facing QR Platba for paying the council: yes. Guests never see a fee |
| 30 Sep | Document type: derived automatically, editable on the host guest form |

---

## 12. i18n keys (host UI; EN/CS parity-tested)

Put page, nav and flash keys in `host_i18n.STRINGS`: nav keys next to `nav.invoices`, flash keys next to `flash.entities.saved`. Put form keys in `host_i18n._INTERFACE_STRINGS`, after `apartment.form.passport_policy.*`. Counted keys ship bare/`.one`/`.few` and are used via `tp()`.

### 12.1 Section, list, detail, flash (`STRINGS`)

| Key | EN | CS |
|---|---|---|
| `nav.stay_fees` | Stay fee | Poplatek z pobytu |
| `stay_fees.title` | Stay fee | Poplatek z pobytu |
| `stay_fees.lede` | What each property owes the municipality per period. Open a property for the report, the payment details and the QR. | Kolik která nemovitost odvádí obci za období. Otevřete nemovitost pro hlášení, platební údaje a QR kód. |
| `stay_fees.col.property` | Property | Nemovitost |
| `stay_fees.col.period` | Period | Období |
| `stay_fees.col.liable` | Liable bed-days | Lůžkodny podléhající |
| `stay_fees.col.exempt` | Exempt | Osvobozené |
| `stay_fees.col.total` | Total | Celkem |
| `stay_fees.rate_line` | rate %(rate)s Kč | sazba %(rate)s Kč |
| `stay_fees.quarter` | Q%(n)s %(year)s | %(n)s. čtvrtletí %(year)s |
| `stay_fees.open` | Open | Zobrazit |
| `stay_fees.needs_setup` | Needs setup | Doplnit údaje |
| `stay_fees.footnote` | Only properties with a rate appear here. Set a rate on a property to enable the stay fee — it is optional and never part of onboarding. | Zobrazují se jen nemovitosti se zadanou sazbou. Poplatek zapnete zadáním sazby u nemovitosti — je volitelný a není součástí úvodního nastavení. |
| `stay_fees.empty_title` | No property has a stay fee yet | Žádná nemovitost zatím nemá poplatek z pobytu |
| `stay_fees.empty` | Set a rate in a property's Stay fee section to see the totals here. | Zadejte sazbu v sekci Poplatek z pobytu u nemovitosti a součty se zobrazí zde. |
| `stay_fees.empty_action` | Open properties | Otevřít nemovitosti |
| `stay_fees.back` | Back to overview | Zpět na přehled |
| `stay_fees.detail_lede` | The report for the council. Download the PDF for the office, or pay directly with the QR. | Hlášení k místnímu poplatku z pobytu. Stáhněte PDF pro úřad, nebo zaplaťte přímo přes QR. |
| `stay_fees.download_pdf` | Download PDF | Stáhnout PDF |
| `stay_fees.download_csv` | Download CSV | Stáhnout CSV |
| `stay_fees.group_note` | This report also includes %(names)s (same legal entity and variable symbol). The guest list below is this property only. | Toto hlášení zahrnuje i %(names)s (stejný subjekt a variabilní symbol). Seznam hostů níže je jen pro tuto nemovitost. |
| `stay_fees.metric.liable` | Liable bed-days | Lůžkodny podléhající poplatku |
| `stay_fees.metric.exempt` | Exempt bed-days | Osvobozené lůžkodny |
| `stay_fees.metric.total` | Total | Celková částka |
| `stay_fees.metric.vs` | Variable symbol | Variabilní symbol |
| `stay_fees.payment.title` | Payment to the council | Platba úřadu |
| `stay_fees.payment.ready` | Ready to pay | Připraveno k zaplacení |
| `stay_fees.payment.incomplete` | Payment details missing | Chybí platební údaje |
| `stay_fees.payment.account` | Council account | Číslo účtu úřadu |
| `stay_fees.payment.iban` | IBAN | IBAN |
| `stay_fees.payment.vs` | Variable symbol | Variabilní symbol |
| `stay_fees.payment.vs_hint` | The council assigned this symbol to you. Include it with the payment. | Tento symbol vám přidělil úřad. Uveďte ho v platbě. |
| `stay_fees.payment.qr_alt` | QR code for paying the stay fee to the council | QR kód pro zaplacení poplatku úřadu |
| `stay_fees.payment.qr_help` | Scan it in your banking app and pay %(amount)s to the council. It carries the amount, the account and the variable symbol. | Naskenujte v bankovní aplikaci a zaplaťte %(amount)s na účet úřadu. QR kód obsahuje částku, účet i variabilní symbol. |
| `stay_fees.payment.footnote` | You enter these payment details yourself (council account and variable symbol). They are not part of the report — they are only for paying. | Tyto platební údaje zadáváte sami (účet úřadu a variabilní symbol). Nejsou součástí hlášení pro úřad — slouží jen k zaplacení. |
| `stay_fees.guests.title` | Guests in this period | Hosté v tomto období |
| `stay_fees.guests.empty` | No signed guest stayed in this period. The report is still due, with zero. | V tomto období nebyl žádný podepsaný host. Hlášení je přesto nutné podat, s nulou. |
| `stay_fees.nights` | %(count)s nights | %(count)s nocí |
| `stay_fees.nights.one` | %(count)s night | %(count)s noc |
| `stay_fees.nights.few` | %(count)s nights | %(count)s noci |
| `stay_fees.status.liable` | Liable | Podléhá |
| `stay_fees.status.exempt` | Exempt | Osvobozen/a |
| `stay_fees.status.under_18` | Exempt — under 18 | Osvobozen/a — mladší 18 let |
| `stay_fees.status.not_subject` | Stay over 60 days — not subject | Pobyt nad 60 dnů — nepodléhá |
| `stay_fees.decision.change` | Change | Změnit |
| `stay_fees.decision.exempt` | Exempt | Osvobodit |
| `stay_fees.decision.charge` | Charge | Zpoplatnit |
| `stay_fees.decision.auto` | Automatic | Automaticky |
| `stay_fees.decision.reason_label` | Reason (required to exempt) | Důvod (povinný pro osvobození) |
| `stay_fees.decision.reason_placeholder` | e.g. ZTP/P card checked; registered in this municipality | např. ověřen průkaz ZTP/P; trvalý pobyt v obci |
| `stay_fees.hint.local_resident` | The guest's declared city matches this property's municipality. Check their registration on their ID before exempting. | Obec uvedená hostem odpovídá obci nemovitosti. Před osvobozením ověřte trvalý pobyt v dokladu. |
| `stay_fees.issue.period_running` | This period is not over yet. The PDF is available from the day after it ends. | Toto období ještě neskončilo. PDF bude k dispozici den po jeho skončení. |
| `stay_fees.issue.no_vs` | Add the variable symbol the council gave you. | Doplňte variabilní symbol, který vám přidělil úřad. |
| `stay_fees.issue.no_authority` | Add the council office name. | Doplňte název úřadu. |
| `stay_fees.issue.no_payer` | The property needs a legal entity with a name. | Nemovitost potřebuje subjekt s názvem. |
| `flash.stay_fees.saved` | Saved. | Uloženo. |
| `flash.stay_fees.reason_required` | Give a reason when you exempt a guest. | Při osvobození hosta uveďte důvod. |
| `flash.stay_fees.report_blocked` | The report can't be created yet. Fix the items shown on the page. | Hlášení zatím nelze vytvořit. Doplňte údaje uvedené na stránce. |
| `flash.stay_fees.account_invalid` | That council account number is not valid. Nothing was saved. | Číslo účtu obce není platné. Nic nebylo uloženo. |
| `flash.entities.signature_invalid` | The signature must be a PNG or JPEG image up to 300 KB. | Podpis musí být obrázek PNG nebo JPEG do 300 KB. |
| `month.1` … `month.12` | January … December | Leden … Prosinec |

(`month.N` is 12 keys. EN: January, February, March, April, May, June, July, August, September, October, November, December. CS: Leden, Únor, Březen, Duben, Květen, Červen, Červenec, Srpen, Září, Říjen, Listopad, Prosinec. None exist at `cf5dd4e`.)

### 12.2 Property panel, entity form, host guest form (`_INTERFACE_STRINGS`)

| Key | EN | CS |
|---|---|---|
| `apartment.form.nav.stay_fee` | Stay fee | Poplatek z pobytu |
| `apartment.form.stay_fee.heading` | Stay fee (poplatek z pobytu) | Poplatek z pobytu |
| `apartment.form.stay_fee.lede` | Optional. Only for your report and payment to the municipality — guests never see it. | Volitelné. Jen pro vaše hlášení a platbu obci — hosté ho nikdy neuvidí. |
| `apartment.form.stay_fee.rate_label` | Rate per person per night (Kč) | Sazba za osobu a noc (Kč) |
| `apartment.form.stay_fee.rate_hint` | From your municipality's decree (max 50 Kč). 0 turns the stay fee off. | Podle vyhlášky vaší obce (max. 50 Kč). 0 poplatek vypne. |
| `apartment.form.stay_fee.cadence_label` | Reporting period | Období hlášení |
| `apartment.form.stay_fee.cadence.monthly` | Monthly | Měsíčně |
| `apartment.form.stay_fee.cadence.quarterly` | Quarterly | Čtvrtletně |
| `apartment.form.stay_fee.vs_label` | Variable symbol (from the council) | Variabilní symbol (od obce) |
| `apartment.form.stay_fee.vs_hint` | Up to 10 digits. Properties with the same legal entity and symbol share one report. | Až 10 číslic. Nemovitosti se stejným subjektem a symbolem mají jedno společné hlášení. |
| `apartment.form.stay_fee.account_label` | Council account | Účet obce |
| `apartment.form.stay_fee.account_hint` | Czech format (prefix-number/bank code) or IBAN. Used for the payment QR. | Český formát (předčíslí-číslo/kód banky) nebo IBAN. Použije se pro platební QR kód. |
| `apartment.form.stay_fee.authority_name_label` | Council office name | Název úřadu |
| `apartment.form.stay_fee.authority_address_label` | Office department and address | Odbor a adresa úřadu |
| `apartment.form.stay_fee.authority_contact_label` | Office contact line (tel, e-mail, account) | Kontaktní údaje úřadu (tel., e-mail, účet) |
| `apartment.form.stay_fee.payee_label` | "Paid to the account of …" | „Odváděná na účet …“ |
| `apartment.form.stay_fee.payee_hint` | As printed on the report, e.g. "MČ Praha 3" or "města Brna". Empty prints "obce". | Jak se vytiskne na hlášení, např. „MČ Praha 3“ nebo „města Brna“. Prázdné = „obce“. |
| `apartment.form.stay_fee.instruction_label` | How to send the report (optional) | Jak hlášení odeslat (nepovinné) |
| `apartment.form.stay_fee.instruction_hint` | Your office's instruction, printed at the foot of the report. | Pokyn vašeho úřadu, vytiskne se v zápatí hlášení. |
| `apartment.form.stay_fee.missing_warn` | Add the variable symbol, the council account and the office name to create the report and the payment QR. | Pro vytvoření hlášení a platebního QR kódu doplňte variabilní symbol, účet obce a název úřadu. |
| `apartment.form.stay_fee.open_overview` | Open this property's stay fee | Otevřít poplatek této nemovitosti |
| `apartment.form.stay_fee.copy_label` | Copy from another property | Zkopírovat z jiné nemovitosti |
| `apartment.form.stay_fee.copy_button` | Copy | Zkopírovat |
| `apartment.form.stay_fee.copy_hint` | Fills the fields below. Nothing is saved until you press Save changes. | Vyplní pole níže. Uloží se až po stisknutí Uložit změny. |
| `entity.signature_label` | Signature for reports (PNG or JPEG, max 300 KB) | Podpis na hlášení (PNG nebo JPEG, max. 300 KB) |
| `entity.signature_remove` | Remove the stored signature | Odstranit uložený podpis |
| `entity.signature_name_label` | Typed name (used when there is no image) | Jméno (použije se, když chybí obrázek) |
| `guest.doc_type.label` | Document type | Druh dokladu |
| `guest.doc_type.hint` | For the stay-fee register. Set from nationality; change it if the guest used another document. | Pro evidenční knihu poplatku. Nastaví se podle státní příslušnosti; změňte, pokud host použil jiný doklad. |
| `guest.doc_type.op` | National ID card | Občanský průkaz |
| `guest.doc_type.pas` | Passport | Cestovní pas |
| `guest.doc_type.prechodny_pobyt` | Certificate of temporary residence | Potvrzení o přechodném pobytu |
| `guest.doc_type.pobytova_karta_eu` | Residence card of an EU citizen's family member | Pobytová karta rodinného příslušníka občana EU |
| `guest.doc_type.povoleni_pobyt` | Residence permit | Průkaz o povolení k pobytu |
| `guest.doc_type.povoleni_pobyt_cizinec` | Residence permit for a foreign national | Průkaz o povolení k pobytu pro cizince |
| `guest.doc_type.trvaly_pobyt` | Permanent residence permit | Průkaz o povolení k trvalému pobytu |
| `guest.doc_type.zadatel_mezinarodni_ochrana` | International protection applicant card | Průkaz žadatele o mezinárodní ochranu |
| `guest.doc_type.zadatel_docasna_ochrana` | Temporary protection applicant card | Průkaz žadatele o dočasnou ochranu |

---

## 13. Implementation order (one PR each; tests green after each)

| # | Branch | Do | Tests (new file) / done when |
|---|---|---|---|
| 0 | — | Python 3.12 venv; `pip install -r requirements.txt -r requirements-dev.txt`; run the suite on `main`; note the failing tests | baseline list in the step-1 PR description |
| 1 | `feat/stay-fee-core` | `git apply --binary stay-fee-remittance-core.patch` (delivered with this plan). It adds: the DB columns + one-time reset, `validation.DOC_TYPES` + `age_on`, `stay_fee.py`, `stay_fee_remittance_pdf.py` (Invoice companion), `tests/test_stay_fee.py`, the design kit folder `docs/plans/stay-fee-remittance-design/` (the owner's DESIGN.md, `build_sample.py`, the sample PDF), the fixed content mockups (§0.1 #13–14) and **this plan**. Then run `App/.venv/bin/python docs/plans/stay-fee-remittance-design/build_sample.py` and check the sample opens | `test_stay_fee.py` (40) green; `test_db_upgrade.py`, `test_payments.py` green; no new failures |
| 2 | `feat/stay-fee-property-panel` | §9.4 (panel, payload, account validation, copy-from JS) + §12.2 `apartment.form.stay_fee.*` | `test_stay_fee_property_panel.py`: see below |
| 3 | `feat/stay-fee-doc-type` | §9.5 + `guest.doc_type.*` keys | `test_stay_fee_doc_type.py`: see below |
| 4 | `feat/stay-fee-entity-signature` | §8.3 + `entity.signature_*`, `flash.entities.signature_invalid` | `test_stay_fee_signature.py`: see below |
| 5 | `feat/stay-fee-list` | `routes/stay_fees.py` (list route), `stay_fees.html`, sidebar, icon, palette, `main.py`, **all §12.1 keys** | `test_stay_fee_list.py`: see below |
| 6 | `feat/stay-fee-detail` | detail route + template, payment panel, guest list, decision POST, CSS | `test_stay_fee_detail.py`: see below |
| 7 | `feat/stay-fee-downloads` | PDF + CSV routes (§8.2, §10); the PDF module is `stay_fee_remittance_pdf` | `test_stay_fee_downloads.py`: see below |
| 8 | `docs/stay-fee` | `App/README.md` "What it deliberately does not do": the fee line becomes "Calculates the local stay fee (poplatek z pobytu) per property and prepares the council report PDF, register CSV and a payment QR for the host. It does not collect the fee from guests, file the report or make the payment." `docs/plans/README.md`: this plan, **Built**. Add a banner to `PLAN_POPLATEK_Z_POBYTU.md`: "> Superseded for the host side by `stay-fee-remittance/PLAN_STAY_FEE_REMITTANCE.md`; the guest side stays on hold." `docs/OPERATIONS.md`: a short "Stay fee" subsection | — |
| 9 | — | Owner merges and deploys **staging**. You run the QA list below | owner sign-off |

**Test contents per step:**

- **Step 2, `test_stay_fee_property_panel.py`:**
  - The edit page has `#stay-fee-settings` and the nav link; the create page doesn't.
  - Rate 75 → 50; `abc` → 0.
  - The VS `12 34-56` → `123456`.
  - The account `19-2000781379/0800` → IBAN `CZ3008000000192000781379`. An invalid account → error flash and **nothing** saved.
  - A post without the fee fields keeps the stored values.
  - `fee_template_peers` excludes the property itself and rate-0 properties.
  - The warning shows when rate > 0 and the VS is empty.
- **Step 3, `test_stay_fee_doc_type.py`:**
  - The select has 9 options, with `op` preselected for a CZE guest.
  - Saving `trvaly_pobyt` stores it; `bogus` → NULL.
  - The guest's own form HTML has no `doc_type`.
- **Step 4, `test_stay_fee_signature.py`:**
  - A PNG upload is stored encrypted: the column doesn't start with `data:`, and `decrypt_field` gives a `data:image/png` URI.
  - A 301 KB file → error.
  - A text file renamed `.png` → error.
  - Remove clears it; the typed name is saved.
  - The PDF text contains the typed name when there's no image.
- **Step 5, `test_stay_fee_list.py`:**
  - Login is required.
  - With no active property → the empty state and no `btn accent primary`.
  - Monthly + quarterly properties → the rows show "Srpen 2026" and "3. čtvrtletí 2026" (CS) with the right numbers.
  - Another owner's properties never appear.
  - The chips mark the selected month.
  - A future `month` → redirect.
  - The sidebar link `/stay-fees` exists.
  - `/api/command-palette` lists it.
- **Step 6, `test_stay_fee_detail.py`:**
  - Another owner's property → redirect with an error.
  - The metrics show the group totals.
  - The group note lists the sibling properties.
  - The QR `<img>` is present with a council IBAN + VS and absent without.
  - Exempt without a reason → error flash; with a reason → the total drops, the audit row has no reason text.
  - `charge` on a minor → the total rises.
  - `""` → back to automatic.
  - Another owner's guest → error.
  - Exactly one `btn accent primary` when there are no issues, zero when blocked.
  - The page never contains "undefined" or a raw `stay_fees.` key.
- **Step 7, `test_stay_fee_downloads.py`:**
  - The PDF is `application/pdf`, starts with `%PDF`, and its text contains the office name, the period label, the VS and the total.
  - For a running period → a redirect with `report_blocked`.
  - A zero period → it still renders.
  - For quarterly, the text contains "ČTVRTLETNÍ HLÁŠENÍ" and "za 3. čtvrtletí".
  - The CSV has a BOM and `;`, the header equals the `REGISTER_COLUMNS` labels, and restricted guests are blanked.
  - Both are owner-scoped.

**Step 9 staging QA list:**

- (a) Rate 0 everywhere → the empty state; the guest flow unchanged.
- (b) Set up Praha 3 as in the mockup → the list row, the detail, the QR scans in a Czech banking app with the right amount and VS, and the PDF matches `stay-fee-remittance-design/sample-invoice-companion.pdf` in layout.
- (c) A 30.8.–3.9. stay, 2 adults + 1 child → August 4 liable / 2 exempt, September the same.
- (d) Exempt one adult with a reason → the totals update on the list, the detail, the PDF and the CSV.
- (e) Two properties with the same VS → one combined PDF, and the group note on both.
- (f) Brno quarterly → Q3 figures, and the PDF says "ČTVRTLETNÍ HLÁŠENÍ … za 3. čtvrtletí 2026".
- (g) Czech and English UI, 1440 px and 375 px.

---

## 14. Explicit non-goals for v2

- Nothing guest-facing: no fee amount, QR, payment or exemption input for guests. `PLAN_POPLATEK_Z_POBYTU.md` stays on hold.
- **No stay-page fee panel** (`reservation_detail.html` is unchanged).
- No electronic filing, no data-box integration, no bank API, no payment verification, no "paid/remitted" status.
- No municipality-specific form clones; no ohlášení (§14a) automation.
- No per-document signature override; no free-number overrides of the figures.
- No frozen snapshots: a changed rate or decision changes past periods on re-download (see §15 #6).

---

## 15. Open items for the owner and a lawyer (list them in the step-8 PR; do not implement)

1. **Night allocation:** each night goes to its date's month. Confirm with your office (Praha 3) that this is how they count a stay crossing the month end.
2. **60-day limit:** out of scope from 61 calendar days (60 nights). Confirm.
3. **Under-18 on the arrival day** vs someone turning 18 during the stay.
4. **Exemption reasons are free text** and may reveal health data (ZTP/P). §3g requires "důvod osvobození". Confirm the GDPR basis (Art. 6(1)(c), Art. 9(2)(b)/(g)) and add "stay-fee register" to the DPA/privacy documents' purposes.
5. **Restricted guests (Art. 18)** are counted, with identity blanked in the CSV. Confirm.
6. **No snapshots:** a later rate change alters the figures of past periods on re-download. The host should keep the PDF and CSV they filed. Is a regenerated CSV an acceptable evidenční kniha ("trvalost zápisů", §3g(3))?
7. **One hlášení per VS:** confirm the offices accept one hlášení covering several facilities under one VS.

---

## 16. Sources (checked 29–30 Sep 2026)

- Zákon č. 565/1990 Sb., o místních poplatcích: https://www.zakonyprolidi.cz/cs/1990-565
- OZV hl. m. Prahy č. 18/2019 Sb. ve znění 19/2021: https://praha.eu/documents/d/praha/vyhlaska_c_18_2019_sb_3078187
- Praha 1, Poplatek z pobytu (assigning days to months; register contents; deadlines): https://www.praha1.cz/potrebuji-si-vyridit/odbory/poplatek-z-pobytu/
- Portál veřejné správy, Poplatek z pobytu: https://portal.gov.cz/sluzby-vs/poplatek-z-pobytu-S1005
- Deník veřejné správy, Poplatek z pobytu a měsíční hlášení (zero reports): https://denikverejnespravy.cz/clanek.asp?id=7068720
- QR Platba (SPAYD) specification: https://qr-platba.cz/pro-vyvojare/specifikace-formatu/
