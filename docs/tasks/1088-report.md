# 1088 report: police letter parser hardening

Status: review

## Files

- `App/app/police_letter.py`: rules 1 to 6 and `FieldResult.source`
- `App/tests/test_police_letter_parser.py`: 27 new rows (`h_*`), `test_source_slices`, source and password asserts on every row
- `docs/tasks/1088-police-letter-parser-hardening.md`: two review clarifications (rule 1 prose skip first, rule 3 unbroken run after `+`)

## Commands

- `pytest tests/test_police_letter_parser.py tests/test_ubyport_sample_pdf.py -q --tb=short -x`: `234 passed, 2 warnings` after attempt 2 (198 before)
- `pytest tests/test_police_*.py tests/test_ubyport_*.py -q --tb=short -x`: `279 passed, 2 warnings`
- `python3 scripts/context_lint.py`: `context lint: OK` (3 WARN, none from this brief)

## Acceptance (section 7)

- [x] Text before a label empties the field; `source` holds only label-to-value slices, 120 characters at most, never a password
- [x] Separated 12 to 14-digit chains count, except a `+` phone and the barcode shape; the full sample letter parses
- [x] Dash and space login variants count as candidates
- [x] Mark conflict covers Unicode tokens of 4 to 7 characters (label word excluded) and soft hyphens
- [x] Login wrap guard catches a 1 to 3-character first word
- [x] All old and new rows green; only section 3 files touched

## Old rows changed

- Rule 1 (text before the label), `ambiguous` to `unreadable`, still empty: `idub_on_password_line`, `login_on_password_line`, `login_password_word_en`, `guard_inflection_heslem`, `guard_inflection_hesla`, `guard_capitals_no_diacritics`
- Rule 3 (`+` phone excluded), IDUB `unreadable` to `found`, as the brief's step 2 states: `a3_spaced_phone_number`

## Deviations

1. IDUB chains are compared as written, not as joined digits. The brief's own rows use a password with the same digits as the IDUB (`2099-8877-6655`); joined, it is the same candidate and the IDUB stays `found`. Compared as written (as rule 4 does for logins) it is `unreadable`, which the brief expects.
2. The excluded-chain rows put the extra line before the official letter, not after: a digit line right after the IDUB value trips the 1083 wrap guard, which is kept.
3. `_DIGIT_RUN_RE` removed: no longer used.

## Attempt 2 (strict review)

- Every unbroken 12 to 14-digit run is a candidate again, also inside a longer chain; a run of 12 or more digits right after `+` too. `_DIGIT_RUN_RE` is back.
- Chain separators: en dash, `,`, `_`, and spaces around a separator.
- A soft hyphen is removed before the "zkratka" match (the soft-hyphen tick now holds for the label word too).
- 9 `h2_*` rows added. `h_plus_phone_unbroken` (`+420777000111`) changed `found` to `unreadable`: the review's rule replaces the earlier clarification.
- Both questions below are closed by this.

## Questions (closed in attempt 2)

- A 12 to 14-digit run inside a longer chain (`99 209988776656 99`, 16 digits) was a candidate on 71448224 and is not one now ("never cut in the middle"). No row covers it. Keep, or count unbroken runs too?
- A soft hyphen inside the word "zkratka" itself hides the line from `_mark_conflicts` (unchanged from 1083). Strip it before the check?
