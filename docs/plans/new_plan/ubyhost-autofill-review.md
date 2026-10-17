# UbyHost: every field a host or guest types, and what we can fill for them

*11 Oct 2026. Read from the repo (templates + routes), not guessed. ARES checked live today.*

**The rule:** a field is typed by a person only if no one else knows the answer. Otherwise we **derive** it (from something they already typed), **look it up** (from a free public register), **copy** it (from their other property or the previous guest), or **default** it (a sensible value they can change later).

## 1. The headline numbers

To set up one flat completely (operator + property + police + calendar + stay fee + invoicing), a host types today **about 45 fields**. With the changes below: **about 12**.

| Area | Typed today | After | How |
|---|---|---|---|
| Operator (who runs it) | 4 required + 2 optional + signature | **1** (IČO), plus an e-mail check | ARES fills name, seat, DIČ; e-mail = login e-mail |
| Property basics + address | name + 7 address boxes | **2** (name, address on one line) | 0045 splits the address |
| Police (UbyPort) | IDUB, mark, police name, WS login, WS password | **3** (IDUB, login, password) | 0043 derives the mark and the name |
| Calendar | URL + platform + own name | **1** (URL) | the platform is **already** auto-detected |
| Guest link, PIN, purpose, windows | 6 | **0** | **already** defaulted; just hide them under "More options" |
| Stay fee | 9 | **3** (pick town, rate, VS) | 0052 municipality list fills the office name, address and data box |
| Invoice settings | 7 | **1** (bank account) | ARES gives VAT status and the registry entry; the bank code gives the BIC |
| Each invoice (buyer) | 8 buyer boxes | **0–1** | "Use the guest's details" or IČO → ARES |

## 2. What we already do well (no work needed)

Credit where due: the app is smarter than it looks. The problem is mostly that the smart bits are hidden among visible fields.

- **Calendar platform** is detected from the link (`icalsync.platform_of`).
- **The guest-link name** comes from the property name (`guest_slug.readable_part`).
- **The PIN** is generated automatically, the default purpose is "tourism", and the windows have defaults.
- **Guest form:** the second guest gets the first guest's address offered automatically (`routes/guest.py` ~line 205). Browser autofill works (`given-name`, `family-name`, `bday`, `country`, address). The passport photo upload appears only for foreigners.
- **Invoice:** the buyer e-mail comes from the stay; the operator comes from the property; the due date is today + due days; DUZP (the tax date) = checkout.
- **Settings copy** between properties (0046, planned).

## 3. Page by page: what to change

Legend: **D** derive · **L** look up · **C** copy · **Def** default/hide · **K** keep (only the person knows).

### Operator (`entities.html`)
| Field | Today | Change |
|---|---|---|
| IČO | typed | **K**, first and alone. Checksum checked as they type (`validation.ico_ok` exists) |
| Name, seat (address) | typed | **L** ARES `obchodniJmeno`, `sidlo.textovaAdresa` |
| DIČ (VAT ID) | typed | **L** ARES `dic` |
| Contact e-mail | typed | **Def** = the login e-mail (editable) |
| Phone | typed, optional | **K**, optional, under "More" |
| No IČO (private person) | not supported well | name + "same as the flat's address" tick |
| Signature | drawn or uploaded | **K**, but move it to "when you first need it" (invoices / the WS letter), not setup |

### Property (`apartment_form.html`)
| Field | Change |
|---|---|
| Internal name | **K** |
| Police facility name (`uby_name`) | **D** from the name (0043) |
| Address (7 boxes, plus district) | **D** one line → split (0045). Later: the flat's address → the municipality → the stay-fee office (0052) |
| IDUB, WS login, WS password | **K** (from the police letter) |
| Mark (`uby_mark`) | **D** from the WS login (0043) |
| Operator / controller pickers | **Def** to your only operator; hide when you have one |
| Reporting mode, after-hours, default purpose | **Def**, under "More options" |
| Guest message | **Def** a ready-made friendly text (CS/EN) instead of an empty box |
| Link name, PIN, windows, passport policy | **Def**, under "More options" |
| Calendar platform label, own name | **D**/hide; ask only the URL |
| Everything else for property #2 | **C** from property #1 (0046) |

### Stay fee (`_stay_fee_fields.html`)
| Field | Change |
|---|---|
| Office name, address, contact | **L** from the open state list of public offices with their data-box IDs, chosen by the flat's town (0052) |
| Data box (0051) | **L**, same list |
| Rate | **K** (each town sets its own; show "Prague: 50 CZK" style hints only where we're sure) |
| Cadence | **Def** monthly |
| VS (payment reference), payee account | **K** (from the town's letter); **C** to other flats in the same town |
| Instruction | **Def** generated |

### Invoice settings (`invoice_settings.html`)
| Field | Change |
|---|---|
| Bank account | **K**, and **C** from the stay-fee/payment account if already typed |
| BIC | **D** from the Czech bank code (`/0800` → GIBACZPX) using the national bank's code list, **shipped as a file in the repo** (no outbound request) |
| VAT status | **L** ARES: registered for VAT yes/no (`seznamRegistraci.stavZdrojeDph`) → suggest "payer" / "non-payer" |
| Registry entry ("Zapsáno v OR…") | **L** ARES `spisovaZnacka` (e.g. "B 8525/MSPH") + court-name map; empty for sole traders |
| Prefix, next number, due days | **Def** (already), hide under "More" |

### Each invoice (`invoice_form.html`)
| Field | Change |
|---|---|
| Buyer name, street, city, ZIP, country | **C** a button **"Use the guest's details"**: the lead guest's name and residence address from the check-in form. A button, not automatic (see privacy below) |
| Buyer is a company | **L** type their IČO → ARES fills name, address, DIČ |
| Buyer e-mail | already from the stay |
| Stay price | **K** (calendars don't carry the price); **C** remember the last price for that flat as a hint |
| Extra items | **Def** keep the existing kinds |

### Guest form (guest side, the most-used form)
Already good. Two small wins:
- **Residence country defaults to the nationality** (true for most guests; one tap to change).
- The phone keyboard should show numbers for the document number only where the country uses digits. Skip it: too fiddly, little gain.
- *Not doing:* reading the passport photo automatically (MRZ/OCR). It's heavy, needs a library or a paid API, and it can misread. Maybe later, as a paid extra.

## 4. Privacy and cost check

| Change | Outbound request? | Personal data? | Cost |
|---|---|---|---|
| ARES lookup | yes, to `ares.gov.cz`, sending **only the IČO** | the result is public register data | free, no key (checked today: JSON comes back with name, seat, DIČ, VAT and court file) |
| BIC from the bank code | no (a file in the repo) | no | free |
| Municipality list (0052) | a monthly download of a public file | no | free |
| "Use the guest's details" on an invoice | no | **yes**: reuses check-in data for the invoice. Keep it **a button the host presses**, and only for the stay's own guest. The guest is the buyer, so it's the same person and the same stay. Add one line to `docs/privacy/ROPA.md` | free |
| Residence country = nationality | no | no new data | free |
| Default guest message, hiding fields | no | no | free |

`requests` is already installed, so ARES needs **no new dependency**: just a decision line (you've said yes).

**One thing to check:** the ARES terms-of-use page loads with JavaScript, so I couldn't read it. The service is public and keyless; the brief caps us at 1 lookup per click, caches results for 24 h, and limits each user to 20 lookups per hour.

## 5. Build order

| # | Brief | Size | Status |
|---|---|---|---|
| 0043 | Police: 3 fields, derive mark + name | S | written |
| 0045 | One-line address | S | written |
| 0046 | Copy settings from another property | S | written |
| **0055** | **ARES lookup: operator form + invoice settings + invoice buyer** | M | **full prompt below** |
| 0061 | Invoice: "Use the guest's details" button, BIC from bank code, remember the last price | S | outline |
| 0062 | Hide-by-default pass: "More options" on the property form, default guest message, one-operator auto-pick, residence country = nationality | S | outline |
| 0052 | Municipality picker fills the stay-fee office + data box | M | outlined earlier |

**0061 outline:** ship the national bank's bank-code CSV as `App/app/data/bank_codes.csv` (code, name, BIC) with a dated source note; `payments.bic_for_account(account)` fills BIC when blank; the invoice form gets a `<button name="fill_from_guest">` (works without JS: re-render with values) that copies the lead guest (first complete guest on that reservation, owned by the host) into the buyer fields, never overwriting typed values; remember the last stay price per flat as a placeholder, not a value. ROPA line added.

**0062 outline:** the property form shows name, address, police (3), calendars; everything else goes inside `<details>` "More options" (open if any of those fields has an error). One operator → hidden input + "Operator: X · change". The default guest message comes from i18n (CS/EN) when blank. Guest form: if `res_country` is empty, the server pre-selects the nationality; JS mirrors it until the guest changes it themselves.

---

### 0055 Cursor prompt

````
Read AGENTS.md. Create docs/tasks/0055-ares-lookup.md with exactly the content between the BRIEF markers, commit it on a new branch task/0055-ares-lookup, then follow it exactly. Open only the files it names. If any stop condition in §8 happens, stop and write the report. Finish by writing docs/tasks/0055-report.md in the §9 format and opening one PR.
<<<BRIEF
# 0055: Fill business details from the IČO (ARES)

Status: todo
Depends on: none | Branch: task/0055-ares-lookup
Executor: Cursor local agent | Fits one session

## 1. Objective
A host types an IČO and presses "Fill from register". The operator form, the invoice settings and the invoice buyer fill themselves from the free public Czech business register (ARES). Nothing is saved until the host presses Save. It works without JavaScript.

## 2. Context
- ARES REST (checked 2026-10-11, no key): `GET https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/{ico}` → JSON. Fields used: `obchodniJmeno`, `sidlo.textovaAdresa`, `sidlo.nazevUlice`, `cisloDomovni`, `cisloOrientacni`, `cisloOrientacniPismeno`, `nazevObce`, `psc`, `dic`, `seznamRegistraci.stavZdrojeDph` ("AKTIVNI" = VAT-registered), `dalsiUdaje[]` item with `datovyZdroj == "vr"` → `spisovaZnacka` (e.g. "B 8525/MSPH"). 404 = unknown IČO.
- `validation.ico_ok` (mod-11 check) exists. `requests` is already a runtime dependency. `rate_limit.blocked/record` exist.
- Operator form: `templates/entities.html` (name, seat, ico, dic, contact_email…), POST `/entities` and `/entities/{id}` in `routes/admin.py` (~700–751).
- Invoice settings: `templates/invoice_settings.html`, `routes/invoices.py` `_settings_detail_payload` (vat_status, registry_entry).
- Invoice buyer: `templates/invoice_form.html` (buyer_name, buyer_street, buyer_city, buyer_zip, buyer_country, buyer_ico, buyer_dic), `routes/invoices.py` `_form_context`.
- Rules: rule 6 (works without JS), privacy rule 2 (outbound request: reason in the PR), decisions.md line, EN + CS parity.

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/ares.py | new | `lookup(ico) -> dict or None`, `CourtError`-free: returns None on any failure. 4 s timeout, User-Agent "UbyHost", in-memory cache 24 h, maps to `{name, seat, street, city, zip, country:"CZE", dic, vat_payer: bool, registry_entry}` |
| App/app/routes/admin.py | edit | entities form: if `fill_from_register` is in the POST, re-render the form with the looked-up values merged into blank fields only; do not save |
| App/app/routes/invoices.py | edit | the same for invoice settings (vat_status suggestion, registry_entry) and the invoice buyer (`fill_buyer_from_register`) |
| App/app/templates/entities.html, invoice_settings.html, invoice_form.html | edit | a secondary button "Fill from register" next to the IČO field (`<button name="fill_from_register" value="1" formnovalidate>`); a note "Filled from the public business register (ARES). Check and save." |
| App/app/host_i18n.py | edit | EN + CS keys `ares.*` |
| App/tests/test_ares.py | new | tests with a mocked `requests.get`; **no real network in tests** |
| docs/context/decisions.md | edit | `- 2026-10-11 \| ARES lookup on host click; sends only the IČO; requests lib; 24 h cache; 20/h per user \| owner \| [0055](../tasks/0055-ares-lookup.md)` |

## 4. Steps
1. `ares.lookup`: reject if `not validation.ico_ok(ico)` (no request). Map the registry entry: `spisovaZnacka` "B 8525/MSPH" → "spisová značka B 8525 vedená u Městského soudu v Praze"; court map MSPH Městský soud v Praze, KSBR Krajský soud v Brně, KSOS … v Ostravě, KSPH … v Praze, KSPL … v Plzni, KSUL … v Ústí nad Labem, KSHK … v Hradci Králové, KSCB … v Českých Budějovicích; unknown code → keep the raw value.
2. Rate limit: scope "ares", key = owner id, 20 per hour; blocked → the flash "Too many lookups, try again later".
3. Merge rule: **fill only fields that are blank** in the submitted form; list which fields were filled in the note. Never touch the signature, e-mail or phone.
4. vat_status: `vat_payer` True → preselect "payer", else leave as is. Show "We found: VAT registered" as text so the host confirms.
5. Failures (None): the message "The register didn't answer or doesn't know this IČO. Please type the details." Keep everything typed.
6. JS (optional progressive enhancement): none required. Do not add fetch calls.
7. Tests: valid IČO → fields filled, nothing saved to the DB; typed values never overwritten; bad checksum → no request made; timeout → friendly message; rate limit after 20; court mapping; CS/EN keys exist.

## 5. Do not touch
UbyPort, the guest pages, migrations (none needed), the signature handling.

## 6. Commands
From App/: `.venv/bin/python -m pytest tests -q`. Root: `python3 scripts/context_lint.py`. Browser and geometry tests 0 skipped.

## 7. Acceptance
- [ ] On /entities, typing 27074358 and pressing "Fill from register" fills name, seat and DIČ; the page says what was filled; refresh without saving shows nothing stored.
- [ ] Screenshots of the three forms after a fill at 360, 390 and 1280 px.
- [ ] The PR states the outbound request and its reason.

## 8. Stop and ask
1. Any page already sends the IČO elsewhere, or an outbound allowlist blocks ares.gov.cz (CSP or an egress config).
2. The entities POST can't re-render without saving without restructuring the handler.

## 9. Report
Files, test tail, screenshots, the decision line added.
BRIEF>>>
````

## 6. Notes on your answers

- **Human help / testing with beginners:** dropped from the plan.
- **Screenshots for the guides:** if you don't have them, 0058 will use **drawn step cards** (simple CSS mock-ups of "Calendar → Export → Copy link"). They're cheaper, don't show anyone's data, and don't go stale as fast. If you do have them, drop them in and 0058 uses them.

---

### 0061 brief (invoice autofill)

<<<BRIEF
# 0061: Invoice fills itself: guest's details, BIC from the bank code, last price hint

Status: todo
Depends on: none | Branch: task/0061-invoice-autofill
Executor: Cursor local agent | Fits one session

## 1. Objective
Writing an invoice for a stay needs almost no typing: one button copies the stay's lead guest into the buyer fields, the BIC fills itself from the Czech bank code, and the stay price shows last time's price as a hint.

## 2. Context
- `App/app/routes/invoices.py`: `_stay_for`, `_form_context` (already copies `guest_email`), `invoice_new`, POST `/invoices/preview`, `_settings_detail_payload` (bic).
- `App/app/templates/invoice_form.html` buyer fields: buyer_name, buyer_street, buyer_city, buyer_zip, buyer_country, buyer_ico, buyer_dic, buyer_email; `stay_price`.
- `App/app/payments.py` `czech_account_parts(raw)` returns prefix/number/bank/iban.
- `guest` table: reservation_id, first_name, surname, res_street, res_city, res_country, archived_at; `reporting.guest_is_complete(row, reservation)`.
- Bank codes: ČNB list `https://www.cnb.cz/cs/platebni-styk/.galleries/ucty_kody_bank/download/kody_bank_CR.csv` (semicolon CSV, columns code; name; BIC; CERTIS). Checked 2026-10-11 (0800 → GIBACZPX, 2010 → FIOBCZPP).
- Privacy rule 2. This reuses check-in data for that same guest's invoice, only when the host presses the button.

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/data/bank_codes.csv | new | the ČNB file saved once in UTF-8 (code;name;bic), with a header comment line giving the source URL and date |
| App/app/payments.py | edit | `bic_for_account(account: str) -> str` (from the bank part of a Czech account, or the IBAN's digits 5–8 for CZ IBANs); "" if unknown |
| App/app/routes/invoices.py | edit | the settings save fills `bic` when blank; preview/new: `fill_from_guest` button handling; the last-price hint |
| App/app/templates/invoice_form.html | edit | `<button name="fill_from_guest" value="1" formnovalidate class="btn-secondary">Use the guest's details</button>` above the buyer block, shown only when the stay has a complete guest; the price `placeholder` = the last price |
| App/app/host_i18n.py | edit | EN + CS keys `invoice.fill_guest.*`, `invoice.price_hint` |
| docs/privacy/ROPA.md | edit | one line: check-in name and address may be copied to that stay's invoice on host request |
| App/tests/test_invoice_autofill.py | new | tests |

## 4. Steps
1. Lead guest = the first (lowest id) non-archived guest on the reservation for which `guest_is_complete` is true and that belongs to the host's apartment.
2. On `fill_from_guest`: re-render the form (no save, no preview) with buyer_name = "first_name surname", buyer_street = res_street, buyer_city = res_city, buyer_country = res_country. **Only fill blank fields.** Keep all other typed values (reuse `_form_state`).
3. BIC: on settings save, when `bic` is blank and the account has a known bank code, store the derived BIC; show it in the form as "Filled from your bank code". Never overwrite a typed BIC.
4. Price hint: the last issued invoice for the same apartment → its stay item unit price as the `placeholder` (not a value).
5. Tests: the button fills blanks only; another host's guest is never used; no complete guest → no button; BIC 0800 → GIBACZPX, unknown → blank; a typed BIC is kept; the hint is a placeholder and empty when there is no earlier invoice; works without JS.

## 5. Do not touch
Invoice numbering, the PDF layout, issue/cancel logic, migrations (none).

## 6. Commands
From App/: `.venv/bin/python -m pytest tests -q`. Root: `python3 scripts/context_lint.py`. Browser and geometry tests 0 skipped.

## 7. Acceptance
- [ ] A stay with a checked-in guest: one click fills the buyer; the preview shows the guest as buyer.
- [ ] Screenshots of the invoice form before and after the fill at 360, 390 and 1280 px.

## 8. Stop and ask
1. The invoice form can't re-render without a preview POST without restructuring the routes.
2. Guest rows are encrypted or not readable from the invoices route without a new access helper.

## 9. Report
Files, test tail, screenshots, the ROPA line.
BRIEF>>>

---

### 0062 brief (hide by default)

<<<BRIEF
# 0062: Calmer forms: "More options", default guest message, one-operator auto-pick, residence = nationality

Status: todo
Depends on: none (rebase after 0043/0045 if they merged first) | Branch: task/0062-calmer-forms
Executor: Cursor local agent | Fits one session

## 1. Objective
The property form shows only what a host must answer: name, address, the police fields and calendar links. Everything that already has a good default moves into a closed "More options" section. Small defaults remove more typing.

## 2. Context
- `App/app/templates/apartment_form.html`: sections basics/address/ubyport/automation/communication/stay-fee/door-code/calendars; fields `legal_entity_id`, `data_controller_entity_id`, `automation_mode`, `submit_after_hours`, `default_purpose`, `guest_message`, `guest_link_name`, `permalink_pin`, `permalink_window_days`, `permalink_reachback_days`, `passport_photo_policy`; calendar fields `url`, `label`, `own_name`.
- `App/app/routes/admin.py` `_apartment_payload` (~line 900–980) and the update handler (~1120). The PIN is generated (`auth.new_permalink_pin`), the purpose defaults to `validation.DEFAULT_PURPOSE`, the platform is detected (`icalsync.platform_of`).
- `App/app/templates/guest/form.html`: `nationality` select (~line 130), `res_country` select (~line 215), the `val()` macro.
- HOST_APP_DESIGN §1; rule 6 (works without JS); readiness links (`_readiness`) must still reach every field.

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/templates/apartment_form.html | edit | wrap automation mode, after-hours, purpose, link name, PIN, windows, passport policy, controller and the calendar `label`/`own_name` inputs in `<details class="more-options">` "More options", `open` when any of those fields has an error or a readiness link targets one |
| App/app/templates/apartment_form.html | edit | when the host has exactly one operator: a hidden `legal_entity_id` and the text "Operator: {name} · change" (a link to show the select via `<details>`) |
| App/app/routes/admin.py | edit | blank `guest_message` on **create** → the i18n default text (CS/EN by host language); never on update |
| App/app/templates/guest/form.html | edit | `res_country` falls back to the chosen nationality when empty (`val('res_country', val('nationality'))`); small JS mirrors nationality → residence until the guest changes residence |
| App/app/host_i18n.py, App/app/i18n.py | edit | EN + CS: `apartment.form.more_options`, `apartment.form.guest_message.default`, `apartment.form.operator_only` |
| App/app/static/components.css | edit | `.more-options` summary styled like the existing section headers |
| App/tests/test_calmer_forms.py | new | tests |

## 4. Steps
1. Default guest message (EN): "Hello, before you arrive please fill in the short check-in form at the link below. It takes about 2 minutes per person and is required by Czech law. Thank you and see you soon!" CS: the same meaning, natural Czech.
2. The readiness checklist links to a field inside "More options" → the section renders `open` (server-side, from the `#anchor` the readiness item uses, or an `open_more=1` query).
3. Residence default: server-side only when `res_country` has no saved or posted value; the JS stops mirroring after the first manual change of `res_country`.
4. Tests: the form renders with `<details>` closed by default and open on a related error; one operator → the hidden input is posted and saves correctly; two operators → the select is shown; create with a blank message stores the default, update with a blank message stores blank; guest form: nationality DEU and empty residence → residence preselected DEU; a saved residence is never replaced.

## 5. Do not touch
UbyPort submission, validation rules, migrations (none), the stay-fee and door-code sections.

## 6. Commands
From App/: `.venv/bin/python -m pytest tests -q`. Root: `python3 scripts/context_lint.py`. Browser and geometry tests 0 skipped.

## 7. Acceptance
- [ ] The new-property page shows at most name, address, the police fields and the calendar URL above the fold at 390 px.
- [ ] Screenshots of the property form (closed and open) and the guest form at 360, 390 and 1280 px.

## 8. Stop and ask
1. Any browser test relies on a moved field being visible without opening `<details>`; list them before changing the tests.
2. The readiness anchors can't open the section without JS.

## 9. Report
Files, test tail, screenshots.
BRIEF>>>
