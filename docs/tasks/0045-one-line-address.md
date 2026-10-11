# 0045: Property address as one line, split for the police

Status: done
Depends on: 0043 merged | Branch: task/0045-one-line-address
Executor: Cursor local agent | Fits one session
Risk: HIGH (UbyPort report header). Never overwrite a field the host typed.

## 1. Objective
The host types the address once ("Vinohradská 1234/12, 120 00 Praha 2"). UbyHost splits it into street, house number, orientation number, postcode and municipality, shows the parts under "Address as sent to the police", and keeps them editable. There is no external lookup.

## 2. Context
- `App/app/templates/apartment_form.html` `<details ... id="address">`: fields addr_okres (optional), addr_obec (required), addr_obec_cast (optional), addr_street (optional), addr_house_no (required), addr_orient_no (optional), addr_zip (required).
- `App/app/validation.py`: `_HOUSE_RE = ^(?:\d{1,4}|E\d{1,4}|\d{1,4}E)$` (case-insensitive), `_ORIENT_RE = ^\d{1,3}[A-Za-z]?$`, `normalise_zip`. Limits in `APARTMENT_FIELD_LIMITS`.
- `App/app/routes/admin.py` `_apartment_payload(form)` and `APARTMENT_TEXT_FIELDS`.
- Auth and host forms work without JavaScript, so the split runs on the server at save.

## 3. Files
| Path | Action | What |
|---|---|---|
| App/app/validation.py | edit | `split_czech_address(line) -> dict` |
| App/app/routes/admin.py | edit | read `address_line`; fill only empty addr_* fields from the split |
| App/app/templates/apartment_form.html | edit | one visible input `address_line`; the 7 fields move into `<details>` "Address as sent to the police" |
| App/app/host_i18n.py | edit | EN + CS keys |
| App/tests/test_address_split.py | new | tests |

## 4. Steps
1. `split_czech_address(line)`: pure function, no I/O. Accepted shapes (comma optional, extra spaces ignored):
   - `Street 1234/12, 12000 Praha 2` and `Street 1234/12a, 120 00 Praha`
   - `Street 1234, 120 00 Praha` (house only)
   - `Obec 123, 54321 Obec` (village without streets: street empty)
   - `č.p. 123` / `čp. 123` prefixes, and `E123` evidence numbers
   - City part after " - " (`Praha 2 - Vinohrady`) → addr_obec_cast
   Return keys addr_street, addr_house_no, addr_orient_no, addr_zip, addr_obec, addr_obec_cast; a key is missing when unsure. Validate the outputs with `_HOUSE_RE` and `_ORIENT_RE` and drop any part that fails.
2. Save: if `address_line` is present, compute the split and set **only empty** addr_* fields. If a parsed value differs from a non-empty typed value, keep the typed one and add a warning issue "The address line and the details differ. We kept the details."
3. Template: one input "Address" with a placeholder example; below it, the details block, open when any required addr field is missing or a warning exists. Remove no field name. Don't persist `address_line` (no migration); render it from the parts.
4. Tests: at least 12 real-shape cases (table-driven), including failures that return {} and the "never overwrite" rule.

## 5. Do not touch
Report building, migrations, okres logic (stays optional and manual).

## 6. Commands
From App/: `.venv/bin/python -m pytest tests -q`. Root: `python3 scripts/context_lint.py`. Browser and geometry tests 0 skipped.

## 7. Acceptance
- [ ] Typing "Vinohradská 1234/12, 120 00 Praha 2" and saving fills all required police address items in the readiness list.
- [ ] Screenshots at 360, 390 and 1280 px.

## 8. Stop and ask
1. Any case where the split would fill addr_house_no with a number that is really the orientation number. If ambiguous, leave it empty and open the details.
2. A required addr field would need a new database column.

## 9. Report
Files, test tail, screenshots, the test-case table.
