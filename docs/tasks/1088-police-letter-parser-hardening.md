# 1088: G6 police letter: parser hardening (source slices, separated numbers, dash logins, wider mark conflict, full-letter paste)

Status: review
Tier: A | Depends on: 1083 (merged, PR #877) | Base commit: 71448224 | Branch: claude/1088-police-letter-hardening
Executor: Fable 5.2 (owner tier override in decisions.md) | Attempts: 3 at most | Fits one session: stop at 60 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer
Review: an extremely strict fresh Fable diff review (owner's words) before the PR opens, on filing safety and the parser.
Report: docs/tasks/1088-report.md

## 1. Objective

The strict reviews of 1085 found five gaps in the merged parser `App/app/police_letter.py` (1083, final rules in `docs/tasks/1083-police-letter.md` rule 12). This brief closes them before 1085 wires the parser into the property editor. 1085 depends on this brief.

1. A new `FieldResult.source`: the exact text the value came from, which 1085 shows next to each value. It must never be able to show a password.
2. IDUB candidates written with separators (`2099-8877-6655`) count, so a numeric password makes the IDUB `unreadable`. Phone numbers and the data-box barcode of a full letter do not count, so that a full paste still works.
3. Login candidates written with any dash or with spaces count.
4. The mark conflict also covers words of 4 and 7 characters, and soft hyphens.
5. A wrapped login (`UBY-WS_ABCDE` then a line starting `F`) is `unreadable`.

**Tier A, filing HIGH RISK:** when in doubt the field stays empty, and the host types it.

## 2. Context

Read only these parts of `police_letter.py` (on 71448224):

| Lines | What |
|---|---|
| 29-57 | constants and dataclasses |
| 58-105 | patterns |
| 145-245 | `_candidates`, `_wrapped`, `_valid_value`, `_parse_field` |
| 246-312 | `_mark_conflicts`, `parse_letter` |

Today's behaviour, checked by running the parser on 71448224:

| Input | Today | After this brief |
|---|---|---|
| `IDUB: 209988776655` plus `Přístupové heslo: 2099-8877-6655` (also with `.` or double spaces) | IDUB `found` | `unreadable` |
| official letter plus `UBY–WS_DEMO2` or `UBY - WS_DEMO2` | login `found` | `unreadable` |
| official letter plus `Zkratka ubytovacího zařízení: DEMO`, `DEMO1XY` or `DE­MO1` | mark `derived` | login and mark `conflict` |
| `Přihlašovací jméno: UBY-WS_ABCDE\nF    Přístupové heslo: xx` | login `found` | `unreadable` |
| `Přístupové heslo:\nXy7kLm9 IDUB: 209988776655` | IDUB `found` (a source would show the password) | `unreadable` |

### Rules (rule 12 of 1083 stays; where these differ, these win)

1. **The label starts its line.** Before a label, the label's line may hold only spaces and the noise characters `|`, `_`, `>`, `•`, `*` and `-`. Any other text before the label makes that label `unreadable`. "Unreadable wins" (rule 4) then empties the field. The prose skip (`_PROSE_RE`) runs first, so `V dotazu uveďte IDUB.` stays `missing` (the existing `prose_idub_*` rows keep passing). For a next-line value, the value line must also hold nothing before the value (this is true today through `_GAP_NEXT`; keep it).
2. **`source`:** add `source: tuple[str, ...] = ()` as the **last** field of `FieldResult`. For a `found` value it holds exact slices of the normalised text, never whole lines:
   - same-line layout: one string, from the label's first character to the value's last character (for example `IDUB: 209988776655`)
   - next-line layout: two strings, the label slice up to and including its colon, and the value itself
   - each string is cut to 120 characters
   - a `derived` mark carries the login's `source`
   - every other state has `()`
   Because of rule 1 and the slice, no text outside the label and the value can appear.
3. **IDUB candidates, the maximal chain rule:**
   - **Chain:** a run of ASCII digit groups joined by single separators: one `-`, `.` or `/`, or one or more spaces or tabs. It is maximal: it extends as far as the separators allow, and is never cut in the middle.
   - **Candidate:** a chain whose digits, joined, number 12 to 14. A chain of one unbroken group is today's digit run.
   - **Not a candidate:**
     - a chain right after a `+` (only spaces between): a phone number such as `+420 777 000 111`
     - attempt 2 (review, replaces the earlier `+420777000111` clarification): every unbroken run of 12 to 14 digits anywhere is a candidate, also inside a longer chain, and so is a run of 12 or more digits right after a `+`. Only the spaced phone shape after `+` is excluded. Chain separators also include the en dash, `,`, `_` and a separator with spaces around it. A soft hyphen is removed before the "zkratka" match.
     - a chain of exactly the shape `[0-9]{3}\.[0-9]{4}\.[0-9]{7}`: the data-box barcode (`SAMPLE_DS_BARCODE = "380.0000.0000001"`, `ubyport_sample_pdf.py:37`), printed at the foot of every letter
   - Only an unbroken group right after a label can be the value. The rest of rule 12A (exactly one distinct candidate) is unchanged.
   - Replace `_SPACED_DIGITS_RE` with the chain pattern. Keep `_DIGIT_RUN_RE` if it is still used.
4. **Login candidates with any dash or spaces:** the candidate pattern becomes `uby[ \t]*[-‐‑‒–—−][ \t]*t?ws[_A-Za-z0-9]*`, without case.
   - Candidates are compared after `upper()` only, with no dash or space folding. So `UBY–WS_DEMO1` next to `UBY-WS_DEMO1` makes two distinct candidates, and the login is `unreadable`.
   - Only the plain `uby-ws…` form can be the value (`_valid_value` and `_WS_USER_RE`, unchanged).
5. **Mark conflict, wider but not narrower:** in `_mark_conflicts`, keep today's set: any `_WORD_RE` (Unicode letters and digits) token of 5 or 6 characters. Add tokens of 4 and of 7 characters.
   - Exclude every token whose plain form (`_plain`) contains `zkratk`: "Zkratka" is itself 7 letters.
   - Remove soft hyphens (U+00AD) from the line before splitting it into words. A soft hyphen anywhere on a zkratka line, or on the next non-blank line when that one is read, is a conflict on its own.
   - Do not narrow the set to ASCII.
6. **Wrap guard for the login:** the login is `unreadable` when the line after the value, after `_LEADING_NOISE_RE`, **starts** with a `_WORD_RE` word of 1 to 3 characters followed by anything. Today only a line that is nothing but such a fragment counts. The official next line `Přístupové heslo:` starts with a 10-letter word and stays fine.
7. **Full-letter paste:** the text of the whole sample letter must give IDUB `found` (`SAMPLE_IDUB`), login `found` (`SAMPLE_WS_USER`) and mark `derived` (`SAMPLE_ZKRATKA`). Build the text from the strings that `_draw_cover_letter` and `_draw_credential_extract` (`ubyport_sample_pdf.py:159-320`) draw, one string per line, in drawing order. Leave out UbyHost's own annotations (the text of `_draw_field_mapping_block` and `_draw_off_letter_callout`): they are not part of a police letter, and the mapping line `IDUB → UbyHost IDUB (…)` would rightly make the IDUB `unreadable`. A separate row adds the `+420` phone of the callout. If the parser cannot pass this row without breaking a rule above, STOP and report which line breaks it. Do not loosen a rule.
8. **Kept:** never raises; ASCII-only values; the prose rule and the next-line colon; the password-word guard; "unreadable wins"; the mark is only `derived`.

### Anchors (verified on 71448224; re-check each with `grep -nF`)

1. `App/app/police_letter.py`: `class FieldResult:`, `_SPACED_DIGITS_RE = re.compile(`, `_LOGIN_TOKEN_RE = re.compile(`, `def _candidates(`, `def _wrapped(`, `def _mark_conflicts(`, `words = [w for w in _WORD_RE.findall(line) if 5 <= len(w) <= 6]`
2. `App/app/ubyport_sample_pdf.py:32` `SAMPLE_CONTACT = "+420 777 000 111"`, `:37` `SAMPLE_DS_BARCODE = "380.0000.0000001"`, `:159` `def _draw_cover_letter(`, `:247` `def _draw_credential_extract(`
3. `App/tests/test_police_letter_parser.py` exists and is green before you start.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/police_letter.py` | edit | rules 1 to 6 and `source` |
| `App/tests/test_police_letter_parser.py` | edit | the step 2 rows; the existing rows stay green |
| `docs/tasks/1088-report.md` | create | the report, plus `Status: review` here |

## 4. Steps (commit after each: `1088 step k`)

1. Confirm anchors 1 to 3 with `grep -nF`; if one is missing, STOP. Run section 6's first command: green. Apply rules 1 to 6.
2. Add these rows to the parser table (states as expected):
   - **Separated IDUB candidates:** `IDUB: 209988776655` plus a password line `Přístupové heslo: 2099-8877-6655`; the same with `2099.8877.6655`, with `2099  8877  6655` and with `2099/8877/6655`: IDUB `unreadable`. `IDUB: 2099-8877-6655` alone: `unreadable`.
   - **Excluded chains:** the official letter plus `+420 777 000 111`: IDUB `found`. The same plus `380.0000.0000001`: `found`. The same plus `420 777 000 111` with no `+`: `unreadable`.
   - **Full sample letter (rule 7):** IDUB `found`, login `found`, mark `derived`.
   - **Dash logins:** the official letter plus `UBY–WS_DEMO1`, plus `UBY - WS_DEMO1`, and plus `uby—ws_demo2`: login `unreadable`, mark `missing`.
   - **Mark conflict:** the official letter plus `Zkratka ubytovacího zařízení: DEMO` (4), `…: DEMO1XY` (7), `…: DE­MO1` (soft hyphen), `…: DĚMO1` (Unicode, 5): login and mark `conflict`. `…: DEMO1`: mark `derived`. `Zkratka ubytovacího zařízení:` alone (only the label words): `derived`.
   - **Wrap guard:** `Přihlašovací jméno: UBY-WS_ABCDE\nF    Přístupové heslo: xx`: login `unreadable`. The official letter: `found`.
   - **Text before a label:** `Přístupové heslo:\nXy7kLm9 IDUB: 209988776655`: IDUB `unreadable`, and `Xy7kLm9` appears in no field's `repr`. `• IDUB: 209988776655` and `| IDUB: 209988776655`: `found`.
   - **`source`:** the official letter gives IDUB `source == ("IDUB: 209988776655",)`. A next-line layout gives `("IDUB:", "209988776655")`. The mark's `source` equals the login's. A 200-character label line is cut to 120. No `source` string of any row contains `SAMPLE_WS_PASSWORD` or a password-row value.
   An old row that now fails on purpose: change its expectation, and name it in the report.
3. Run section 6, then write the report.

## 5. Do not touch

`validation.py`, `ubyport_sample_pdf.py`, the routes, the templates, the CSS, i18n, `db.py`, migrations, any dependency. The public names (`parse_letter`, `confirmed_fields`, `line_from_form`, `FIELDS`, `FILLED_STATES`, `MAX_LETTER_CHARS`) keep their signatures. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`)

From `App/`: `.venv/bin/python -m pytest tests/test_police_letter_parser.py tests/test_ubyport_sample_pdf.py -q --tb=short -x`. Filing row: `.venv/bin/python -m pytest tests/test_police_*.py tests/test_ubyport_*.py -q --tb=short -x`. Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] Text before a label empties the field. `source` holds only the label-to-value slices, 120 characters at most each, and never a password.
- [ ] Separated 12 to 14-digit chains count as IDUB candidates, except a `+` phone and the barcode shape. The full sample letter parses.
- [ ] Dash and space login variants count as candidates.
- [ ] The mark conflict covers Unicode tokens of 4 to 7 characters (the label words excluded) and soft hyphens.
- [ ] The login wrap guard catches a 1 to 3-character first word.
- [ ] All old and new rows green. `git diff --stat origin/main` touches only section 3 files.

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; the full sample row (rule 7) needs a looser rule; a test fails twice on the same cause (attempt 3 of 3); 60 tool calls or 60k tokens (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to n.`).

## 9. Report

`docs/tasks/1088-report.md`, 400 tokens at most: files, each command with its last 5 lines, section 7 ticked, the rows added and the old rows changed, deviations and questions. Set this brief `Status: review`. After the strict fresh Fable review, open one PR. Body: parser only, not yet wired in, no request, no storage. Merge only with `scripts/merge-pr-on-green.sh`.
