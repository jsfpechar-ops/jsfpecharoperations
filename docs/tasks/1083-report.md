# 1083 report: police letter parser

Status: review (attempt 3 of 3)

## Files

- `App/app/police_letter.py` (new): `parse_letter`, `confirmed_fields`, `line_from_form`, `FieldResult`, `LetterResult`, `FIELDS`, `FILLED_STATES`, `MAX_LETTER_CHARS`.
- `App/tests/test_police_letter_parser.py` (new): 145 parser rows, 15 `confirmed_fields` rows, 19 `line_from_form` rows.
- `docs/tasks/1083-police-letter.md`: `Status: review`, rules 11 and 12 added.

## Commands

- `pytest tests/test_police_letter_parser.py tests/test_ubyport_sample_pdf.py -q --tb=short`: `198 passed, 2 warnings`
- `pytest tests/test_police_*.py tests/test_ubyport_*.py -q --tb=short -x`: `243 passed, 2 warnings`
- `python3 scripts/context_lint.py`: `context lint: OK`
- `ruff check` on both new files: clean.

## Acceptance (section 7)

- [x] A field is filled only for exactly one valid value that ends its line after its label, and only when it is the one value of its shape in the whole text.
- [x] The three functions never raise. ASCII-only values; the IDUB uses `[0-9]`.
- [x] Digits-only IDUB. No repair, no NFKC. The zkratka is derived only through `mark_from_ws_user`.
- [x] The password never appears in any result. The module has no I/O.
- [x] 145 table rows plus both form tables, all green.
- [x] Only section 3 files changed.

## Attempt 3: global rules (brief rule 12)

- A. IDUB: every 12 to 14 digit run in the text (also digits split by single spaces) is a candidate. Not exactly one: `unreadable`. The password-above window and its exception are deleted.
- B. Login: every `uby-ws…` token is a candidate. Not exactly one: `unreadable`.
- C. A printed mark is never the value. A `zkratk…` line with a different 5 to 6 character word: login and mark `conflict`.
- D. Wrap guard strips leading non-alphanumerics first.
- All inputs from both reviews are rows (`a3_*` and the attempt 2 block). Rows whose result changed were updated, none removed.

## Deviations (all stricter than the coordinator's text)

1. **A and B keep the label position:** exactly one candidate is `found` only if it also follows its label (same line, or next line after the colon). Without this, `V dotazu uveďte IDUB\n420974841356` (no period) would be `found`. So `Přihlašovací jméno:\nPřístupové heslo:\nUBY-WS_DEMO1…` gives the login `unreadable`, not `found`.
2. **The password-word guard stays** for the lines from the label to the value (`Heslem je Přihlašovací jméno: UBY-WS_ZZZZZ` must stay refused).
3. **C also reads the next non-blank line** when the zkratka line has no 5 to 6 character word (needed for `Zkratka:\nXYZ12`).
4. From attempt 1: NFC keeps U+212A, U+037E, U+1FEF; GAP and END avoid quadratic time.

## Known cost (owner should know)

- A letter that holds a spaced phone number of 12 digits (`+420 777 000 111`), a numeric password, a bank account or a timestamp gives the IDUB `unreadable`; the host types it.
- A password that looks like a login (`UBY-WS_…`) gives the login `unreadable`.
- `Přístupové heslo:\nIDUB: 934857203948` is `found` (one number): the connection test and the host's tick are the guard.

## Questions

- `line` is the value's line for `found`, the first label's line for `unreadable`, `None` otherwise. Right for 1085?
- 20001 spaces give `empty`, not `too_long`.

## Owner steps left

None. No PR is open yet.
