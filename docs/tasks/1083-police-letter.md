# 1083: G6 police details from the letter (find-it picture, paste and check, then an automatic connection test)

Status: todo
Tier: A | Depends on: nothing (main alone) | Base commit: f1ca4288 | Branch: claude/1083-police-letter
Executor: Fable 5.2 | Attempts: 3 at most | Fits one session: stop at 25 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer
Review: an extremely strict fresh Fable diff review (owner's words) before the PR opens: filing safety, the parser, UX.
Report: docs/tasks/1083-report.md

## 1. Objective

Plan [speed-and-ease](../plans/speed-and-ease.md) G6 (line 266) and owner decision 4c: the police letter fills IDUB and short name. The owner said yes, and added on 2026-11-10: after the save, run the existing UbyPort connection test automatically and say the result in plain words.

In the property editor, section "Reporting & fees", card `#ubyport` (`_property_editor.html:305-342`):

1. **"Where do I find these?"**: a folded card with a drawn, generic picture of a police letter. Numbered markers show where IDUB, short name (zkratka), login and password sit. Placeholder values only: never a real letter, a real IDUB, a real login, a real name, the police crest or the police logo.
2. **"Paste the letter text"**: the host pastes the text. The server reads it with a pure function: no outbound request, no AI, no storage. It picks out IDUB and zkratka, plus the web-service login if the letter has one. **The password is never extracted.** The host always types it by hand.
3. **Check answers**: the page comes back with the found values pre-filled in the fields, **not saved**. Each value shows where it came from (line number and label). Each has its own "Matches my letter" tick, and the save is refused until every pre-filled value is ticked. The host can edit any value first.
4. **After the save, an automatic connection test**: when the post carries letter values, the save runs the existing read-only test and shows the result in plain words. The test never files a guest; a new test proves it.

**Tier A, filing HIGH RISK (rule 1):** a wrong IDUB, zkratka or login files guests under the wrong account. So the rule is: when in doubt, fill nothing. A strict format check, refusal on two different candidates, a large parser table, and nothing saved without the host's tick.

## 2. Context

### Formats (learned from `App/app/validation.py:1002-1013`; do not edit validation.py)

- `_IDUB_RE = ^[A-Za-z0-9]{12,14}$`. The host hint (`host_i18n.py:4551`) says "12 to 14 numbers", so the parser is **stricter: digits only**, `\d{12,14}`. A letter or symbol inside the value means no match: the host types it.
- `_MARK_RE = ^[A-Za-z0-9]{5,6}$`; the save upper-cases it (`routes/admin.py:1774`).
- `_WS_USER_RE`: `uby-ws` plus 6 alphanumerics, `uby-ws_` plus 5 or 6, or `uby-tws` plus 5, case-insensitive. Reuse the compiled `validation._WS_USER_RE` for the final check (read it; do not copy the pattern by hand).

### Parser rules (new `App/app/police_letter.py`, pure, standard library only)

`parse_letter(text: str) -> LetterResult`. No database, no request, no logging, no global state. Same input gives the same output.

1. **Size:** empty after strip gives `status="empty"`. Over `MAX_LETTER_CHARS = 20000` characters gives `status="too_long"`, and nothing is parsed. Otherwise `status="ok"`.
2. **Normalise:** `unicodedata.normalize("NFC", text)`; `\r\n` and `\r` become `\n`; NBSP (U+00A0), narrow NBSP (U+202F), thin space (U+2009) and tab become a space. **No other change:** no NFKC (it would turn `²` or full-width digits into digits), no diacritic stripping of values, no O-to-0 or l-to-1 "repair". A value that needs a repair does not match.
3. **Labels:** search the whole normalised text with `re.IGNORECASE`. The gap between label and value is `[ \t]*[:.\-–]?[ \t]*(?:\n[ \t]*)?`: optional punctuation, then at most **one** line break. The value must start right after the gap.
   - IDUB: `(?<![A-Za-z0-9])IDUB(?![A-Za-z0-9])`, value `(\d{12,14})(?![A-Za-z0-9])`.
   - Zkratka: the full label `zkratka\s+ubytovac[ií]ho\s+za[rř][ií]zen[ií]` (`\s+` may include a line break; with or without diacritics, any case). Value `([A-Za-z0-9]{5,6})(?![A-Za-z0-9])`, returned upper-cased. A bare "Zkratka" without the rest of the label is **not** a label.
   - Login: unlabelled, because its shape is unique: `(?<![A-Za-z0-9_\-])(uby-t?ws_?[A-Za-z0-9]{5,6})(?![A-Za-z0-9_\-])`, kept only if `validation._WS_USER_RE.fullmatch` passes. It is returned as written in the letter (case kept).
4. **One answer or none, per field:**
   - Exactly one distinct value (the same value repeated counts once; compare the mark and login case-insensitively): `found`, with the 1-based line number and the label text of the **first** occurrence.
   - Two or more distinct values: `ambiguous`, with their line numbers. **No value**, not even the first.
   - A label is present but no valid value follows it (15 digits, spaces inside, a letter inside, the value two lines down): `unreadable`. This wins over a valid match elsewhere: if one `IDUB` label is unreadable and another reads fine, the result is `unreadable`, and nothing is filled.
   - Nothing found: `missing`.
5. **Password guard:** a login candidate on a line that also contains `heslo`, `password` or `passwort` (any case), or on the line directly after such a label with nothing after it, makes the login `ambiguous`. The parser has no password field and never returns any text other than the three values and their line numbers.
6. **No cross-guessing:** the zkratka is never derived from the login inside the parser. The existing save still derives it on save when the field is empty (`_apply_police_defaults`, `routes/admin.py:1803`). That is unchanged.
7. `LetterResult` is a frozen dataclass: `status`, and `fields: dict[str, FieldResult]` keyed `uby_idub`, `uby_mark`, `uby_ws_user`. `FieldResult(state, value, line, label, lines)` where `state` is one of `found missing ambiguous unreadable`, `value` is `""` unless `found`, and `lines` is a tuple of ints.
8. A second function, `confirmed_fields(form) -> tuple[list[str], list[str]]`, returns (listed, unconfirmed). It reads the hidden `letter_fields` (comma list; keep only the three names above, ignore anything else, de-duplicate) and, for each name, whether `letter_ok_<name> == "1"` was posted. Pure: it takes any mapping with `.get`.

### The connection test is read-only (verified on f1ca4288)

- `routes/admin.py:3373-3416` `test_connection`: it saves typed values through `_save_apartment_form` (`:3383`), then calls only `client.test_availability` (`:3391`), `client.max_batch_size` (`:3392`) and `client.code_list` (`:3412`). After that it runs `billing_trial.mark_verified` (`:3406`, an `UPDATE` of `ubyport_verified_at` only, `billing_trial.py:94-99`) and `alerts.resolve` (`:3407`, an `UPDATE alert`).
- `ubyport/client.py:174-194`: those three methods send only `TestDostupnosti`, `MaximalniDelkaSeznamu` and `DejMiCiselnik`. Filing is only `submit` (`client.py:196`, `ZapisUbytovane` at `:206`), and nothing on the test path calls it. `_save_apartment_form` (`routes/admin.py:2711`) calls no `reporting.submit_*`.
- **Known and unchanged:** once correct details are saved, the regular sweep may file guests that were already waiting (G1, owner decision 2). That is the point of entering details. It is a separate path, the same as on main for any save. Do not change it.

### Flow (works without JavaScript, rule 6)

- **Paste form outside the big form:** `#property-settings-form` runs from line 139 to line 431, and forms cannot nest. Add a new `<form id="police-letter-form" method="post" action="{{ base_url }}/police-letter">` with only `_csrf`, placed directly after line 431's `</form>`. Inside the `#ubyport` card, the textarea and its button use `form="police-letter-form"`, so they post only the letter and the token, and the unsaved guard (`app.js:2237-2252`, per form) ignores them.
- **New route** `POST /apartments/{apartment_id}/police-letter` in `routes/admin.py`, on the same `router` (CSRF via `security.protect_host_post`, `admin.py:87`). It calls `auth.require_login`, then `access.apartment` (a property of another host, or a missing one, gets `_back("/apartments", err=no_such_apartment)` and nothing is parsed). It reads `letter_text`, calls `parse_letter`, and renders the page with `_render_property_detail(apartment_id, request, extra={...})` (`admin.py:2211`), status 200, header `Cache-Control: no-store`. It writes **nothing**: no `db.update`, no audit with values, no session, no flash. Optionally one `db.audit("police_letter_read", f"apartment={id} found=<comma names>")` with field **names** only. The text is never echoed: the textarea comes back empty.
- **`extra`** carries `letter_check` (the result) and whatever opens `#sec-police` and the settings view (read `_property_view_state`; `inline_flash_section="police"` opens the details, template line 301). Confirm in the browser that the card is visible on the returned page.
- **Pre-fill:** in the template, each of the three `text_field` calls uses the found value when `letter_check` has one, else the saved value. Password: always the existing empty input.
- **Check-answers card** at the top of `#ubyport`, rendered only when `letter_check` is set, **inside** the big form. Heading "Check what we found". One row per field, in the order IDUB, short name, login, password:
  - `found`: the field's label, the value in the mono token style, the source "Line 7, after “IDUB:”", "Saved now: X" when the property already has a different saved value, and a checkbox `letter_ok_<field>` value `1`, `required`, label "Matches my letter".
  - `missing`, `ambiguous` or `unreadable`: one line in plain words (keys below). No checkbox, and the field keeps the saved value.
  - Password row: always "Type it yourself".
  - Hidden `letter_fields` = comma list of the `found` names, and `letter_line_<field>` = the line number, so a refused save can rebuild the card.
  - The card has **no button** (rule 5). The existing "Save and test connection" button (line 340) and the form's one Save are the actions.
- **Confirm on save (server, both save paths):** at the start of `_save_apartment_form`, right after the apartment is found, `listed, unconfirmed = police_letter.confirmed_fields(form)`. If `unconfirmed`, nothing is saved: return `_refuse_apartment_save(...)` (`admin.py:2240`) with a new keyword `letter_unconfirmed=unconfirmed`. It re-renders the posted values, rebuilds `letter_check` from the form (values from the posted inputs, lines from `letter_line_*`), and adds one `_save_error("police", "letter_ok_<first>")` plus the error text under each unticked box. This also covers the "Save and test connection" button, which has `formnovalidate`, so HTML `required` alone is not enough.
- **Automatic test after the save:** move the test body of `test_connection` (from `client = reporting.client_for(apartment)` to the code-list refresh, lines 3390-3415) **verbatim** into `async def _run_connection_test(request, apartment_id, apartment) -> bool`. `test_connection` calls it and keeps its exact flashes. In `apartment_update` (`admin.py:2472`), after a successful save, when `listed` is not empty:
  - no stored password (`not apartment["uby_ws_password_enc"]`): `_back(return_to, msg=flash.apartments.letter_no_password)`
  - test passed: `msg=flash.apartments.letter_test_ok`
  - test failed: `err=flash.error.letter_test_failed`
  The return target is the same one `apartment_update` uses now, with `#ubyport`. In `test_connection`, keep today's flashes; only the confirm check (above) is new on that path.

### Copy (rule 9; host languages are `en cs vi`, `host_i18n.py:17`)

`en` and `cs` go in `_INTERFACE_STRINGS` (beside `apartment.form.ubyport.*`, `host_i18n.py:4549` and `:5394`); the flash keys go beside `flash.apartments.connection_ok` (`:783`, `:2929`) and `flash.error.connection_failed` (`:917`, `:3063`). `vi` goes in `App/app/host_vi_i18n.py` with the same keys and placeholders (`test_host_i18n.py:156` checks them). Translate `vi` in the tone of its neighbours (`host_vi_i18n.py:1906-1910`). The legend reuses the existing labels `apartment.form.ubyport.idub_label`, `apartment.form.ubyport.mark_label`, `automation.login` and `automation.password`. Do not repeat the IDUB or zkratka hints.

| Key | en | cs |
|---|---|---|
| `police_letter.find_title` | Where do I find these? | Kde to najdu? |
| `police_letter.figure_title` | Drawing of a police letter with the values marked | Nákres dopisu od policie s vyznačenými údaji |
| `police_letter.by_hand` | Type it yourself | Napište ho sami |
| `police_letter.paste_title` | Paste the letter text | Vložit text dopisu |
| `police_letter.paste_label` | Text of the police letter | Text dopisu od policie |
| `police_letter.paste_help` | UbyHost reads the text once on its own server and does not keep it. It picks out the IDUB, the short name and the login. It never reads the password. | UbyHost text jednou přečte na vlastním serveru a neuchová ho. Vybere z něj IDUB, zkratku a přihlašovací jméno. Heslo nikdy nečte. |
| `police_letter.read_button` | Read the letter | Přečíst dopis |
| `police_letter.check_title` | Check what we found | Zkontrolujte, co jsme našli |
| `police_letter.source` | Line %(line)s, after “%(label)s” | Řádek %(line)s, za „%(label)s“ |
| `police_letter.saved_now` | Saved now: %(value)s | Teď uloženo: %(value)s |
| `police_letter.confirm` | Matches my letter | Souhlasí s dopisem |
| `police_letter.missing` | Not in the text. Type it from the letter. | V textu není. Opište ho z dopisu. |
| `police_letter.ambiguous` | Different values on lines %(lines)s. Type the right one yourself. | Různé hodnoty na řádcích %(lines)s. Opište tu správnou sami. |
| `police_letter.unreadable` | Line %(line)s could not be read safely. Type it from the letter. | Řádek %(line)s nejde spolehlivě přečíst. Opište ho z dopisu. |
| `police_letter.empty` | Paste the letter text first. | Nejdřív vložte text dopisu. |
| `police_letter.too_long` | This is longer than one letter. Paste only the letter. | Text je delší než jeden dopis. Vložte jen dopis. |
| `police_letter.confirm_missing` | Tick “Matches my letter”, or change the value. | Zaškrtněte „Souhlasí s dopisem“, nebo hodnotu změňte. |
| `flash.apartments.letter_test_ok` | Saved. The police accepted the login, so the details work. | Uloženo. Policie přihlášení přijala, údaje fungují. |
| `flash.error.letter_test_failed` | Saved, but the police did not accept the login. Check the login and password, then test again. | Uloženo, ale policie přihlášení nepřijala. Zkontrolujte jméno a heslo a otestujte znovu. |
| `flash.apartments.letter_no_password` | Saved. Type the password from the letter, then test the connection. | Uloženo. Napište heslo z dopisu a otestujte spojení. |

### Picture

A new partial `App/app/templates/_police_letter_figure.html` with an inline `<svg viewBox="0 0 320 220" role="img" aria-labelledby="pl-fig-t">` and a `<title id="pl-fig-t">` (`figure_title`). It shows a sheet, grey bars for the letterhead and the body text (no crest, no logo, no address), and four lines in Czech, as the letter is Czech: `IDUB: 000000000000`, `Zkratka ubytovacího zařízení: ABCDE`, `Uživatelské jméno: UBY-WS_ABCDE`, `Heslo: ••••••••`. Each line has a numbered circle 1 to 4. Under the SVG an `<ol>` maps 1 to 4 to the four field labels; item 4 adds `by_hand`. Colours only through classes in `host.css` that use `tokens.css` variables. No `style=""`, no `<style>`, no raw hex (design rule 2). Text in the SVG uses `font-family: inherit` via the class. The SVG scales to the card width (`width: 100%; height: auto`, max 360 px) and never scrolls sideways at 390 px.

### Layout inside `#ubyport` (copy the closest existing pattern; MASTER section for details and help)

Order: the existing head row and `.ui-sub` lines (unchanged; the `#police-sample-link` stays where it is, because `test_ubyport_sample_pdf.py:194` and `test_reporting_help_0097.py:87` pin it), then `<details class="police-letter-find">` (summary `find_title`, the figure), then `<details class="police-letter-paste">` (summary `paste_title`, label `paste_label` with `help_tip('police-letter-help', t('police_letter.paste_help'))` on the label line, textarea `name="letter_text" form="police-letter-form" rows="6" maxlength="20000" autocomplete="off" spellcheck="false"`, button `ui-btn ui-btn-secondary` "Read the letter", `type="submit" form="police-letter-form"`), then the check-answers card (only with `letter_check`), then the existing fields. On the returned page both `details` are closed and the check-answers card is shown. `empty` or `too_long` shows its line inside the open paste `details`, as an error under the textarea. No card inside a card: the two `details` and the check-answers card are plain blocks in the `#ubyport` panel, separated by the spacing tokens (12 px minimum, rule 3).

### Privacy and rules

No new column, cookie, script, outbound request or dependency. No migration. The pasted text lives only in the request: not stored, not logged, not echoed, so it needs no retention line (rule 2). The response is `no-store`. The repo is public: test letters use made-up values (`000011112222`, `ABCDE`, `UBY-WS_ABCDE`), never real ones.

### Anchors (verified on f1ca4288; re-check each with `grep -nF`)

1. `App/app/templates/_property_editor.html:305` `    <section class="panel property-section ui-section" id="ubyport">`
2. `_property_editor.html:311` `{{ text_field('uby_idub', t('apartment.form.ubyport.idub_label'), apartment.uby_idub,`; `:314` `{{ text_field('uby_ws_user',`; `:332` `{{ text_field('uby_mark',`
3. `_property_editor.html:340` `<button class="ui-btn ui-btn-secondary" type="submit" formaction="{{ base_url }}/test-connection"`; `:431` `</form>` (the end of `#property-settings-form`, opened at `:139`)
4. `App/app/routes/admin.py:3373` `@router.post("/apartments/{apartment_id}/test-connection")`; `:3390` `    client = reporting.client_for(apartment)`; `:3416` `    return _back(return_to, msg=_flash(request, "flash.apartments.connection_ok"))`
5. `admin.py:2711` `def _save_apartment_form(`; `:2240` `def _refuse_apartment_save(`; `:2211` `def _render_property_detail(`; `:2472` `@router.post("/apartments/{apartment_id}")`
6. `App/app/ubyport/client.py:174` `    def test_availability(self) -> bool:`; `:196` `    def submit(`
7. `App/app/validation.py:1010` `_WS_USER_RE = re.compile(`
8. `App/app/templates/base.html:33` `host.css?v=20261108-1010a`; `App/tests/static_versions.json:114` `"host.css": {`

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/police_letter.py` | create | `parse_letter`, `confirmed_fields`, dataclasses (section 2) |
| `App/app/routes/admin.py` | edit | new route; `_run_connection_test` (moved verbatim); confirm check in `_save_apartment_form`; `letter_unconfirmed` in `_refuse_apartment_save`; auto test in `apartment_update` |
| `App/app/templates/_property_editor.html` | edit | the two `details`, check-answers card, pre-fill, `#police-letter-form` after line 431 |
| `App/app/templates/_police_letter_figure.html` | create | the SVG and legend |
| `App/app/static/host.css` | edit | classes for the figure, the two `details` and the card, tokens only |
| `App/app/templates/base.html` | edit | `host.css` cache key `?v=20261110-1083` |
| `App/tests/static_versions.json` | regenerate | only with `tests/test_static_versions.py --write` |
| `App/app/host_i18n.py` | edit | `en` and `cs` keys (section 2 table) |
| `App/app/host_vi_i18n.py` | edit | the same keys in `vi` |
| `App/tests/test_police_letter_parser.py` | create | parser table (step 2) |
| `App/tests/test_police_letter_flow.py` | create | route, confirm, auto test, read-only proof (step 5) |
| `App/tests/test_host_police_letter_browser.py` | create | browser, no-JS, geometry, screenshots (step 7) |
| `docs/tasks/screenshots-1083/` | create | PNGs (step 7) |
| `docs/tasks/1083-report.md` | create | report, plus `Status: review` here |

## 4. Steps (commit after each: `1083 step k`)

1. Confirm anchors 1 to 8 with `grep -nF`. If one is missing, STOP. Read `_property_view_state` (grep it, read 40 lines) and `_refuse_apartment_save` (`admin.py:2240-2290`) and nothing else in admin.py beyond the anchors.
2. Create `police_letter.py` exactly per section 2 "Parser rules". Then write `test_police_letter_parser.py` as one `@pytest.mark.parametrize` table of at least 45 rows `(id, text, expected_states_and_values)`, covering at least:
   - Clean letter: all three found, right lines. The same with `\r\n`. The same with NBSP after the colon. Label in lower case (`idub:`) and upper case.
   - Value on the next line after `IDUB:`: found. Value two lines down: `unreadable`.
   - 11 digits, 15 digits, `1234 5678 9012`, `12345678901O` (letter O), `12345678901l`, full-width digits, `12345678901²`: `unreadable`, no value.
   - Trailing period or comma after a valid IDUB: found. IDUB inside a longer word (`XIDUB: …`): not a label, `missing`.
   - The same IDUB twice: found. Two different IDUBs: `ambiguous`, lines listed, value `""`. One readable and one unreadable IDUB: `unreadable`.
   - Extra unlabelled 12 to 14-digit numbers (a phone number, a reference number, a date run `20261110120000`, a bank number): ignored. IČO `12345678` near the IDUB: ignored.
   - Zkratka with and without diacritics (`ubytovaciho zarizeni`), label split over a line break, mixed case, value in lower case (returned upper case), 4 and 7 characters (`unreadable`), a value with `Č` (`unreadable`), a bare `Zkratka: ABCDE` (`missing`), two different marks (`ambiguous`).
   - Login: `UBY-WS_ABCDE`, `uby-ws_abcde1`, `UBY-WSab12cd`, `uby-tws1ab45` found as written. `UBY-WS_ABCD` and `UBY-WS_ABCDEFG`: missing. `ub1234567` (the web-form login): missing. Two different logins: ambiguous. The same login in two cases: found once. A login on a `Heslo:` line: ambiguous.
   - The password never comes out: a letter with `Heslo: Zz9!fake-pass` and `Password: Zz9!fake-pass`. Assert the string appears in no field of the result (`repr(result)`).
   - OCR-like noise: stray `|`, `_`, doubled spaces, a page footer `Strana 1 z 2`, a soft hyphen, Czech text all round (`Vážený pane, přidělujeme …`). Expected values unchanged.
   - Empty, only spaces, exactly 20000 characters (`ok`) and 20001 characters (`too_long`, empty `fields` or all `missing`).
   - Purity: the same input twice gives equal results; a test that monkeypatches `socket.socket` to raise still passes a full parse.
   Then a `confirmed_fields` table: unknown names ignored, duplicates folded, `letter_ok_x=0` counts as unconfirmed.
3. Copy: add the section 2 keys in `en`, `cs`, `vi`. Run `test_host_i18n.py`.
4. Template and CSS per section 2 (picture partial, two `details`, card, pre-fill, separate form). Bump the `host.css` key (anchor 8) to `20261110-1083`, then from `App/` run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30`. Its diff must touch only the `host.css` entry. If you edit `host.css` again later, bump the key again to `20261110-1083b` and rerun.
5. Routes per section 2. Then write `test_police_letter_flow.py`. Model the fixtures on `test_property_form_save.py` (read its first 80 lines only):
   a. POST `/police-letter` with a clean synthetic letter: 200, `no-store`, the three inputs carry the found values, three `letter_ok_*` checkboxes, a password row and no password value. The pasted text (use a unique marker line) is absent from the HTML. The apartment row (`SELECT *`) is byte-identical before and after, and no `audit` row contains the IDUB, the login or the marker.
   b. Ambiguous and unreadable letters: the field keeps the saved value, with no checkbox, and the right line is shown.
   c. No `_csrf`: refused as for other host posts, nothing parsed. Logged out: login redirect. Another host's property: no parse, nothing in the page.
   d. Save with `letter_fields=uby_idub,uby_mark` and only one tick: nothing saved (row unchanged), status 400, both values still in the inputs, the error under the unticked box. The same through `/test-connection`, which must not even call the client (monkeypatch `reporting.client_for` to raise).
   e. Save with all ticks, password stored, client monkeypatched OK: values saved, flash `letter_test_ok`. Client raising `UbyportAuthError`: values saved, flash `letter_test_failed`. No stored password: `letter_no_password`, and the client is not called. A save without `letter_fields`: exactly today's flash, and no test is run.
   f. **Read-only proof:** seed a property with a stay and a reportable guest that is not yet sent. Monkeypatch `UbyportClient.submit`, `reporting.submit_for_apartment`, `reporting.submit_batch` and `reporting.submit_stay_if_complete` to raise `AssertionError`. Monkeypatch `UbyportClient._post` to record `method` and return `""`, with `soap.parse_scalar_response` returning `"true"` and `soap.parse_ciselnik_response` returning `[]`. Run both `/test-connection` and the letter save with the auto test. Assert the recorded methods are a subset of `{"TestDostupnosti", "MaximalniDelkaSeznamu", "DejMiCiselnik"}`, the guest's `submit_state` is unchanged, and no submission row was added. Add a source pin: the body of `_run_connection_test` and of `test_connection` contains no `submit` and no `ZapisUbytovane`.
   g. Idempotency: the same confirmed save posted twice gives one apartment row with the same values, and the second test runs again harmlessly. Concurrency: two threads with two clients save letter values for **two different** properties of one host at the same moment; each row ends with its own IDUB, and neither has the other's.
6. Run the section 6 non-browser commands.
7. `test_host_police_letter_browser.py`, modelled on `test_0833_property_editor_browser.py` (its imports and fixtures, first 60 lines), `@pytest.mark.parametrize("width", [390, 768, 1280])`:
   a. Open the property settings, Reporting & fees. Open "Where do I find these?": the SVG is visible, `scrollWidth <= innerWidth`, its box is inside the card. Paste a synthetic letter, click "Read the letter": the check-answers card shows, inputs pre-filled, password empty.
   b. Click Save with no ticks: the browser blocks (`required`). Tick all, type a password, click "Save and test connection" with a mock UbyPort (the mock server or a monkeypatched client as the e2e tests do): flash in plain words.
   c. No JavaScript (`java_script_enabled=False`): the same paste, check and confirmed save work, and the refusal on a missing tick shows.
   d. Geometry: 12 px minimum between the two `details`, the card and the fields (`Guest.check_spacing`, or the host equivalent from the model file). No overlap. The textarea fills the column on the phone. The focus ring is visible on the checkbox.
   e. Screenshots into `docs/tasks/screenshots-1083/`: `find-{390,768,1280}.png` (picture open) and `check-{390,768,1280}.png` (check-answers card). Look at each once, and write one line per file in the report.
8. UX gate (rule 10): run `test_layout_lint_browser.py` green (no new `ALLOW` entry), then open its 390, 768 and 1280 shots of the property settings page with Reporting open. Fill in the [design-system](../design/design-system.md) section 5 checklist in the report and, later, in the PR.
9. Run section 6 in full, then write the report.

## 5. Do not touch

`validation.py`, `reporting.py` (beyond reading `client_for`), `ubyport/*`, `submit_*`, `deadlines.py`, `billing_trial.py`, `alerts.py`, `codelists.py`, the onboarding wizard police step and its templates, guest templates, `db.py`, migrations, any dependency, `#police-sample-link` and the sample PDF. The test path keeps its existing calls and order (moved verbatim). Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`)

From `App/`: `.venv/bin/python -m pytest tests/test_police_letter_parser.py tests/test_police_letter_flow.py tests/test_property_form_save.py tests/test_property_operator_defaults.py tests/test_flash_next_step.py tests/test_property_hub.py tests/test_remove_legacy_actions.py tests/test_ubyport_sample_pdf.py tests/test_reporting_help_0097.py tests/test_host_i18n.py tests/test_static_versions.py -q --tb=short -x`. Filing row (test-map): `.venv/bin/python -m pytest tests/test_ubyport_*.py tests/test_police_*.py tests/test_endtoend.py tests/test_submission_*.py -q --tb=short -x`. Browser, 0 skipped: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_police_letter_browser.py tests/test_0833_property_editor_browser.py tests/test_property_navigation_browser.py tests/test_host_geometry.py tests/test_layout_lint_browser.py -q --tb=short -rs`. Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] The parser fills a field only for exactly one valid, labelled (or, for the login, well-formed) value. Two values or an unreadable label fill nothing. No repair, no NFKC, digits-only IDUB. The table has at least 45 rows, all green.
- [ ] The password is never extracted, echoed or pre-filled. The pasted text is not stored, logged or echoed. The response is `no-store`. No outbound request.
- [ ] Nothing saves until each pre-filled value is ticked, on both the Save and the "Save and test connection" path, with or without JavaScript.
- [ ] After a confirmed letter save the test runs automatically, with a plain-words result. Saves without letter values behave exactly as on main.
- [ ] Read-only proof test green: only `TestDostupnosti`, `MaximalniDelkaSeznamu` and `DejMiCiselnik` are sent, no guest changes state, and there is no submission.
- [ ] Copy in `en cs vi`. The picture has no real data, crest or logo. Tokens only, no `style=""`.
- [ ] Browser tests 0 skipped at 390, 768 and 1280. Layout lint green with no new `ALLOW`. Six screenshots. Design-system checklist ticked.
- [ ] `git diff --stat origin/main` touches only section 3 files.

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; the test path calls anything beyond the three read-only methods; the change needs `validation.py`, `reporting.py`, a migration or a dependency; the check-answers card cannot be shown on a 200 re-render without JavaScript; a browser test skips; a test fails twice on the same cause (attempt 3 of 3); 25 tool calls or 60k tokens (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to n.`).

## 9. Report

`docs/tasks/1083-report.md`, 600 tokens at most: files changed, each command with its last 5 lines, section 7 ticked, one line per screenshot on what you saw, layout-lint result per width, the design-system checklist, deviations, questions. Set this brief `Status: review`. After the strict fresh Fable diff review (filing safety, parser, UX), open one PR. Body: filing path untouched, connection test read-only (with the test name), pasted text not stored, no new request, field or dependency, plus the UX-gate lines per page. Merge only with `scripts/merge-pr-on-green.sh`.

## 10. Open questions (not blocking)

- **Q1:** `_IDUB_RE` allows letters, but the hint says numbers. The parser takes digits only (the safe side). If a real IDUB ever has a letter, the host types it, and nothing breaks.
- **Q2:** the exact label wording of every police letter variant is unknown. Only `IDUB` and the full "Zkratka ubytovacího zařízení" are labels. A variant label means `missing`, and the host types it. Widen only with a real (redacted) sample from the owner.
