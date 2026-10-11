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
