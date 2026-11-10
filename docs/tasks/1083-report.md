# 1083 report: police letter parser

Status: review (attempt 2 of 3)

## Files

- `App/app/police_letter.py` (new): `parse_letter`, `confirmed_fields`, `line_from_form`, `FieldResult`, `LetterResult`, `FIELDS`, `FILLED_STATES`, `MAX_LETTER_CHARS`.
- `App/tests/test_police_letter_parser.py` (new): 118 parser rows, 15 `confirmed_fields` rows, 19 `line_from_form` rows.
- `docs/tasks/1083-police-letter.md`: `Status: review`, rule 11 added.

## Commands

- `pytest tests/test_police_letter_parser.py tests/test_ubyport_sample_pdf.py -q --tb=short`: `171 passed, 2 warnings`
- `pytest tests/test_police_*.py tests/test_ubyport_*.py -q --tb=short -x`: `216 passed, 2 warnings`
- `python3 scripts/context_lint.py`: `context lint: OK`

## Acceptance (section 7)

- [x] A field is filled only for exactly one valid value that ends its line after its label.
- [x] The three functions never raise. ASCII-only values; the IDUB uses `[0-9]`.
- [x] Digits-only IDUB. No repair, no NFKC. The zkratka is derived only through `mark_from_ws_user`.
- [x] The password never appears in any result. The module has no I/O.
- [x] 118 table rows plus both form tables, all green.
- [x] Only section 3 files changed.

## Attempt 2: review findings, all fixed (brief rule 11), each input is a table row

1. Wrapped value (`…655\n66`, `UBY-WS_ABCDE\nF`): `unreadable`.
2. The printed mark is read on the label's line only and must pass `_MARK_RE` (`…zařízení\nAdresa`: `unreadable`). A printed or bare `Zkratka` value that differs from the derived mark: login and mark `conflict`.
3. `IDUB.` and other sentence punctuation: prose, skipped. A next-line value needs `LABEL:`.
4. Password label above a next-line value: `unreadable`. Two value lines under one label: `ambiguous`.
5. Guard stem `hesl`, without diacritics, any case.

## Deviations

1. **Finding 4, two lines above:** taken literally, the official next-line layout (`Přístupové heslo:` / password / `IDUB:` / value), which step 2 requires to be `found`, would be dropped. So a password label two lines above is let through only when it is an open label and the line between is its value (not blank, not a label). Every other case is `unreadable`.
2. NFC keeps U+212A, U+037E and U+1FEF as written (plain NFC makes the Kelvin sign an ASCII `K`).
3. GAP and END are written without nested optional space runs (no quadratic time).
4. Row `mark_bare_label` changed: a bare `Zkratka: ABCDE` next to login `DEMO1` is now `conflict` (finding 2), not derived.

## Questions

- `line` is the value's line for `found`, the label's line for `unreadable`, and `None` for `ambiguous`, `conflict` and `missing`. Right for 1085?
- 20001 spaces give `empty`, not `too_long`.

## Owner steps left

None. No PR is open yet.
