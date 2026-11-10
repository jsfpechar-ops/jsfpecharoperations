# 1083: G6 police letter, part 1 of 3: the parser and its test table

Status: todo
Tier: A | Depends on: nothing (main alone) | Base commit: f1ca4288 | Branch: claude/1083-police-letter
Executor: Fable 5.2 (owner tier override in decisions.md) | Attempts: 3 at most | Fits one session: stop at 25 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer
Review: an extremely strict fresh Fable diff review (owner's words) before the PR opens, on filing safety and the parser.
Report: docs/tasks/1083-report.md

## 1. Objective

Plan [speed-and-ease](../plans/speed-and-ease.md) G6 (line 266), owner decision 4c (yes). On 2026-11-10 the owner added an automatic connection test after the save. G6 ships in three briefs:

- **1083 (this one):** a pure parser module and its test table. No route, template or copy.
- **1085** (`1085-police-letter-flow.md`): the route, the template, the copy and the flow tests. It uses this module.
- **1086** (`1086-police-letter-ux.md`): the browser tests, the screenshots and the UX gate.

The host pastes the text of the police **web-service letter** ("Přihlašovací údaje pro robotické vkládání Ubyport Webová služba"). The parser picks out the **IDUB** (`IDUB:`) and the **login** (`Přihlašovací jméno:`). From those it derives the **short name (zkratka)** with `validation.mark_from_ws_user(login)`, because real letters usually do not print it (`ubyport_sample_pdf.py:300-307`). A printed "Zkratka ubytovacího zařízení" line is read too, when there is one. **The password (`Přístupové heslo:`) is never read.**

**Tier A, filing HIGH RISK (rule 1):** a wrong value files guests under the wrong account. The rule is: when in doubt, return nothing for that field. The host then types it, and 1085 makes the host tick every value that is filled.

## 2. Context

### The letter (from `App/app/ubyport_sample_pdf.py:252-263`, measured from official PDFs)

The title line `Přihlašovací údaje pro robotické vkládání Ubyport Webová služba`, then three label and value pairs: `Přihlašovací jméno:` then `UBY-WS_DEMO1`, `Přístupové heslo:` then the password, and `IDUB:` then `209988776655`. In a PDF a label and its value sit on one row, but copied text may put the value on the next line. The off-letter note (`:300-307`) says the zkratka is usually not on the letter and often matches the part after `UBY-WS_`. All `SAMPLE_*` values (`ubyport_sample_pdf.py:26-44`) are fake and safe to use in tests.

### Formats (`App/app/validation.py:1002-1013`; do not edit validation.py)

- `_IDUB_RE = ^[A-Za-z0-9]{12,14}$`. The host hint (`host_i18n.py:4551` on f1ca4288, key `apartment.form.ubyport.idub_hint`) says "12 to 14 numbers", so the parser is **stricter: digits only**.
- `_MARK_RE = ^[A-Za-z0-9]{5,6}$`.
- `_WS_USER_RE` (`:1010`) and `mark_from_ws_user` (`:1016`). Import and reuse both; do not copy the pattern.

### Parser rules (new `App/app/police_letter.py`, standard library plus `validation` only)

`parse_letter(text: str) -> LetterResult`. No database, request, logging, file or global state. The same input always gives the same output.

1. **Size:** empty after strip gives `status="empty"`. Over `MAX_LETTER_CHARS = 20000` characters gives `status="too_long"` and nothing is parsed. Otherwise `status="ok"`. Under `empty` and `too_long`, all three fields are `missing`.
2. **Normalise:** `unicodedata.normalize("NFC", text)`. `\r\n` and `\r` become `\n`. NBSP (U+00A0), narrow NBSP (U+202F), thin space (U+2009) and tab become a space. Nothing else changes: no NFKC (it would turn `²` or full-width digits into digits), no diacritic stripping of values, and no O-to-0 or l-to-1 repair. A value that needs a repair does not match.
3. **Pattern per field:** search the whole normalised text with `re.IGNORECASE`. Each pattern is `LABEL + GAP + VALUE + END`:
   - `GAP` = `[ \t]*[:.\-–]?[ \t]*(?:\n[ \t]*)?`: optional punctuation, then at most **one** line break.
   - `END` = `[ \t]*[.,;]?[ \t]*(?=\n|\Z)`. **The value must end its line.** So `Zkratka ubytovacího zařízení: podle přílohy` gives no `PODLE`, and a value line followed by `:` (a next-line `Heslo:` would give `HESLO`) does not match.

   | Field | LABEL | VALUE |
   |---|---|---|
   | `uby_idub` | `(?<![A-Za-z0-9])IDUB(?![A-Za-z0-9])` | `(\d{12,14})` |
   | `uby_ws_user` | `p[rř][ií]hla[sš]ovac[ií]\s+jm[eé]no` | `(uby-t?ws_?[A-Za-z0-9]{5,6})`, kept only if `_WS_USER_RE.fullmatch`, returned as written |
   | `uby_mark` (printed) | `zkratka\s+ubytovac[ií]ho\s+za[rř][ií]zen[ií]`; `\s+` may cross a line break; a bare `Zkratka` is not a label | `([A-Za-z0-9]{5,6})`, returned upper-cased |

4. **A label with no valid value:** a label that matches with `LABEL` but not with the full pattern (15 digits, spaces or a letter inside, words after the value, the value two lines down) is `unreadable` at that line. **Unreadable wins:** if one `IDUB` label reads fine and another is unreadable, the field is `unreadable` and empty.
5. **One answer or none:** exactly one distinct value (repeats count once; the login and the mark compare case-insensitively) gives `found`, with the line number (1-based) and the label of the first occurrence. Two or more distinct values give `ambiguous`, with all their line numbers and **no value**. No label gives `missing`.
6. **Password guard:** a value whose line also contains `heslo`, `password` or `passwort` (any case) makes that field `ambiguous`. There is no password field, and no pattern for `Přístupové heslo`. The password text must never appear in the result.
7. **The short name, after steps 3 to 6:**
   - Login `found`, and `derived = mark_from_ws_user(login)` is not empty:
     - printed mark `missing`: the mark is `derived`, with value `derived` and the line and label of the login
     - printed mark `found` and equal to `derived` (ignoring case): stays `found`
     - printed mark `found` but different: **both** the mark and the login become `conflict`, with no value and both line numbers
   - Login `found` with a test login (`uby-tws…`, `derived` empty): the printed mark keeps its state; there is no derivation.
   - Login not `found`: no derivation; the mark keeps its own state.
   - Printed mark `unreadable` or `ambiguous`: it stays so, and nothing is derived.
8. **Result types (frozen dataclasses):** `LetterResult(status, fields)`, where `fields` is a dict keyed `uby_idub`, `uby_ws_user`, `uby_mark`. Each value is `FieldResult(state, value, line, label, lines)`. `state` is one of `found derived missing ambiguous unreadable conflict`. `value` is `""` unless `found` or `derived`. `line` is an int or `None`, `label` is the matched label text or `""`, and `lines` is a tuple of ints. Constants: `FIELDS = ("uby_idub", "uby_ws_user", "uby_mark")`, `FILLED_STATES = frozenset({"found", "derived"})`.
9. **`confirmed_fields(form) -> tuple[list[str], list[str]]`** returns (listed, unconfirmed). `form` is any mapping with `.get`. It reads the hidden `letter_fields` (a comma list; keeps only names in `FIELDS`, in `FIELDS` order, without duplicates) and counts a field confirmed only if `letter_ok_<name> == "1"`.
10. **`line_from_form(form, name) -> int | None`:** `letter_line_<name>` read as an int from 1 to 100000 only (`str.isdigit()`, at most 6 characters), else `None`. 1085 uses it so a forged value can never crash the re-render.

### Anchors (verified on f1ca4288; re-check each with `grep -nF`)

1. `App/app/validation.py:1010` `_WS_USER_RE = re.compile(`
2. `App/app/validation.py:1016` `def mark_from_ws_user(user: str) -> str:`
3. `App/app/ubyport_sample_pdf.py:26` `SAMPLE_IDUB = "209988776655"` and `:28` `SAMPLE_WS_USER = f"UBY-WS_{SAMPLE_ZKRATKA}"`
4. `App/app/ubyport_sample_pdf.py:258` `"Přihlašovací jméno:"` and `:263` `"IDUB:"`

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/police_letter.py` | create | `parse_letter`, `confirmed_fields`, `line_from_form`, the dataclasses and constants (section 2) |
| `App/tests/test_police_letter_parser.py` | create | the table (step 2) |
| `docs/tasks/1083-report.md` | create | the report, plus `Status: review` here |

## 4. Steps (commit after each: `1083 step k`)

1. Confirm anchors 1 to 4 with `grep -nF`. If one is missing, STOP. Create `police_letter.py` exactly per section 2, with a module docstring that says: pure, no storage, no request, the password is never read.
2. Write `test_police_letter_parser.py`: one `@pytest.mark.parametrize` table of at least 50 rows, each `(id, text, expected)`, where `expected` maps each field to `(state, value)`. Build letters from `SAMPLE_IDUB`, `SAMPLE_WS_USER`, `SAMPLE_ZKRATKA` and `SAMPLE_WS_PASSWORD` imported from `app.ubyport_sample_pdf`, or from obviously fake values (`000011112222`, `UBY-WS_ABCDE`). It covers at least:
   - **Official layout** (the sample PDF order: title, login, password, IDUB): IDUB `found`, login `found`, mark `derived` = `SAMPLE_ZKRATKA`. The same with each value on the line after its label. The same with `\r\n`, with NBSP after the colon, and with labels written without diacritics (`Prihlasovaci jmeno`). The same in a full Czech letter body (`Vážený pane, …`, a `Strana 1 z 2` footer, a `Č. j.` line with digits).
   - **IDUB:** 11 digits, 15 digits, `1234 5678 9012`, `12345678901O`, `12345678901l`, full-width digits, a trailing `²`, and `IDUB: 209988776655 (viz níže)`: all `unreadable`. A trailing period or comma: found. `XIDUB:`: `missing`. The same IDUB twice: found. Two different: `ambiguous`, with lines. One readable and one unreadable: `unreadable`. The value two lines below the label: `unreadable`.
   - **Extra numbers ignored:** unlabelled 12 to 14-digit numbers (a phone number, `SAMPLE_JID`-like ids, `20261110120000`, a bank account), and an IČO of 8 digits.
   - **Login:** `UBY-WS_ABCDE`, `uby-ws_abcde1` and `UBY-WSab12cd` are found as written. `uby-tws1ab45` is found, and the mark stays `missing`. `UBY-WS_ABCD`, `UBY-WS_ABCDEFG` and `ub1234567`: `unreadable`. A login with no label: `missing`. Two different logins: `ambiguous`. One login in two cases: found once. A login on a line that holds `heslo`: `ambiguous`.
   - **Printed zkratka:** equal to the derived one: `found`. Different from the derived one: mark and login both `conflict`, both empty. Without a login: `found`. Without diacritics, split over a line break, or in lower case (returned upper case): `found`. `podle přílohy`: `unreadable`. A label line followed by a `Heslo:` line: `unreadable`, never `HESLO`. 4 or 7 characters, or a value with `Č`: `unreadable`. A bare `Zkratka: ABCDE`: `missing`, so the mark comes from the login.
   - **Password never out:** every row's `repr(result)` contains neither `SAMPLE_WS_PASSWORD` nor `Zz9!fake-pass`. A separate row has `Přístupové heslo: UBY-WS_ZZZZZ` (a password that looks like a login): the login must not be `UBY-WS_ZZZZZ`.
   - **OCR-like noise:** stray `|` and `_`, doubled spaces, a soft hyphen inside the title line, a label in capitals. The expected values do not change.
   - **Size:** empty and spaces only give `empty`. Exactly 20000 characters with a valid letter: `ok`. 20001 characters: `too_long`, all `missing`.
   - **Purity:** the same input twice gives equal results. With `socket.socket` monkeypatched to raise, a full parse still passes.
   Add a `confirmed_fields` table (unknown names ignored, duplicates folded, `letter_ok_x=0` and a missing tick count as unconfirmed) and a `line_from_form` table (`7` gives 7; `0`, `-1`, `1e3`, `999999999`, `abc`, `""` and `"٣"` give `None`).
3. Run section 6, then write the report.

## 5. Do not touch

`validation.py`, `ubyport_sample_pdf.py`, `reporting.py`, `ubyport/*`, `routes/*`, all templates, all CSS, all i18n, `db.py`, migrations, any dependency. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`)

From `App/`: `.venv/bin/python -m pytest tests/test_police_letter_parser.py tests/test_ubyport_sample_pdf.py -q --tb=short -x`. Filing row of the test-map: `.venv/bin/python -m pytest tests/test_police_*.py tests/test_ubyport_*.py -q --tb=short -x`. Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] A field is filled only for exactly one valid value that ends its line after its label. Two values, an unreadable label, a password-line value or a mark that conflicts with the login fill nothing.
- [ ] Digits-only IDUB. No repair and no NFKC. The zkratka is derived only through `mark_from_ws_user`, and is marked `derived`.
- [ ] The password never appears in any result. The module has no I/O.
- [ ] At least 50 table rows, plus the `confirmed_fields` and `line_from_form` tables, all green.
- [ ] `git diff --stat origin/main` touches only section 3 files.

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; a rule in section 2 cannot be met with the standard library; a test fails twice on the same cause (attempt 3 of 3); 25 tool calls or 60k tokens (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to n.`).

## 9. Report

`docs/tasks/1083-report.md`, 400 tokens at most: files, each command with its last 5 lines, section 7 ticked, the number of table rows, deviations and questions. Set this brief `Status: review`. After the strict fresh Fable review, open one PR. Body: a pure module, not wired in yet (1085 wires it), no request, no storage. Merge only with `scripts/merge-pr-on-green.sh`.

## 10. Open questions (not blocking)

- **Q1:** `_IDUB_RE` allows letters, but the hint says numbers. The parser takes digits only. If a real IDUB ever has a letter, the host types it.
- **Q2:** other letter variants may word their labels differently. Such a label gives `missing`, and the host types the value. Widen the labels only with a real, redacted sample from the owner.
