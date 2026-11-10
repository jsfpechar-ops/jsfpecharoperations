# 1085: G6 police letter, part 2 of 3: the paste, check and confirm flow, and the automatic connection test

Status: todo
Tier: A | Depends on: 1083 (merged, PR #877) and **1088** (parser hardening, `FieldResult.source`; merge it, or merge main after it lands, before step 1) | Base commit: 71448224 (origin/main) | Branch: claude/1085-police-letter-flow
Executor: Fable 5.2 (owner tier override in decisions.md) | Attempts: 3 at most | Fits one session: stop at 60 tool calls or 60k tokens (section 8); reads stay at 150 lines or fewer
Review: an extremely strict fresh Fable diff review (owner's words) before the PR opens, on filing safety, privacy and the no-JavaScript flow.
Report: docs/tasks/1085-report.md

## 1. Objective

Plan [speed-and-ease](../plans/speed-and-ease.md) G6, part 2. It wires the 1083 parser into the property editor, in section "Reporting & fees", card `#ubyport` (`_property_editor.html:305-342`). It adds:

1. A folded **"Where do I find these?"** card with a drawn, generic picture of the web-service letter, with the real labels and fake values.
2. A folded **"Paste the letter text"** box. The server parses the text (1083's `parse_letter`, hardened by 1088) and does not store it.
3. **Check answers:** the values come back pre-filled and **not saved**. Each value shows the exact source line from the pasted text, the plain words "Check this against your letter", and its own "Matches my letter" tick. The save is refused until every pre-filled value is ticked.
4. **Automatic connection test after the save, but only when the host typed a password in that same save** (lockout guard). It is a **new automatic outbound trigger** (rule 2): a letter save with a typed password now sends the three read-only test calls to the police endpoint without a separate click. The result is in plain words, with a different message for "the login was refused" and "the service could not be reached".

Part 3 (1086) adds the browser tests, the screenshots and the UX gate on top of this branch. This brief has no browser test.

**Tier A, filing HIGH RISK:** a wrong value means filings under the wrong account. Nothing saves without the tick; the test never files.

## 2. Context

### The connection test is read-only (verified on f1ca4288)

- `routes/admin.py:3373-3416` `test_connection`. It saves typed values through `_save_apartment_form` (`:3383`), then calls only `client.test_availability` (`:3391`), `client.max_batch_size` (`:3392`) and `client.code_list` (`:3412`). After that it runs `billing_trial.mark_verified` (`:3406`, one `UPDATE` of `ubyport_verified_at`, `billing_trial.py:94-99`) and `alerts.resolve` (`:3407`).
- `ubyport/client.py:174-194`: those three methods send only `TestDostupnosti`, `MaximalniDelkaSeznamu` and `DejMiCiselnik`. Filing is only `submit` (`client.py:196`, `ZapisUbytovane`). `_save_apartment_form` (`admin.py:2711`) calls no `reporting.submit_*`.
- **Unchanged:** once the details are right, the regular sweep may file guests that were already waiting (G1, owner decision 2), exactly as after any save on main.
- **Lockout guard:** an empty password field keeps the stored password (`admin.py:2866-2878`). An automatic test with a new login and an old password could fail again and again, and the police may lock the account. So the auto test runs **only** when `_form_str(form, "uby_ws_password")` is not empty in the same post, at most once per save, with no retry.
- **The same guard on `/test-connection`:** when `uby_ws_user` is in `listed` (from `confirmed_fields`), the posted login differs (case-insensitive, stripped) from the login saved **before** this post, and no password is posted, the route saves as usual but **skips the test**. It redirects with `msg=letter_new_login_no_password`. Read the saved login before `_save_apartment_form` runs. In every other case `test_connection` behaves as today.

### The parser on main (1083, PR #877; read `App/app/police_letter.py`, final rules in `docs/tasks/1083-police-letter.md` rule 12)

- Exports: `parse_letter(text) -> LetterResult`, `confirmed_fields(form) -> (listed, unconfirmed)`, `line_from_form(form, name) -> int | None`, `FIELDS = ("uby_idub", "uby_ws_user", "uby_mark")`, `FILLED_STATES = {"found", "derived"}` and `MAX_LETTER_CHARS = 20000`. None of them raises on any input.
- `LetterResult(status, fields)`: `status` is `ok`, `empty` or `too_long`. `FieldResult(state, value, line, label, lines)`.
- **States as built:**
  - IDUB and login: `found`, `missing`, `unreadable` (zero or several candidates in the whole text, or a wrapped value) or `ambiguous` (a password word on the lines from the label to the value)
  - Short name: only `derived` (from a `found` login, through `mark_from_ws_user`, with the login's `line` and `label`), `missing`, or `conflict`
  - A zkratka word in the text that differs from the derived mark makes the login **and** the mark `conflict`
- **A printed mark is never the value.** The flow has no "printed mark found" case. The short-name row is either the derived value (from the login) or a plain line.
- 1088 adds `FieldResult.source: tuple[str, ...] = ()` as the last field: the exact label-to-value slices, each 120 characters at most, at most two strings, never a password (text before a label makes it `unreadable`). This brief only reads it.

### Turbo and status codes

Turbo 8 runs on host pages (`base.html:44`). It does not render a 200 reply to a form POST; it needs a redirect or a 4xx. So:

- the paste route answers **422** for the check-answers page and for its `empty`, `too_long` and `failed` states
- a refused unconfirmed save answers **400**: add `letter_unconfirmed` to the 400 condition at `admin.py:2320` (`if (operator_error or address_errors or shared_time_error or lock_times_error)`)
- every successful save redirects as today

Without JavaScript, browsers render 422 and 400 pages normally.

### Flow (works without JavaScript, rule 6)

- **A separate form:** `#property-settings-form` runs from line 139 to line 431, and forms cannot nest. Add `<form id="police-letter-form" method="post" action="{{ base_url }}/police-letter">` with only `_csrf`, directly after line 431's `</form>`. The textarea and its button inside `#ubyport` use `form="police-letter-form"`. The unsaved guard (`app.js:2237-2252`) is per form, so it ignores them.
- **Route** `POST /apartments/{apartment_id}/police-letter` on the same `router`, so CSRF comes from `security.protect_host_post` (`admin.py:87`).
  - Call `auth.require_login`, then `access.apartment`; a missing property or another host's gets `_back("/apartments", err=no_such_apartment)` and is not parsed.
  - Read `letter_text`. Call `police_letter.parse_letter` inside `try: … except Exception as exc:`. On an exception, render the `failed` state and log only `type(exc).__name__` with `db.audit("police_letter_failed", f"apartment={id} error={type(exc).__name__}")`. **No traceback may escape:** `main.py:296` `log.exception` would print the pasted text. Afterwards, `del` the text variable.
  - Render through `_render_property_detail(apartment_id, request, extra=…, status_code=422)` (`admin.py:2211`) with the header `Cache-Control: no-store`.
  - It writes nothing else: no `db.update`, no session, no flash. One optional `db.audit("police_letter_read", f"apartment={id} filled=<comma names>")`, with field **names** only.
  - The text is never echoed: the textarea comes back empty.
- **`extra`:** `letter_check` (the `LetterResult`), plus what opens `#sec-police` and the settings view. Read `_property_view_state` (grep it, about 40 lines); `inline_flash_section="police"` opens the details (template line 301).
- **Unsaved edits (JavaScript):** when `letter_check` is shown, `#property-settings-form` gets `data-dirty-start="1"` (extend the existing `{% if operator_error %}` on line 139 to `{% if operator_error or letter_check %}`), so the guard (`recomputeDirty`, `app.js:2230`) warns before the host leaves with unsaved pre-filled values. Add one listener in `app.js`, beside `initUnsavedForms`: on `submit` of `#police-letter-form`, if `#property-settings-form` has `data-dirty="1"` or `#uby_ws_password` has a value, call `window.confirm(form.dataset.discardWarning)`. If the host cancels, `preventDefault()`. Otherwise set `_ubySubmitting` on the big form, so that `beforeunload` does not warn a second time. `#police-letter-form` carries `data-discard-warning="{{ t('police_letter.discard_warning') }}"`. Without JavaScript there is no warning; the 422 page still keeps nothing that was saved. Bump the `app.js` key (`base.html:47`, `?v=20261109-qa3`) to `20261110-1085` and regenerate `static_versions.json`.
- **Pre-fill:** each of the three `text_field` calls (lines 311, 314, 332) shows the letter value when its state is in `police_letter.FILLED_STATES`, else the saved value. The password input never gets a value.
- **Check-answers card:** at the top of `#ubyport`, inside the big form, only with `letter_check`. Heading `check_title`. Rows in the order IDUB, login, short name, password:
  - `found` (IDUB, login) or `derived` (short name): the field label and the value in the mono token style.
    - Next to it, the **exact source**: `source` (the line number), then each string of `FieldResult.source` in a `<code>` (autoescaped, never `|safe`). For `derived`, the login's source, introduced by `source_login`.
    - Then `check_against`, always, for every value.
    - Add `saved_now` when a different value is saved.
    - A checkbox `letter_ok_<field>`, value `1`, `required`, labelled `confirm`.
  - `missing`, `ambiguous`, `unreadable` and `conflict`: one plain line (keys below), with no line text. No checkbox, and the field keeps the saved value.
  - The password row always says `by_hand`.
  - Hidden inputs: `letter_fields` (comma list of the filled names), `letter_line_<field>` (the line number), and `letter_src_<field>_1` and `letter_src_<field>_2`, one per `source` string (the second only for a next-line layout). On a refused save the card shows them again: each read only if it is a `str`, with every control character removed and cut to 120 characters, autoescaped. It is the host's own text, sent back to the host only.
  - The card has **no button** (rule 5). The actions are the existing "Save and test connection" (line 340) and the form's one Save.
- **Confirm on save, on both paths:** at the start of `_save_apartment_form`, right after the apartment is found, call `listed, unconfirmed = police_letter.confirmed_fields(form)`. If `unconfirmed` is not empty, save nothing: return `_refuse_apartment_save(..., letter_unconfirmed=unconfirmed)` (`admin.py:2240`, new keyword, default `None`). It re-renders the posted values and rebuilds the card from the form: values from the posted inputs, lines from `police_letter.line_from_form` (no line text when that gives `None`), and source text from `letter_src_*_1` and `_2`. It adds `_save_error("police", "letter_ok_<first>")` and the `confirm_missing` text under each unticked box, status 400. This also covers "Save and test connection", which has `formnovalidate`.
- **Automatic test:** move the test body of `test_connection` verbatim (from `client = reporting.client_for(apartment)` at `:3390` to the end of the code-list refresh, `:3415`) into `async def _run_connection_test(request, apartment_id, apartment) -> str`. It returns `"ok"`, `"auth"` (caught `UbyportAuthError`, checked **first**, since it subclasses `UbyportTransportError`) or `"unreachable"` (any other `UbyportTransportError` or `UbyportError`). The same audit rows as today in each branch.
  - `test_connection` maps `"ok"` to its existing `connection_ok` and anything else to its existing `connection_failed`, so its behaviour does not change.
  - In `apartment_update` (`admin.py:2472`), **only at its final success exit**, the last `return _back(path + hash_ + fragment, msg=msg)` (after the fee-return and `_setup_after_save` returns, which stay as they are, with no test). **Skip the test whenever `setup_step` is posted** (the wizard), even at that exit. There:
    - `listed` is not empty **and** a password was posted: run the test; `"ok"` gives `msg=letter_test_ok`, `"auth"` gives `err=letter_test_failed`, `"unreachable"` gives `err=letter_test_unreachable`
    - `listed` is not empty and **no** password was posted: no test; `msg=letter_saved_untested`
    - `listed` is empty: exactly today's flash, and no test
  - The return target is `apartment_update`'s usual one, with `#ubyport`.

### Picture: new `App/app/templates/_police_letter_figure.html`

- An inline `<svg viewBox="0 0 320 200" role="img" aria-labelledby="pl-fig-t">` with `<title id="pl-fig-t">` (`figure_title`). It shows a sheet, with grey bars for the letterhead and the body (no crest, logo, address or names).
- The title line `Přihlašovací údaje pro robotické vkládání Ubyport Webová služba` (or a grey bar if it does not fit), then the **real labels** of `ubyport_sample_pdf.py:258-263` with fake values: `Přihlašovací jméno: UBY-WS_ABCDE`, `Přístupové heslo: ••••••••`, `IDUB: 000000000000`. Each line has a numbered circle 1 to 3.
- An `<ol>` under it: 1 the login label (`automation.login`), 2 the password label (`automation.password`) plus `by_hand`, 3 `apartment.form.ubyport.idub_label`. Then one more plain line: `apartment.form.ubyport.mark_label` plus `mark_note`, because the zkratka is usually not printed.
- Colours only through `host.css` classes that use `tokens.css` variables. No `style=""`, no `<style>`, no raw hex. Width 100%, max 360 px, `height: auto`, no sideways scroll at 390 px.

### Layout inside `#ubyport`

- The existing head row and `.ui-sub` lines stay as they are. `#police-sample-link` stays where it is, because `test_ubyport_sample_pdf.py:194` and `test_reporting_help_0097.py:87` pin it.
- Then `<details class="police-letter-find">` (summary `find_title`, the figure).
- Then `<details class="police-letter-paste">`: summary `paste_title`; label `paste_label` with `help_tip('police-letter-help', t('police_letter.paste_help'))` on its line; textarea `name="letter_text" form="police-letter-form" rows="6" maxlength="20000" autocomplete="off" spellcheck="false"`; button `ui-btn ui-btn-secondary` `read_button`, `type="submit" form="police-letter-form"`. The `empty`, `too_long` or `failed` line shows as an error under the textarea, with that `details` open.
- Then the check-answers card, then the existing fields.
- These are plain blocks in the panel (no card in a card). 12 px minimum between them, with spacing tokens.

### Copy (rule 9; host languages are `en cs vi`, `host_i18n.py:17`)

- `en` and `cs` go in `_INTERFACE_STRINGS`, beside `apartment.form.ubyport.*` (en from `:4549`, cs from `:5394`).
- The flash keys go beside `flash.apartments.connection_ok` (`:783`, `:2929`) and `flash.error.connection_failed` (`:917`, `:3063`).
- `vi` goes in `App/app/host_vi_i18n.py`, with the same keys and placeholders (checked by `test_host_i18n.py:156`), in the tone of `host_vi_i18n.py:1906-1910`.
- Do not repeat the IDUB or login hints.

| Key | en | cs |
|---|---|---|
| `police_letter.find_title` | Where do I find these? | Kde to najdu? |
| `police_letter.figure_title` | Drawing of the police web-service letter with the values marked | Nákres dopisu policie k webové službě s vyznačenými údaji |
| `police_letter.by_hand` | Type it yourself | Napište ho sami |
| `police_letter.mark_note` | Usually not printed. UbyHost takes it from the login, and you check it. | Obvykle v dopise není. UbyHost ji odvodí z přihlašovacího jména a vy ji zkontrolujete. |
| `police_letter.paste_title` | Paste the letter text | Vložit text dopisu |
| `police_letter.paste_label` | Text of the police letter | Text dopisu od policie |
| `police_letter.paste_help` | Paste the part of the letter with the IDUB and the login. UbyHost reads the text once on its own server and does not keep it. It never reads the password. | Vložte část dopisu s IDUB a přihlašovacím jménem. UbyHost text jednou přečte na vlastním serveru a neuchová ho. Heslo nikdy nečte. |
| `police_letter.read_button` | Read the letter | Přečíst dopis |
| `police_letter.check_title` | Check what we found | Zkontrolujte, co jsme našli |
| `police_letter.source` | From line %(line)s of your text: | Z řádku %(line)s vašeho textu: |
| `police_letter.check_against` | Check this against your letter. | Zkontrolujte to podle dopisu. |
| `police_letter.source_login` | Taken from the login on line %(line)s: | Odvozeno z přihlašovacího jména na řádku %(line)s: |
| `police_letter.saved_now` | Saved now: %(value)s | Teď uloženo: %(value)s |
| `police_letter.confirm` | Matches my letter | Souhlasí s dopisem |
| `police_letter.missing` | Not in the text. Type it from the letter. | Údaj v textu není. Opište ho z dopisu. |
| `police_letter.ambiguous` | It sits next to the password, so it was not taken. Type it from the letter. | Údaj je u hesla, proto se nepřevzal. Opište ho z dopisu. |
| `police_letter.unreadable` | Could not be read safely from this text. Type it from the letter. | Údaj nejde z tohoto textu spolehlivě přečíst. Opište ho z dopisu. |
| `police_letter.conflict` | The short name and the login do not match. Type both from the letter. | Zkratka a přihlašovací jméno si neodpovídají. Opište obojí z dopisu. |
| `police_letter.empty` | Paste the letter text first. | Nejdřív vložte text dopisu. |
| `police_letter.too_long` | This is longer than one letter. Paste only the letter. | Text je delší než jeden dopis. Vložte jen dopis. |
| `police_letter.failed` | This text could not be read. Type the values from the letter. | Tento text nejde přečíst. Opište údaje z dopisu. |
| `police_letter.confirm_missing` | Tick “Matches my letter” for this value. | U tohoto údaje zaškrtněte „Souhlasí s dopisem“. |
| `police_letter.discard_warning` | Reading the letter reloads this page. Your unsaved changes here, and a typed password, will be lost. | Přečtení dopisu načte stránku znovu. Neuložené změny i napsané heslo se ztratí. |
| `flash.apartments.letter_test_ok` | Saved. The login and password work. | Uloženo. Přihlašovací jméno a heslo fungují. |
| `flash.error.letter_test_failed` | Saved, but the police refused the login. Check the login and the password, then test again. | Uloženo, ale policie přihlášení odmítla. Zkontrolujte jméno a heslo a otestujte znovu. |
| `flash.error.letter_test_unreachable` | Saved. The police service could not be reached just now, so the login was not checked. Test again later. | Uloženo. Policejní služba teď není dostupná, přihlášení se neověřilo. Otestujte později. |
| `flash.apartments.letter_saved_untested` | Saved. Not tested yet, because no password was typed. Type it and test the connection. | Uloženo. Zatím neotestováno, protože nebylo zadáno heslo. Napište ho a otestujte spojení. |
| `flash.apartments.letter_new_login_no_password` | Saved. Type the password to test the new login. | Uloženo. Pro test nového přihlašovacího jména napište heslo. |

### Privacy and rules

- No new column, cookie, script, outbound request or dependency, and no migration.
- The pasted text lives only in the request: not stored, logged or audited. The only echo is the source lines of filled values (each passed the parser's password-word guard), in the reply and in hidden inputs, never the full text. So it needs no retention line (rule 2).
- The responses are `no-store`.
- Test letters use the fake `SAMPLE_*` values or `000011112222` and `UBY-WS_ABCDE`, never real ones.

### Anchors (verified on 24c704fd, main 71448224 merged in; re-check each with `grep -nF`)

1. `App/app/police_letter.py` (on main): `def parse_letter(text: str) -> LetterResult:`, `def confirmed_fields(form)`, `def line_from_form(form, name: str)`, `FILLED_STATES = frozenset({"found", "derived"})`, `class FieldResult:`, `def _mark_conflicts(`, `_LOGIN_TOKEN_RE = re.compile(` and `_SPACED_DIGITS_RE = re.compile(`. If one is missing: STOP.
2. `App/app/templates/_property_editor.html:305` `id="ubyport"`; `:311` `{{ text_field('uby_idub',`; `:314` `{{ text_field('uby_ws_user',`; `:332` `{{ text_field('uby_mark',`; `:340` `formaction="{{ base_url }}/test-connection"`; `:431` `</form>`
3. `App/app/routes/admin.py:3373` `@router.post("/apartments/{apartment_id}/test-connection")`; `:3390` `    client = reporting.client_for(apartment)`; `:3416` `    return _back(return_to, msg=_flash(request, "flash.apartments.connection_ok"))`
4. `admin.py:2711` `def _save_apartment_form(`; `:2240` `def _refuse_apartment_save(`; `:2320` `if (operator_error or address_errors or shared_time_error or lock_times_error)`; `:2211` `def _render_property_detail(`; `:2472` `@router.post("/apartments/{apartment_id}")`; `:2866` `    password = _form_str(form, "uby_ws_password")`
5. `App/app/ubyport/client.py:57` `class UbyportAuthError(UbyportTransportError):`; `:174` `    def test_availability(self) -> bool:`; `:196` `    def submit(`
6. `App/app/main.py:296` `    log.exception("unhandled error on %s", _access_route(request))`
7. `App/app/templates/base.html:33` `host.css?v=20261108-1010a`; `:44` `turbo-8.0.13.js`; `App/tests/static_versions.json:114` `"host.css": {`

Line numbers move after a rebase on main. Trust `grep -nF`, not the number.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/static/app.js` | edit | the discard warning listener only |
| `App/app/routes/admin.py` | edit | the paste route; `_run_connection_test`, moved verbatim; the confirm check; `letter_unconfirmed`; the auto test |
| `App/app/templates/_property_editor.html` | edit | the two `details`, the check-answers card, the pre-fill, `#police-letter-form` |
| `App/app/templates/_police_letter_figure.html` | create | the SVG and its legend |
| `App/app/static/host.css` | edit | classes, tokens only |
| `App/app/templates/base.html` | edit | `host.css` and `app.js` cache keys `?v=20261110-1085` |
| `App/tests/static_versions.json` | regenerate | only with `tests/test_static_versions.py --write` |
| `App/app/host_i18n.py` | edit | the `en` and `cs` keys |
| `App/app/host_vi_i18n.py` | edit | the `vi` keys |
| `App/tests/test_police_letter_flow.py` | create | the flow tests (step 4) |
| `docs/tasks/1085-report.md` | create | the report, plus `Status: review` here |

## 4. Steps (commit after each: `1085 step k`)

1. Merge `origin/main` again if it moved since 71448224. Merge 1088 (or main after it). Confirm `class FieldResult:` holds `source`; if not, STOP. Confirm anchors 1 to 7 with `grep -nF`; if one is missing, STOP. Read `_property_view_state` (about 40 lines) and `_refuse_apartment_save` (about 80 lines), and nothing else in admin.py beyond the anchors.
2. Copy: add the section 2 keys in `en`, `cs` and `vi`, then run `test_host_i18n.py`.
3. Template, figure and CSS per section 2. Bump the `host.css` key **and** the `app.js` key (`base.html:47`, `?v=20261109-qa3`) to `20261110-1085`, then from `App/` run `.venv/bin/python tests/test_static_versions.py --write 2>&1 | tail -30`. Its diff must change only the `host.css` and `app.js` entries. If you edit `host.css` or `app.js` again later, bump that key to `20261110-1085b` and rerun the command.
4. Routes per section 2. Then write `test_police_letter_flow.py`, with fixtures modelled on `test_property_form_save.py` (read its first 80 lines only):
   a. A POST of the official-layout letter (the `SAMPLE_*` values) gives 422 and `no-store`. Each filled row shows its exact source line in a `<code>` and the `check_against` text (count: one per filled value). A source line holding `<b>` comes back escaped. The IDUB and login inputs carry the values; the short name carries `SAMPLE_ZKRATKA` with the `source_login` text; there are three `letter_ok_*` boxes, a password row, and an empty password input. A unique marker line from the paste and `SAMPLE_WS_PASSWORD` are both absent from the HTML. The apartment row (`SELECT *`) is identical before and after, and no `audit` row holds the IDUB, the login, the password or the marker.
   b. Ambiguous, unreadable and conflict letters: the field keeps the saved value, there is no box, and the plain line is shown. `empty` and `too_long`: 422 with their line.
   c. A parser exception (monkeypatch `police_letter.parse_letter` to raise `ValueError(<marker>)`): 422 with `failed`. The marker is absent from the captured logs (`caplog`) and from the audit rows.
   d. No `_csrf`: refused like other host posts, and not parsed. Logged out: the login redirect. Another host's property: not parsed, no values in the page.
   e. A save with `letter_fields=uby_idub,uby_ws_user` and one tick: 400, nothing saved, both values still in the inputs, the error under the unticked box. The same through `/test-connection`, where `reporting.client_for` (monkeypatched to raise) is never called. `letter_line_uby_idub=abc` and `=99999999999`: 400 with no crash, and no line text.
   f. All ticked, with a password posted and the client monkeypatched:
      - OK gives `letter_test_ok`
      - `UbyportAuthError` gives `letter_test_failed`
      - `UbyportTransportError` gives `letter_test_unreachable`
      - **no password posted** but one stored: `letter_saved_untested`, and the client is never called
      - no `letter_fields`: exactly today's flash, and no test
      - `/test-connection` flashes unchanged for ok, auth and transport
   g. **Read-only proof:** seed a property with a stay and an unsent reportable guest. Monkeypatch `UbyportClient.submit`, `reporting.submit_for_apartment`, `reporting.submit_batch` and `reporting.submit_stay_if_complete` to raise `AssertionError`. Patch `UbyportClient._post` to record `method` and return `""`, `soap.parse_scalar_response` to return `"true"`, and `soap.parse_ciselnik_response` to return `[]`. Run `/test-connection` and the auto-tested letter save. Assert:
      - the recorded methods are a subset of `{"TestDostupnosti", "MaximalniDelkaSeznamu", "DejMiCiselnik"}`
      - the guest's `submit_state` is unchanged
      - no submission row was added
      - (source pin) `_run_connection_test` and `test_connection` contain no `submit` and no `ZapisUbytovane`
   h. **Final exit only:** a letter save with a password that also posts `setup_step=police` runs no test (client monkeypatched to raise). A letter save that returns through `fee_return_to` runs no test. **`/test-connection` guard:** `letter_fields=uby_ws_user`, ticked, a new login and no password: saved, the client is never called, flash `letter_new_login_no_password`. The same with a password: tested.
   i. Idempotency: the same confirmed save twice gives one apartment row with the same values. Concurrency: two threads with two clients save letter values for two different properties of one host at the same moment; each row keeps its own IDUB.
   j. Source pin for the discard warning (no browser here; 1086 tests it in the browser): `app.js` holds the `police-letter-form` submit listener with `window.confirm` and `preventDefault`, and the check-answers HTML has `data-dirty-start="1"` on `#property-settings-form` and `data-discard-warning` on `#police-letter-form`.
5. Run section 6, then write the report.

## 5. Do not touch

`police_letter.py` (1088's), `validation.py`, `reporting.py`, `ubyport/*`, `submit_*`, `billing_trial.py`, `alerts.py`, `codelists.py`, `ubyport_sample_pdf.py`, the onboarding wizard police step, guest templates, `db.py`, migrations, any dependency, and `#police-sample-link`. No browser test here (1086). Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`)

From `App/`: `.venv/bin/python -m pytest tests/test_police_letter_flow.py tests/test_police_letter_parser.py tests/test_property_form_save.py tests/test_property_operator_defaults.py tests/test_flash_next_step.py tests/test_property_hub.py tests/test_remove_legacy_actions.py tests/test_ubyport_sample_pdf.py tests/test_reporting_help_0097.py tests/test_host_i18n.py tests/test_static_versions.py -q --tb=short -x`. Filing row: `.venv/bin/python -m pytest tests/test_ubyport_*.py tests/test_police_*.py tests/test_endtoend.py tests/test_submission_*.py -q --tb=short -x`. Host pages row: `.venv/bin/python -m pytest tests/test_host_*.py -q --tb=short -x`. Repo root: `python3 scripts/context_lint.py 2>&1 | tail -30`.

## 7. Acceptance

- [ ] The auto test runs only at `apartment_update`'s final success exit, never with `setup_step`; `/test-connection` skips a new letter login with no password.
- [ ] The discard warning is wired (source pin, step 4j), and the check-answers page starts dirty; 1086 proves it in the browser.
- [ ] Each filled value shows its exact source line and "Check this against your letter". No printed mark is ever filled.
- [ ] Nothing saves until each pre-filled value is ticked, on both the Save and the "Save and test connection" paths; a forged line number never crashes.
- [ ] The auto test runs only with a password posted in the same save, once. It reports ok, refused or unreachable in plain words. Saves without letter values behave as on main.
- [ ] Read-only proof green: only the three read-only methods are sent, no guest changes, no submission.
- [ ] The pasted text and the password are never stored, logged, audited or echoed, even when the parser raises. `no-store`, 422 and 400 as in section 2.
- [ ] The figure uses the real labels with fake values; no crest, logo or real data. Tokens only. Copy in `en cs vi`.
- [ ] `git diff --stat origin/main` touches only section 3 files.

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing (above all anchor 1); the test path calls anything beyond the three read-only methods; 1088 is not merged in; the change needs `police_letter.py`, `validation.py`, `reporting.py`, a migration or a dependency; the check-answers card cannot be shown without JavaScript; a test fails twice on the same cause (attempt 3 of 3); 60 tool calls or 60k tokens (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to n.`).

## 9. Report

`docs/tasks/1085-report.md`, 600 tokens at most: files, each command with its last 5 lines, section 7 ticked, deviations and questions. Set this brief `Status: review`. After the strict fresh Fable review, open one PR as a **draft**. It is a host page, so it stays a draft until 1086 (built on this branch) passes the UX gate. Then the orchestrator marks it ready and merges it, and 1086 is rebased and merged after it. Body: **a new automatic outbound trigger (rule 2): a confirmed letter save with a typed password sends `TestDostupnosti`, `MaximalniDelkaSeznamu` and `DejMiCiselnik` to the police endpoint, the same read-only calls as the test button**; filing path untouched, the connection test is read-only (`test_police_letter_flow.py` step g), the text is not stored, no new field or dependency. Merge only with `scripts/merge-pr-on-green.sh`.

## 10. Open questions (not blocking)

- **Q1:** with no password typed, the save does not test. The host presses "Save and test connection" when ready. That is a deliberate guard against a police lockout.
