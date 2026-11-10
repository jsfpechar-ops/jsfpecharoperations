# 1083 report: police letter parser

Status: review

## Files

- `App/app/police_letter.py` (new): `parse_letter`, `confirmed_fields`, `line_from_form`, `FieldResult`, `LetterResult`, `FIELDS`, `FILLED_STATES`, `MAX_LETTER_CHARS`.
- `App/tests/test_police_letter_parser.py` (new): 86 parser rows, 15 `confirmed_fields` rows, 19 `line_from_form` rows.
- `docs/tasks/1083-police-letter.md`: `Status: review`.

## Commands

- `pytest tests/test_police_letter_parser.py tests/test_ubyport_sample_pdf.py -q --tb=short -x`: `139 passed, 2 warnings in 1.89s`
- `pytest tests/test_police_*.py tests/test_ubyport_*.py -q --tb=short -x`: `184 passed, 2 warnings in 3.83s`
- `python3 scripts/context_lint.py`: `context lint: OK` (warnings only, none about 1083)

## Acceptance (section 7)

- [x] A field is filled only for exactly one valid value that ends its line after its label.
- [x] The three functions never raise. ASCII-only values; the IDUB uses `[0-9]`.
- [x] Digits-only IDUB. No repair, no NFKC. The zkratka is derived only through `mark_from_ws_user`.
- [x] The password never appears in any result. The module has no I/O.
- [x] 86 table rows plus both form tables, all green.
- [x] Only section 3 files changed.

## Deviations

1. **NFC keeps three characters as written.** Plain NFC turns the Kelvin sign U+212A into ASCII `K`, so rule 2 as written would make `UBY-WS_ABCDK` `found`, against rule 3 and the step 2 row (`unreadable`). `_normalise` leaves U+212A, U+037E and U+1FEF (the only non-ASCII characters NFC maps to ASCII; a test scans all code points) untouched. Stricter, never looser.
2. **GAP and END are written in an equivalent form** (`[ \t]*(?:[:.\-–][ \t]*)?…`): the same language, but a long run of spaces cannot cost quadratic time.
3. **Password guard** checks every line from the label to the value, not only the value's line (stricter).

## Questions

- `line` for `found` and `ambiguous` is the line of the **value** (it differs from the label line when the value is on the next line); for `unreadable` it is the label's line. `line` is `None` for `ambiguous`, `conflict` and `missing`. Is that what 1085 wants?
- A 20001-character string of spaces only gives `empty`, not `too_long` (empty is checked first).

## Owner steps left

None. The strict review comes next; no PR is open yet.
