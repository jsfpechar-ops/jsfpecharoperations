# 1100: police letter paste fills every box at once, no tick, Discard fix, send-timing hints, "property" labels

Status: todo
Tier: B | Depends on: 1085, 1086, 1096, 1097, 1099 (all on main) | Base commit: 169ee203 (anchors below are at this commit; re-grep by the quoted text) | Branch: claude/1100-police-autofill
Executor: Opus (Tier B) | Attempts: 3 at most | Fits one session: stop at 60 tool calls (section 8); reads stay at 150 lines or fewer
Report: docs/tasks/1100-report.md
Review: the orchestrator checks the diff, the screenshots and the PR notes before the PR opens.

## 1. Objective

The owner (Josef) tested the live setup on 2026-11-11 (screenshots: `/mnt/project-files/reviews/josef-setup-2026-11-11/`, a network mount: open the PNGs only with the Read tool, at most twice). His decisions:

1. **Labels say "property", never "apartment".** Not every host has an apartment. The property name label reads "Name of the property". Change user-visible host labels only, never code identifiers, routes or key names.
2. **No confirm tick.** Remove "These values match my letter" (`letter_ok`) and the server refusal without it. This reverses 1097's one tick (owner decision 2026-11-11). Every value is in its own editable box.
3. **Paste fills at once.** No "Read the letter" click with JavaScript: when the host pastes the letter text, the boxes fill straight away. Without JavaScript, the submit button stays as the fallback.
4. **Fill everything the letter has:** IDUB, web-service login, web-service **password** (visible, not hidden), short name (zkratka), facility name. The letter has no contact line (the sample letter carries none), so contact is not read.
5. **The unsaved-changes "Discard" works.** Stay, Discard and Save in `#unsaved-dialog` all do what they say.
6. **Send timing is clear.** "Hours after completion" shows only when "Automatically, after a delay" is picked (with JavaScript). Each timing option has a one-line hint saying what it is for.

Out of scope (a second brief follows after this merges): the step-by-step setup flow, section-to-section navigation after police, and the Archive row in setup. Do not touch them.

### Orchestrator decisions (2026-11-11)

- **D-a. The "Check what we found" block goes.** Values go straight into the normal input boxes (`uby_idub`, `uby_ws_user`, `uby_ws_password`, `uby_mark`, `uby_name`). A box is its own Edit, so the per-value Edit disclosure, the source `<code>` slices and the tick go with the block. "Saved now: X" (`police_letter.saved_now`) stays as a one-line note under a box whose stored value differs (never for the password). One short status line says what was filled and what to type.
- **D-b. The password is read from the letter**, reversing the 1085 rule "the password is never read". It is still never stored by the read, never logged, never in audit details, never in `repr()`, never in source slices, and the stored password is still never rendered. Only the response to the host's own paste echoes the value it read from the host's own text, with `Cache-Control: no-store`.
- **D-c. Password box is `type="text"`** (owner: do not hide it) with `autocomplete="off" autocapitalize="off" spellcheck="false"`. On a GET it still has no `value` attribute (placeholder dots when one is stored, as today).
- **D-d. Same route, JSON when asked.** `POST /apartments/{id}/police-letter` returns JSON when the request has `Accept: application/json`, else the HTML page as today. No new route.

## 2. Context (verified with grep at 169ee203)

### Parser: `App/app/police_letter.py` (413 lines)
- Docstring lines 1-17 and `parse_letter` docstring (about 339-342) say the password is never read. Update both to D-b.
- `FIELDS = ("uby_idub", "uby_ws_user", "uby_mark")` (line 30). **Keep it exactly.** `tests/test_police_letter_parser.py:774` pins `tuple(result.fields) == FIELDS`.
- `LetterResult` (about line 48): `status`, `fields`. Add two attributes: `password: FieldResult = field(default=_MISSING_DEFAULT, repr=False)` and `facility: FieldResult = field(default=..., repr=False)` (define the default before the class; `repr=False` keeps `repr(result)` free of the password, pinned at parser test 785-795).
- `_PASSWORD_RE` (115), `_has_password_word` (153): the guard that drops an IDUB or login sharing a line with a password word stays as is.
- `_GAP_NEXT` (66), `_GAP_SAME` (64), `_END` (68), `_normalise` (129), `_line_starts` (138).
- `confirmed_fields` (386-400): returns `(listed, unconfirmed)`; 1097 tick logic at 397-399.
- Sample values: `App/app/ubyport_sample_pdf.py` 26-32: `SAMPLE_WS_PASSWORD = "Uk@zKa-H3sl0-FAKE"`, `SAMPLE_FACILITY_LINE1 = "BYT Č. [2] FIKTVNÍ 1234/56 (PRAHA,"`, `SAMPLE_FACILITY_LINE2`. Labels in the letter: `Přístupové heslo:` (261), `Ubytovací zařízení:` (266). The field note at 383: "Facility name, first line only, max 35 chars". Validation limit: `validation.py:1093` (`uby_name: 35`).
- Parser test texts: `tests/test_police_letter_parser.py` 43-80 (`TITLE`, `L_USER`, `L_PW`, `OFFICIAL`, `OFFICIAL_NEXT_LINE`, `FULL_BODY`), the full sample text at about 130-160 (contains `"Ubytovací zařízení:"` then the two facility lines, and the "Poučení" lines with the word "heslo" in prose).

### Routes: `App/app/routes/admin.py`
- `_letter_saved_now` 2295, `_letter_rows_from_result` 2300, `_letter_rows_from_form` 2323.
- Refusal without the tick: `if letter_unconfirmed:` at about 2414-2425 (in `_refuse_apartment_save`), and in `_save_apartment_form` at about 2861-2866 (`_letter_listed, letter_unconfirmed = police_letter.confirmed_fields(form)` then `return _refuse_apartment_save(...)`).
- **Filing safety (keep):** `apartment_update` about 2648-2660: when `letter_fields` is posted (`letter_listed`) and no `setup_step`, a save with no password returns `letter_saved_untested`; with a password it runs `_run_connection_test` once and calls `property_setup.mark_tested` only on `ok`. `test_connection` about 3531-3560: the 1085 lockout guard on `letter_listed`. Both key on the hidden `letter_fields`, **not** on the tick. Filing reads only the stored row: `reporting.client_for` (`reporting.py:1203`, decrypts `uby_ws_password_enc`) and `reporting.py:118` (`uIdub`). A host could always type these values by hand with no tick, so removing the tick adds no new path to filing.
- `police_letter_read` 3607-3651: parses, sets `letter_rows`, `letter_prefill`, `letter_check`, audits names only (`police_letter_read filled=...`), renders 422 with `Cache-Control: no-store`.

### Template: `App/app/templates/_property_editor.html` (618 lines)
- 342-343 `letter_fill`, `letter_names`; 350-360 `details.police-letter-paste` with `textarea#letter_text` (354, `form="police-letter-form"`) and the button `police_letter.read_button` (358).
- 362-394 the check block `#police-letter-check`, hidden `letter_fields` (366), rows (367-388), the tick `#letter_ok` (390-391).
- 395-429 the boxes: `uby_idub` (397), `uby_ws_user` (402), password `#uby_ws_password` `type="password"` (405-416), `uby_mark` (422), `uby_name` (427, `setup.label.facility`), `uby_contact` (428). `{% if 'x' not in letter_shown %}` wrappers hide a box while the check block shows it.
- 431 "Save and test connection" (`formaction="{{ base_url }}/test-connection"`).
- 437-467 `#automation`: `select#automation_mode` (`data-automation-mode data-hours-target="submit_after_hours"`, 442-450, values `manual`, `scheduled`, `immediate`), hours field 452-456 (`automation.hours`).
- 523 `form#police-letter-form` (`data-discard-warning`, hidden `_csrf`).
- 14 and 162: `letter_rows or letter_status` open the police section and pick the start tab. 336 and 345 (`letter_first`, `section_missing`) also test `letter_rows`. 171: `data-dirty-start="1"` is set by `operator_error or letter_check`. Keep all five working: the simplest is to keep setting `letter_rows` in the route; if you switch to a new `letter_filled` flag, change all of 14, 162, 171, 336 and 345 to it. A no-JS read that filled anything **must still render `data-dirty-start="1"`** (the values are not saved yet; 1096).
- The setup wizard has its own copy of the police boxes (`templates/setup_wizard/police.html`, uses `values.*`); brief 1101 will replace it with the partial from P3. Do not edit the wizard in 1100.

### JavaScript: `App/app/static/app.js`
- `syncAutomationHours` 589-597 (today it disables and greys the hours field, it does not hide it), `initAutomationFields` 600-606. `data-automation-mode` is used only in `_property_editor.html` (grep).
- `formSnapshot` / `recomputeDirty` 2222-2234: a form with `data-dirty-start="1"` (1096: a page that loads with prefilled letter values) is **always** dirty, even right after `form.reset()`.
- `initUnsavedForms` 2236-2284 (`beforeunload` at 2272 skips a form only when `_ubySubmitting === true`).
- `initPoliceLetterForm` 2286-2306 (`window.confirm(discardWarning)` on submit). It also scrolls to `#police-letter-check` after a read (2291-2296): that id goes in P3, so point the scroll at `#police-letter-status` instead.
- `initUnsavedDialog` 2429-2568: capture click handler about 2517-2536 (`document.addEventListener("click", ..., true)`); `discardBtn` handler 2546-2551: `dirtyForms().forEach(discard); ... link.click()`.
- Turbo Drive is on for host pages (`base.html:44`, `turbo-8.0.13.js`; `initPage` runs on every `turbo:load`, app.js 2869). `#unsaved-dialog` is a new element after each Turbo visit, so `claimNode(dialog, ...)` passes again and **each visit adds another document capture listener**, each holding its own old `forms` and old `dialog`. `document._ubyOutsideSync` (2478) is set once and keeps the first page's `forms`.
- **Discard root causes to prove (step 5), at least these three:** (1) after `discard()` a `data-dirty-start` form is still dirty (`recomputeDirty` 2232), so `link.click()` re-enters the capture handler, which reopens the dialog; (2) a stale listener from an earlier Turbo page whose detached form still has `data-dirty="1"` (e.g. left by Save) calls `preventDefault()` and then `showModal()` on a detached dialog, which throws, so the link does nothing; (3) a hidden input changed by JS (the new `[data-letter-fields]`) is not restored by `form.reset()` (hidden inputs reset to their changed value), so the snapshot still differs and the form stays dirty. Whatever the tests show is what you fix.
- Dialog markup: `App/app/templates/base.html` 184-193 (`data-unsaved-stay`, `data-unsaved-discard`, `data-unsaved-save`).

### Cache keys and i18n
- `base.html:23` `app2.css?v=20261111-1099f`; `base.html:47` `app.js?v=20261110-1096a`. New: `app.js?v=20261111-1100a`; `app2.css?v=20261111-1100a` only if CSS changes. Then from `App/`: `.venv/bin/python tests/test_static_versions.py --write`.
- Host strings: `App/app/host_i18n.py`. Parity: en and cs (`tests/test_host_i18n.py:57`). `host_vi_i18n.py` falls back to English; you may leave vi untouched, but delete vi keys you delete from en (`police_letter.confirm_all` vi 1928, `police_letter.confirm_missing` vi 1936) so no orphan remains.
- Existing keys used: `police_letter.paste_help` (en 4568, says "It never reads the password": change it), `police_letter.read_button` (4569), `police_letter.confirm_all` (4574), `police_letter.confirm_missing` (4582), `automation.hours` (en 4372, cs 5241), `automation.mode_short.*` (en 8653-8655, cs 8658-8660).

### "Apartment" labels (en, user-visible, host pages)
| Key | en line | new en | cs |
|---|---|---|---|
| `apartment.form.internal_name.label` | 4501 | Name of the property | keep `Název ubytování` |
| `apartment.form.active.label` | 4392 | ...for this property | keep |
| `apartment.form.archive_help` | 4406 | ...unused properties. | keep |
| `apartment.form.blocking_title` | 4422 | This property cannot report to UbyPort yet. | keep |
| `apartment.form.city_en.hint` | 4433 | ...next to the property name... | keep |
| `apartment.form.create` | 4435 | Create property | keep |
| `apartment.form.guest_link.new_help` | 4471 | ...once you save the property. | keep |
| `apartment.form.guest_link.reachback_hint` | 4474 | ...The property link itself only lists upcoming stays... | keep unless cs says "byt/apartmán" |
| `apartment.form.guest_link.window_hint` | 4480 | ...listed on the property link... | cs 5349 "odkazu bytu" -> "odkazu ubytování" |
| `apartment.form.title_new` | 4560 | New property | keep |
| `notification.guest_pin_rotated.detail` | 727 | ...from the property's guest link page... | cs 2880 "u apartmánu" -> "u ubytování" |
| `billing.plan.fact.apartments`, `billing.order.apartments`, `billing.change.apartments_note`, `billing.change.ttlock_line` | 6373, 6390, 6423, 6429 | Properties / per property | cs 6774, 6791, 6824, 6830: "apartmán(y/ů)" -> "ubytování" forms that read naturally |

Leave alone: `customers.actions.*` (operator admin page), guest-guide placeholders ("byt 12" is an example address), message templates, `bsite.step.page`, `onboarding.property.detail` ("byt nebo dům" is correct). Run one more `grep -niP '": [\x27"].*\bapartments?\b' App/app/host_i18n.py App/app/host_design_i18n.py` and `grep -rnP '>[^<{]*\b[Aa]partment' App/app/templates` and list in the report anything left and why. Tests that assert the old English text: grep `Name of the apartment`, `Create apartment`, `New apartment` in `App/tests` and update only the expected text.

## 2b. Design

### P1. Parser: password and facility (pure, no logging)
- **Password.** Label: `p[rř][ií]stupov[eé]\s+heslo|\bheslo\b|\bpassword\b` (case-insensitive, on the `_plain`ed or normalised text as the existing labels are), **followed by a colon**, then the value on the same line or the next line (reuse `_GAP_NEXT`/the colon form; a label with no colon, like "uživatel heslo, může" in the Poučení, is not a label). Value: one token, no whitespace, 6 to 64 printable ASCII characters, followed only by optional spaces/tabs and the line end (`[ \t]*(?=\n|\Z)`). **Do not use `_END` for the password**: `_END` drops a trailing `.`, `,` or `;`, and those can be part of a password; a password is taken whole or not at all. Filled (`state="found"`) only when exactly one distinct value is found; two different values: `ambiguous`; a label with no valid value: `unreadable`; no label: `missing`. A value equal to the found IDUB or login, or one that has the IDUB shape (12 digits) or matches `_WS_USER_RE`: `unreadable` (keeps the module rule "a password that looks like an IDUB or a login fills nothing"). `source=()` always, `line` set. Never put the value in `label`, `lines` or any slice.
- **Facility.** Label at the start of a line (leading spaces allowed), `^[ \t]*Ubytovac[ií][ \t]+za[rř][ií]zen[ií][ \t]*:` (multiline), so prose and `Zkratka ubytovacího zařízení:` never match; then the first non-empty line after the colon (same line if text follows the colon, else the next line), stripped. Filled when it is 1 to 35 characters and exactly one such label exists; longer than 35: `unreadable` (the host types the short form); none: `missing`. NFC as the rest of the text. `source=()`.
- `parse_letter` sets both on `LetterResult(status, fields, password=..., facility=...)`. `FIELDS` and `result.fields` do not change.
- `confirmed_fields(form)`: no tick. Returns `(listed, [])` always. Update its docstring. Keep the signature so callers keep working.

### P2. Route: HTML and JSON (D-d)
`police_letter_read`:
- Builds the same result. `letter_prefill` gains `uby_ws_password` and `uby_name` when filled.
- **HTML (no JavaScript):** renders the page as today (422, `no-store`) with the five boxes prefilled, the hidden `letter_fields` set to the filled names among `FIELDS`, the status line (P3), and the police section open (set `letter_rows`, or replace the template's `letter_rows` checks at 14 and 162 with a `letter_filled` flag; keep `letter_status` errors exactly as today). The password box gets `value="{{ letter_prefill.uby_ws_password }}"` only in this response; every other render (GET, refused save, test-connection result) keeps it with no `value`. The settings form keeps `data-dirty-start="1"` in this response when anything was filled (section 2, line 171).
- **JSON (`Accept: application/json`):** `JSONResponse`, status 200, `Cache-Control: no-store`, body: `{"status": "ok"|"empty"|"too_long"|"failed", "fields": {name: {"state": s, "value": v}}, "filled": [...], "missing": [...], "message": "<status line text>"}` for the five names. Values only for filled states. No source slices, no line text. The same audit line as today (names only; add `uby_ws_password`/`uby_name` names to `filled=` is allowed, the value never).
- Keep the `except Exception` / `del exc` / `del letter_text, form` shape for both branches: a traceback must never carry the text. The login guard, a missing property and an expired CSRF token (`security.ExpiredFormError`) answer with a redirect, not JSON; leave them so, the JS treats any answer that is not `200` with `content-type: application/json` as a failure (P4).
- CSRF: the JS posts `new FormData(letterForm)` (holds `_csrf` and the textarea through `form="police-letter-form"`), so the existing CSRF check applies unchanged. If the CSRF layer refuses a fetch post, STOP.
- Remove the tick refusal: the `if letter_unconfirmed:` branch in `_refuse_apartment_save` and the `letter_unconfirmed` early return in `_save_apartment_form`. Remove `_letter_rows_from_form` if nothing else calls it (grep). Do not change the `letter_listed` code in `apartment_update` or `test_connection`.

### P3. Template: boxes, no check block, status line
- **Reusable partial (for brief 1101's wizard police step).** Move the police credential UI (the paste `details`, the status line, the hidden `letter_fields`, the IDUB, login, password, short-name, facility and contact boxes, and the "Save and test connection" button) out of `_property_editor.html` into a new `App/app/templates/_police_fields.html`, included at the same place with `{% include "_police_fields.html" %}`. Write a Jinja comment at its top naming the variables it reads (`apartment`, `letter_fill`, `letter_status`, `has_password`, `base_url`, `letter_first`, `facility_help` or how it builds it) and the rule that the page must also render the separate `form#police-letter-form` (it cannot sit inside the settings form: no nested forms; the textarea joins it with `form="police-letter-form"`). The partial uses only `data-letter-*` hooks for JS and no id of the surrounding form. The section heads, the sample link, `why.police` and the `#automation` block stay in the editor. Do not include the partial anywhere else yet.
- Delete `#police-letter-check` (362-394), the tick and the `{% if 'x' not in letter_shown %}` wrappers: the five boxes always render. Move the hidden `<input type="hidden" name="letter_fields" value="..." data-letter-fields data-letter-fields-initial="...">` to just above the IDUB box; it always renders (empty value when nothing was read).
- Each box's value: `letter_fill[name] if name in letter_fill else apartment[name]` (password: only `letter_fill`). Under a filled box whose stored value differs, keep the one-line `police_letter.saved_now` note (class `police-letter-note`), not for the password.
- Status line above the IDUB box: `<p class="police-letter-status small" id="police-letter-status" role="status" aria-live="polite" data-letter-status>`, empty on a GET. After a read: `police_letter.filled` "Filled from your letter: %(names)s." plus, when some are missing, `police_letter.type_rest` "Type the rest from the letter: %(names)s." Names are the box labels.
- Paste box: textarea unchanged except a `data-letter-paste` hook. The read button gets `data-letter-read`; it stays in the HTML (no-JS fallback) and `app.js` sets `hidden` on it. Do not use `<noscript>`.
- Password box: `type="text"` (D-c). Keep its `id`, `name`, `aria-*`, hint and help.
- Copy (en / cs, short; rule 9: no sentence the button already says):

| Key | en | cs |
|---|---|---|
| `police_letter.paste_help` (change) | Paste the whole letter. UbyHost fills the boxes below and does not keep the text. | Vložte celý dopis. UbyHost vyplní pole níže a text si neukládá. |
| `police_letter.filled` | Filled from your letter: %(names)s. | Vyplněno z dopisu: %(names)s. |
| `police_letter.type_rest` | Type the rest from the letter: %(names)s. | Zbytek opište z dopisu: %(names)s. |
| `police_letter.read_failed` | Could not read the letter here. Use the button below. | Dopis se tu nepodařilo přečíst. Použijte tlačítko níže. |

Delete `police_letter.confirm_all`, `police_letter.confirm_missing`, `police_letter.check_title`, `police_letter.source`, `police_letter.source_login` in en and cs (and vi) **only if** grep shows no other user. `police_letter.discard_warning` stays (no-JS button path).

### P4. app.js: paste fills at once
In `initPoliceLetterForm`:
- Hide `[data-letter-read]`. On `paste` in `#letter_text`: wait one tick (`setTimeout 0`) and send. On `input`: debounce 600 ms, send when the text has at least 20 characters. Abort an earlier request (`AbortController`).
- `fetch(letterForm.action, {method: "POST", body: new FormData(letterForm), headers: {Accept: "application/json"}, credentials: "same-origin"})`.
- On `status == "ok"`: for each filled name, set the box value (remember `defaultValue` first; show the saved-now note when it differs and the name is not the password), dispatch `input` and `change` (bubbles) so dirty state and the Save row update. Set `[data-letter-fields]` to the filled names among `uby_idub, uby_ws_user, uby_mark`. Write `message` into `[data-letter-status]`. On `empty`/`too_long`/`failed`: show the matching existing text in the status line and do not touch the boxes. On a network error or a non-200: show `police_letter.read_failed` (pass the text in a `data-` attribute) and un-hide the read button.
- A failure is: a network error, a status other than 200, or a `content-type` that is not `application/json` (a login redirect or an expired-form redirect lands as a 200 HTML page after `fetch` follows it). Parse JSON inside `try`.
- Do not overwrite a box the host changed by hand: fill a box only when its value is still its `defaultValue` or the value this reader put there last (keep that in a `data-letter-filled-value` attribute, never for the password, keep that in a closure variable). Remove an earlier JS saved-now note before adding a new one.
- Never move focus; the status line (`role="status"`) announces the result. The textarea keeps its label, and the hidden button stays in the tab order only when visible.
- Find the target form from the boxes (`document.getElementById("uby_idub").form`), not by `#property-settings-form`, so the same code works in the wizard (1101).
- On the target form's `reset` event (Discard and the Save-bar Cancel both call `form.reset()`), set `[data-letter-fields]` back to `data-letter-fields-initial` and remove the JS-added notes: a hidden input is not restored by `reset()`, and a stale `letter_fields` would keep the form dirty and turn a later plain Save into a letter save.
- The submit `confirm` path stays for the visible-button case.
- Never write the letter text or the password to `console`, `localStorage`, `sessionStorage` or a URL.

### P5. Discard fix (root cause first)
Write the test (step 5) and watch it fail. Then fix the cause in `initUnsavedDialog` (expected: after Discard, leaving must not be caught again by the capture handler or `beforeunload`; e.g. mark the forms as leaving (`_ubySubmitting = true`) and go with `window.location.assign(link.href)` instead of `link.click()`, or a `leaving` flag the capture handler checks). For cause (2) in section 2: register the leave-guard click listener once per document (`document._ubyLeaveGuard`, like `_ubyOutsideMark`) and let it read the current `form[data-unsaved-guard]` list and the current `#unsaved-dialog` from the DOM at click time, instead of one listener per Turbo visit with captured `forms`/`dialog`; do the same for `_ubyOutsideSync`. Cause (3) is fixed by P4's `reset` handler. Stay keeps edits and focus; Save submits the dirty form as today. Do not change `recomputeDirty` or the 1096 dirty-start rule.

### P6. Send timing
- `syncAutomationHours`: also set `field.hidden = !scheduled` (keep `disabled`, so a hidden value is not posted). Without JavaScript the field always shows.
- Hours label: new key `automation.hours_delay` en "Hours to wait (delay option only)", cs "Kolik hodin počkat (jen u odeslání s prodlevou)". Use it in the editor only; leave `automation.hours` for other users.
- Hint: under the select, `<p class="hint" id="automation_mode-hint" data-automation-hint>` with the hint of the selected option (server-rendered from `apartment.automation_mode`); each `<option>` carries `data-hint`; the select gets `aria-describedby="automation_mode-hint"`; `initAutomationFields` updates the text on `change`.

| Key | en | cs |
|---|---|---|
| `automation.mode_hint.manual` | You check each guest, then press Send. | Každého hosta zkontrolujete a pak stisknete Odeslat. |
| `automation.mode_hint.scheduled` | Sent on its own after the hours you set, so you have time to check. | Odešle se samo po zadaném počtu hodin, takže máte čas na kontrolu. |
| `automation.mode_hint.immediate` | Sent as soon as the guest finishes the form. | Odešle se, jakmile host dokončí formulář. |

If `automation.timing_help` (the "?") already says the same as a hint, keep the "?" text as is; the hints say what each option is for, the "?" says the ID-check caveat.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/police_letter.py` | edit | P1 |
| `App/app/routes/admin.py` | edit | P2 only: `police_letter_read`, the two tick refusals, `_letter_rows_*` helpers. No other function. |
| `App/app/templates/_property_editor.html` | edit | P3, P6 |
| `App/app/templates/_police_fields.html` | create | P3 partial (police boxes, paste box, status line) |
| `App/app/static/app.js` | edit | P4, P5, P6 |
| `App/app/static/app2.css` | edit only if needed | status line / hidden hours spacing, under `body.v2`, tokens only |
| `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` | edit | labels table, P3, P6 keys (vi: deletions only) |
| `App/app/templates/base.html` | edit | cache keys (lines 23 and 47) |
| `App/tests/static_versions.json` | regenerate | `--write` |
| `App/tests/test_police_letter_parser.py` | edit | P1 tests, tick cases in `confirmed_fields` table |
| `App/tests/test_police_letter_flow.py` | edit | P2/P3 server tests |
| `App/tests/test_host_police_paste_browser.py` | create | P4, P6 browser and no-JS tests, screenshots |
| `App/tests/test_host_unsaved_changes_browser.py` | edit | P5 Stay/Discard/Save tests |
| `docs/context/decisions.md` | append | two lines (step 8) |
| `docs/tasks/screenshots-1100/` | create | PNGs |
| `docs/tasks/1100-report.md` | create | report |

## 4. Steps (commit after each: `1100 step k`)

1. `git fetch origin main && git merge origin/main`. Re-grep every anchor in section 2 by its quoted text (`FIELDS = (`, `def confirmed_fields`, `id="police-letter-check"`, `id="letter_ok"`, `def police_letter_read`, `if letter_unconfirmed:`, `function syncAutomationHours`, `discardBtn.addEventListener`, `app.js?v=`, `app2.css?v=`, `"apartment.form.internal_name.label"`). A missing one: STOP. Read `docs/design/design-system.md` section 1 and 5 (grep headings, read those ranges only).
2. **Tests first (they must fail on unchanged code; put the failing counts in the report):**
   - Parser (`test_police_letter_parser.py`): `OFFICIAL`, `OFFICIAL_NEXT_LINE`, `FULL_BODY` and the full sample text give `result.password.value == SAMPLE_WS_PASSWORD` and `result.facility.value == SAMPLE_FACILITY_LINE1`; the Poučení prose "heslo" is not a label; two different passwords: `ambiguous`; password label without value: `unreadable`; password equal to the IDUB: `unreadable`; a 12-digit or `UBY-WS_...`-shaped password: `unreadable`; a password ending in `.` (e.g. `Ab3x9q.`) is read whole; facility over 35 chars: `unreadable`; `Zkratka ubytovacího zařízení: X` and a prose line containing "ubytovací zařízení:" mid-line are not the facility label; label and value on one line (`Ubytovací zařízení: BYT ...`) and on two lines both read; no labels: both `missing`; `repr(result)` holds neither password; `result.password.source == ()`; the existing `tuple(result.fields) == FIELDS` and the IDUB/login password-line guard stay green. Update the `confirmed_fields` table (about 900-930): every case returns `(listed, [])`.
   - Server (`test_police_letter_flow.py`): no-JS `POST .../police-letter` (form) renders the five boxes prefilled, the password box `type="text"` with the sample password, the hidden `letter_fields` = `uby_idub,uby_ws_user,uby_mark`, the status line, no `#police-letter-check`, no `letter_ok`, `Cache-Control: no-store`; `Accept: application/json` returns the JSON of P2 with the five values and no source text; the audit table holds no IDUB, login, password or letter text (extend the existing audit assertion to `SAMPLE_WS_PASSWORD` and the facility line); `POST /apartments/{id}` with `letter_fields` and no `letter_ok` **saves** (no 400) and, with a password, runs the connection test once (`fake_client`), `ok` marks tested; without a password returns `letter_saved_untested`; a GET and a refused save (e.g. an invalid IDUB posted with a typed password) never have a `value=` on `#uby_ws_password`; the stored password never appears on any page; the no-JS read response keeps `data-dirty-start="1"`; the JSON request without a session gets no JSON body with values.
   - Labels: the property editor and the new-property page show "Name of the property" (en) and no `apartment` word in any `<label>` (regex on the HTML); cs page shows `Název ubytování`.
3. Implement P1 and P2. Run the parser and flow tests.
4. Implement P3 and P4 and the copy. Browser test `test_host_police_paste_browser.py` (model the server thread, login and fake client on `test_host_police_letter_browser.py`; `UBYHOST_REQUIRE_BROWSER=1`; widths 390, 768, 1280):
   - With JS: the read button is hidden; paste the sample letter text into `#letter_text` (`page.locator("#letter_text").fill(text)` then dispatch `paste`, or use the clipboard API): within 2 s the five boxes hold the sample values, the password box is visible text, the status line names them, the Save row shows (form dirty), no page load happened (check `performance.navigation`/a window marker survives). Then "Save and test connection" passes with the fake client.
   - Paste of unrelated text: boxes untouched, status shows `police_letter.failed` or the missing text.
   - Server down (route the fetch to fail with `page.route`), and a route answering `200` HTML (a redirect target): `read_failed` shows and the read button becomes visible.
   - Type a new value into the login box, then paste the letter: the login box keeps the typed value, the others fill. Focus stays in `#letter_text`.
   - No JS (`java_script_enabled=False`) at 390 and 1280: the read button is visible; fill and submit; the page comes back with the five boxes filled and the police section open; Save posts and saves without any tick.
5. **Discard (P5).** In `test_host_unsaved_changes_browser.py`, on the property editor with JS at 390 and 1280: (a) edit a field, click an in-app nav link: the dialog opens; **Stay** keeps the edit and focus on the link; (b) **Discard** leaves to the link's URL and the edit is not saved (reload the property: old value); (c) **Save** saves and leaves as today; (d) the same Discard check on a page that loads dirty (the no-JS letter read response opened with JS on, `data-dirty-start="1"`: submit `#police-letter-form` with `page.evaluate`, the read button is hidden); (e) reach the property editor through an in-app Turbo link (not `page.goto`) after saving another page once, then edit and Discard: it must leave (stale-listener cause); (f) after a paste fill, Discard leaves and the reloaded page shows the stored values. Run it on unchanged code, write which case fails and why in the report, then fix the root cause in `app.js` (P5).
6. **Timing (P6).** Browser test: with JS, picking `manual` or `immediate` hides `#submit_after_hours`'s field, picking `scheduled` shows it; the hint text changes with the option. No JS: the hours field is visible and its label is `automation.hours_delay`; the hint shows for the saved option. Save with `manual` still posts and saves as before (a hidden disabled field is not posted; the stored hours stay). Then implement.
7. Labels table (section 2). Cache keys: `app.js?v=20261111-1100a`; `app2.css?v=20261111-1100a` if CSS changed; regenerate `static_versions.json`.
8. Append to `docs/context/decisions.md`:
   - `- 2026-11-11 [police] 1100: no confirm tick for police-letter values; each value is an editable box; filing safety stays with Save and test connection (owner, reverses 1097).`
   - `- 2026-11-11 [police] 1100: the letter parser reads the web-service password and facility name; never logged, audited, stored by the read or in repr (owner, reverses 1085 "never reads the password").`
9. **UX gate (rules 7 and 10).** From `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30`, green, 0 skipped, no new `ALLOW`. Screenshots in `docs/tasks/screenshots-1100/` at 390, 768 and 1280 (`full_page=True`, police section in view): `police-empty-`, `police-after-paste-`, `timing-delay-`, `timing-manual-`, `leave-dialog-` (15 files). Open each. In the report **and the PR**, per state and width, write what you saw. Paste and tick the design-system checklist. A finding is fixed in the template or CSS, never silenced.
10. Section 6 commands, report.

## 5. Do not touch

`_run_connection_test` and `test_connection` logic, the `letter_listed` blocks in `apartment_update` (about 2648-2660) and `test_connection` (about 3531-3550), `property_setup.mark_tested` callers, `reporting.py`, `reporting.client_for`, anything under `App/app/ubyport/`, submission and filing (`submit_state`, worker, watchdog), credential encryption and storage (`uby_ws_password_enc`, `db.encrypt_secret`), `validation.py`, `db.py`, migrations, `retention.py` (the read stores nothing new), `routes/onboarding_wizard.py`, the setup flow (`property_setup.py` open/next-section logic, 1099's `sec_open`, `setup_open`, ready card), the Archive row, `recomputeDirty` and the 1096 dirty-start rule, `ALLOW` in `test_layout_lint_browser.py`, any dependency. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`; no full suite)

From `App/`:

1. Server (test-map rows Onboarding and properties, Copy and translations, Static files, plus the police files and privacy): `.venv/bin/python -m pytest tests/test_police_letter_parser.py tests/test_police_letter_flow.py tests/test_onboarding*.py tests/test_property_*.py tests/test_first_*.py tests/test_0534_property_page_v2.py tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_privacy_first.py -q --tb=short -x`. Filing row once, read-only proof that nothing moved: `.venv/bin/python -m pytest tests/test_police_*.py tests/test_ubyport_*.py tests/test_submission_*.py -q --tb=short`.
2. Browser, 0 skipped (test-map row Host pages: `test_host_*.py` and `test_host_geometry.py`, which includes the new `test_host_police_paste_browser.py`, `test_host_unsaved_changes_browser.py` and the police-letter browser files; plus the guards): `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_*.py tests/test_0851_savebar_browser.py tests/test_layout_lint_browser.py tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py tests/test_required_stars.py -q --tb=short -rs`.

Repo root: `python3 scripts/design_lint.py 2>&1 | tail -30`, `python3 scripts/context_lint.py 2>&1 | tail -30`.

Existing tests that pin the 1097 check block and tick (expected edits, change only those assertions): `test_police_letter_flow.py` (about 130-140, 265-290, 340-370, 380, 433, 485-495, 745-790, 875, 890-935: `letter_ok`, `letter_ok-error`, `data-first-error="letter_ok"`, `confirm_all`, `type="password"` regex, `police-letter-check` index, `letter_shown` rows), `test_host_police_letter_browser.py` (128, 145-165, 240-310, 427), `test_host_police_letter_guard_browser.py` (97), `test_first_setup_open_section.py` (243: drop `letter_ok="1"`), `test_police_letter_parser.py` (confirmed_fields table). Every assertion that the stored password is never rendered, the letter text is never echoed, the audit holds no values, the no-test-without-password rule and the 1085 lockout guard stays and stays green. If one of those fails, the code is wrong: fix the code, never the test. More than 8 existing test files need edits: STOP. Two failures are known on clean main (`test_host_ux_acceptance.py` guide page; `test_reporting_help_0097.py`); name them, do not fix.

## 7. Acceptance

- [ ] With JS, pasting the letter fills IDUB, login, password (visible), short name and facility name in place, no page load, no button press; the status line says what was filled and what to type.
- [ ] Without JS, the read button posts and the page returns with the same five boxes filled; Save works with no tick.
- [ ] No `letter_ok` anywhere in `App/app` (grep); no 400 for a missing tick.
- [ ] Filing unchanged: `git diff origin/main -- App/app/reporting.py App/app/ubyport App/app/validation.py App/app/db.py` is empty; the `letter_listed` blocks in `apartment_update` and `test_connection` are unchanged; the connection test still runs once on a letter save with a password.
- [ ] The password is in no log, audit row, `repr`, source slice, URL, storage API, or GET page.
- [ ] Discard leaves without saving; Stay keeps edits; Save saves; the failing-first test is named in the report with its root cause.
- [ ] Discard also works after a Turbo visit and after a paste fill (one leave-guard listener per document); the police UI lives in `_police_fields.html` with its variables listed at the top, and its JS finds its form from the boxes.
- [ ] Hours field hidden unless the delay option is picked (JS); without JS it shows with the "delay option only" label; each option has its hint (en, cs).
- [ ] No host label says "apartment" on the property pages; leftovers listed with reasons.
- [ ] en and cs keys match; no em dash; `app.js` key bumped (and `app2.css` if changed); `static_versions.json` regenerated; no new dependency, route, migration or outbound request.
- [ ] Layout lint green, 0 skipped, no new `ALLOW`; 15 screenshots and per-state notes in the report and PR; checklist ticked; the two decision lines appended.

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; the CSRF layer refuses the fetch post; a step needs a new route, a migration, a dependency or a change in a do-not-touch file; the sample letter's password or facility cannot be read without loosening the IDUB/login password-line guard; a filing or connection-test test fails; more than 8 existing test files need edits; a test fails twice on the same cause (attempt 3 of 3); 60 tool calls (finish the step, commit, write `Done: steps 1 to k. Left: steps k+1 to 10.`).

## 9. Report

`docs/tasks/1100-report.md`: what changed (files), failing-first counts, the Discard root cause, test commands and counts (0 skipped), the 15 screenshot names and per-state, per-width notes, the ticked checklist, any existing test expectation changed (names), leftover "apartment" strings with reasons, anything left.
