# 1097: police letter check step, one tick for all three values, one Edit per value, and the Police section phone fixes

Status: todo
Tier: B | Depends on: 1085, 1086, 1096 (all on main; base `c02b9510`) | Base: origin/main | Branch: claude/1097-police-one-tick
Executor: Opus (Tier B) | Attempts: 3 at most | Fits one session: stop at 60 tool calls (section 8); reads stay at 150 lines or fewer
Review: the orchestrator checks the diff, the screenshots and the PR notes before the PR opens.
Report: docs/tasks/1097-report.md

## 1. Objective

Owner decision (Josef, 2026-11-10 23:46) for the "Check what we found" step on the property settings page, Reporting & fees:

1. **One tick** for all three found values (IDUB, web-service login, short name "zkratka"). It replaces the three "Matches my letter" ticks.
2. **Each value is shown once**, with its own **Edit** control. Edit reveals that value's input in place of the value text. It must work **without JavaScript**.
3. The editable fields below no longer repeat those three values while the check block is shown.
4. The **server still refuses to save without the tick** (400, nothing saved).

Plus three phone fixes in the same Police section, from the design check (`/mnt/project-files/reviews/design-check-2026-11-10/findings.md`, findings 1 to 3; finding 4 is item 3 above). Rule numbers are from [design-system](../design/design-system.md) section 1:

- **F1 (rule 7, rule 3).** At 390 the help "?" is a 44 px white circle that pushes the input about 40 px down. Rule 7: "The '?' is a plain 18 px icon on the same line right after its label, never below it; the tap target is an invisible hit area." Rule 3: "A label sits 6 px above its input, never glued to it." Make it a plain 18 px icon with an invisible 44 px hit area and the label 6 px above the input.
- **F2 (rule 8).** At 390 the "Send timing" select text is cut off ("...from completior"). Rule 8: "Never truncate a label. Text that matters wraps or the layout changes."
- **F3 (rule 4).** At 390 "Save and test connection" is a grey pill on the right. Rule 4: "On phone the primary goes full width"; "no button wraps to two lines". Make it full width and 44 px high on the phone. It **stays `ui-btn-secondary`** (review, 2026-11-11): the form's one coral primary is the Save row (rules 4, 5 and 9), and 1096 shows that Save row at load in the check state, so a coral test button would always compete with it.

Screenshots for the findings: `police-plain-390.png`, `police-pasted-landing-390.png`, `police-pasted-section-390.png` in `/mnt/project-files/reviews/design-check-2026-11-10/` (open with the Read tool, 1 or 2 of them at most).

## 2. Context

### What 1085, 1086 and 1096 settled (keep it, except where section 1 replaces it)

Read `docs/tasks/1086-police-letter-ux.md` section 2 "What 1085's fix rounds settled" only if a point is unclear. Keep:

- helper rules live in `App/app/static/app2.css` under `body.v2` (3435-3474); `host.css` has no police-letter rule; the two `details` (find, paste) are flush rows with a 1 px `--line` rule and 44 px summaries
- `letter_text` has `form="police-letter-form"`; Save never sends it; `#police-letter-form` (line 476) holds only `_csrf`
- `police-letter-note` (never `muted`); the check block scrolls into view with JavaScript; with no JavaScript the first control that needs the host has `autofocus`
- `POST /apartments/{id}/police-letter` answers 422, `Cache-Control: no-store`, stores nothing; a save or `/test-connection` without the tick answers **400** and saves nothing
- the connection test runs only at the final success exit, only with `letter_fields` and a password, never with `setup_step`; flashes `letter_test_ok`, `letter_test_failed`, `letter_test_unreachable`, `letter_saved_untested`, `letter_new_login_no_password` stay as they are
- **1096:** `#property-settings-form` has `data-dirty-start="1"` while `letter_check` is set (`_property_editor.html:139`), so the Save row and the leave warning show at load. Keep it.
- UbyPort credentials handling (password never echoed, never in the page) and "Save and test connection" behaviour: unchanged.

### How it works now (verified on `c02b9510`)

- Template `App/app/templates/_property_editor.html`:
  - `{% if letter_rows %}` block `#police-letter-check` (330-351): hidden `letter_fields` (332), one `.police-letter-row` per row (335-349) with `.police-letter-value` (338), the source `<code>` (341-342), `police-letter-note` (344), the required tick `letter_ok_{{ row.name }}` with label `police_letter.confirm` and a `req-star` (345), the error `police_letter.confirm_missing` (346).
  - The three duplicated inputs: `text_field('uby_idub'` (355), `text_field('uby_ws_user'` (358), `text_field('uby_mark'` (376). Each reads `letter_fill[...]` (the prefill) or the saved value. `uby_ws_password` (361), `uby_name` (380), `uby_contact` (381) are not duplicated and stay.
  - Test button (384): `formaction=".../test-connection" ... formnovalidate`, class `ui-btn ui-btn-secondary`.
  - Send timing select `#automation_mode` (394-401) uses `t('automation.mode.manual')` and `t('automation.mode.scheduled')` and `t('automation.mode.immediate')` (398, 400, 402). Those long keys are also used by `setup_wizard/police.html:52-53` and `setup_wizard/automation.html:12-13`: do not change them.
- `App/app/police_letter.py:386` `confirmed_fields(form)` returns `(listed, unconfirmed)` from `letter_fields` and the per-field ticks `letter_ok_<name>`.
- `App/app/routes/admin.py`:
  - `_letter_rows_from_form` (2286-2312) builds the rows of a refused save, with `ticked` and `error` per row.
  - `_refuse_apartment_save` (2315ff): the `if letter_unconfirmed:` block (2376-2387) adds one `_save_error("police", f"letter_ok_{name}")` per name and sets `letter_check`. It renders from `draft` (the posted `uby_*` values, 2325-2329) and passes **no** `letter_prefill`, so on a refused save the prefill expression yields the posted value.
  - Callers of `confirmed_fields`: 2378, 2612, 2825-2828 (the 400 refusal in the save route), 3494 (test-connection; it only reads `letter_listed`, used again at 3508).
  - 3595: `extra["letter_check"] = result if filled else None` (the paste reply; read 3585-3600).
- i18n `App/app/host_i18n.py`: en `police_letter.confirm` (4574), `police_letter.confirm_missing` (4582), `police_letter.check_title` (4570), `police_letter.source*` (4571-4572); cs `police_letter.confirm` (5443), `police_letter.confirm_missing` (5451), `check_title` (5439). Vietnamese copies: `App/app/host_vi_i18n.py:1928` and `:1936`.
  - **Already on main, reuse, do not add:** `common.edit` (en 982 "Edit", cs 3137 "Upravit") and the short timing keys `automation.mode_short.{manual,scheduled,immediate}` (en 8653-8655: "Only when I press send", "Automatically, after a delay", "As soon as forms are complete"; cs 8658-8660: "Jen po stisknutí Odeslat", "Automaticky, s prodlevou", "Hned po vyplnění formulářů"; vi `host_vi_i18n.py:3476-3478`). No template uses the short keys today.
  - Parity is enforced both ways: `tests/test_guide_coverage.py:15-17` (every en key needs a vi key) and `tests/test_host_i18n.py:155` (every vi key needs an en key), plus en/cs at `test_host_i18n.py:57`. So the vi edits are **required**, not optional.
- CSS: `App/app/static/app2.css`: check block 3461-3474, `.police-sample-link` 2320. **Help tip: the rules that win on this page are the `.property-settings-form` ones at 2271 and 2278-2288**, not the base rules at 1623-1626: 2279 draws the button itself as a 24 px white circle with a 1 px border and `margin:0 0 0 12px`; 2280 makes `::after` an invisible hit area (`inset:-13px`); **2284** (`@media (max-width:1023px)`) grows the button itself to 44 x 44 with `margin:0 0 0 8px`. That last rule is finding 1: the white circle is 44 px and the row grows. It covers 768 as well as 390.
- Cache keys on main: `app2.css?v=20261110-1086b` (`base.html:23`), `app.js?v=20261110-1096a` (`base.html:47`), `host.css?v=20261108-1010a`.

### Design (decided; do not redesign)

**Template (the check block):**

- The block keeps `<h3>` (`check_title`), the hidden `letter_fields`, and one `.police-letter-row` per row.
- Each **filled** row shows once: the name as a `<label for="{{ row.name }}">` (class `police-letter-name`), the value text `.police-letter-value`, the source `<code>` line, the `saved_now` note, and an **Edit** control. The field's old hint text is not repeated in the row (rule 7).
- **Edit without JavaScript** = a per-row `<details class="police-letter-edit">` with `<summary>` `{{ t('common.edit') }}` (44 px high, a text link look, coral only as link per rule 9) whose body holds **the real input** (`id="{{ row.name }}"`, `name="{{ row.name }}"`, `autocomplete="off"`, the value from **the same prefill expression** the removed `text_field` used, the same `maxlength` 14 / none / 6, `aria-required="true"`, never the HTML `required` attribute: a closed `details` cannot show a validation bubble). A closed `details` still posts its inputs, so the value is saved even when Edit is never opened. Do not add JavaScript (`app.js` stays untouched; its key stays `1096a`). If you believe an `app.js` change is required: STOP.
  - **Each name posts exactly once.** `uby_idub`, `uby_ws_user` and `uby_mark` each have one input in the page in every state: inside the row's `details` when the row is filled, else the normal `text_field` below. Never both, never a hidden copy, never a `disabled` input (a disabled input posts nothing and the saved value would be blanked). The server reads the same three names as today, so `_save_apartment_form`, `_posted_credentials` and `/test-connection` see the same post as today.
  - **The shown text and the posted value must never differ (hard rule 1: the tick confirms what the host sees).** Without JavaScript the value text cannot follow the input, so Edit opens **one way**: `body.v2 .police-letter-edit[open]>summary{display:none}` (once open, it cannot be closed again on that page), and `body.v2 .police-letter-row:has(.police-letter-edit[open]) .police-letter-value{display:none}` hides the text while the input shows. So a row shows either the untouched text or the live input, never a stale text over an edited input. `autocomplete="off"` stops a browser from restoring a typed value into a closed row on reload. The source line and its hidden `letter_line_*` / `letter_src_*` inputs stay as they are, outside the `details`.
  - The property sections are themselves `details.prop-sec`, and `details.police-letter-find` / `.police-letter-paste` are already nested in this one: model the new `details` on those (see 3472 for the chevron reset) so no section chevron or `prop-sec` summary style leaks onto the Edit summary.
  - The three summaries all read "Edit": give each a distinct accessible name with the field name in a visually hidden span, only if a visually-hidden class already exists (`grep -n "sr-only\|visually-hidden" App/app/static/app2.css | head -3`); add no new utility class.
- **Unfilled rows** (`row.filled` false: "not found"): keep today's text for the row and keep that field's normal `text_field` below, because the host must type it. Compute the shown set once, for example `{%- set letter_shown = (letter_rows | selectattr('filled') | map(attribute='name') | list) if letter_rows else [] -%}`, and render each of the three `text_field` blocks only `{% if 'uby_idub' not in letter_shown %}`. The `grid` wrappers (355-359, 375-378) must not leave an empty box or gap (hide the wrapper when its only field is hidden). When there is no check block, the page is exactly as today.
- **The single tick**, after the last row, inside `#police-letter-check`: `<div class="checkline"><input type="checkbox" id="letter_ok" name="letter_ok" value="1" required autofocus ...><label for="letter_ok">{{ t('police_letter.confirm_all') }}<span class="req-star" aria-hidden="true">*</span></label></div>` and, only on a refused save (`{% if letter_error %}`), `<p class="err-text" id="letter_ok-error" role="alert" data-field-error>{{ t('police_letter.confirm_missing') }}</p>` with `aria-invalid="true" aria-describedby="letter_ok-error"` on the input. The tick is **never rendered checked**: the block only renders after a paste or after a refusal for the missing tick, so it is always unticked and always carries `autofocus` (the `letter_focus` namespace at 333 goes away). The tick is shown only when at least one row is filled (when no row is filled there is nothing to confirm; `letter_fields` is then empty and the server needs no tick).
- Do not render per-row `letter_ok_<name>` inputs, ids or errors any more.

**Server:**

- `police_letter.confirmed_fields(form)`: `listed` as today; if `listed` is non-empty and `letter_ok` is not exactly the str `"1"` then `unconfirmed` is the whole `listed`; else `[]`. Never raises. Posted old-style `letter_ok_<name>` keys are ignored (a stale page cannot confirm).
- `admin.py`: the `if letter_unconfirmed:` block (2376) adds **one** `_save_error("police", "letter_ok")` (not one per name) and adds `"letter_error": True` to the same `extra.update` (2383-2387). `_letter_rows_from_form` is left alone (its per-row `ticked` / `error` are simply no longer read by the template). The refusal stays 400, saves nothing, and re-renders the rows with the posted (possibly edited) values, the three inputs inside their closed `details`.
- No route, flow-order, parser, password or `reporting.py` change.

**Copy (cs and en together; no em dash in UI copy; rule 9 of the brief rules: say it once):**

- New `police_letter.confirm_all`: en "These values match my letter"; cs "Tyto údaje souhlasí s dopisem"; vi "Các thông tin này khớp với thư của tôi" (name it in the report for the owner to check). Edit uses the existing `common.edit`; add no `police_letter.edit` key (check `grep -n '"common.edit"' App/app/host_vi_i18n.py | head -2`; if vi lacks it the lookup falls back to English, add nothing).
- Reword `police_letter.confirm_missing` for one tick (the block may list one, two or three values, so no count in the text): en "Tick the box to confirm these values."; cs "Zaškrtněte políčko, tím potvrdíte tyto údaje."; vi "Hãy đánh dấu ô để xác nhận các thông tin này.".
- **Remove** the now unused `police_letter.confirm` in en, cs and `host_vi_i18n.py` (all three, or the parity tests fail).
- Send timing select: use the **existing** short keys `automation.mode_short.manual`, `.scheduled`, `.immediate` for the three `<option>` texts at `_property_editor.html:398,400,402`. Do not add, rename or reword an `automation.*` key, and leave `automation.timing_help` alone. The wizard keeps the long keys. If a short text still does not fit at 390 in cs or en, fix it with the select's width (F2 below), not with new copy; if that is not enough: STOP.

**CSS (`App/app/static/app2.css`, tokens only, every selector under `body.v2`):**

- Check block: a `.police-letter-edit` rule (summary 44 px, `--brand-ink` link colour, `--text-base`; open body has 12 px (`--space-3`) above the input; the input fills the column), the two one-way rules above (`[open]>summary{display:none}` and the `:has(...)` rule), and the single tick row reusing the `.checkline` rules (3468-3471; extend their selectors from `.police-letter-row .checkline` to `.police-letter-check .checkline`). 12 px between rows, the Edit summary and the tick (rule 3).
- **F1:** edit the existing `.property-settings-form` rules (2271, 2279, 2280, 2284); do not add a second competing block, and do not touch the base rules at 1623-1626 or the settings-lane rules at 1829-1859 (other pages use them). The fix applies to every help "?" in this form, not only Police, at every width below 1024 px (so 390 **and** 768 change; 1280 does not). Below 1024 px: the button's own box stays **44 x 44** (the layout lint measures the button, so do not shrink it) but is invisible (`background:transparent;border:0`), and its negative block margins (`-13px` top and bottom, as 1626 does) stop it adding height to the label row; the visible mark is an 18 x 18 ring drawn by `::after` (1 px `--line` border, round, centred on the "?" glyph), which replaces the `inset:-10px` / `-13px` hit-area `::after` at these widths. The "?" sits on the label line right after the label with its ring 8 to 12 px from the label text, the invisible box overlaps no other control, and the label is 6 px above its input: find which `.field-label-row` / label margin wins on this page (`grep -n "field-label-row{" App/app/static/app2.css | head`; 1859 applies only inside a settings lane) and override under `body.v2 .property-settings-form` below 1024 px. Measured by the browser test (step 4).
- **F2:** `#automation_mode` shows its full selected text at 390 (see the short keys); `min-width:0;width:100%;text-overflow:clip` (never an ellipsis); `padding-inline` from tokens. The test measures it.
- **F3:** below 768 px (phone, rule 4), `body.v2 .property-settings-form #ubyport .actions .ui-btn` (the test button) is `display:flex;width:100%;min-height:44px;justify-content:center;white-space:normal`. **No class change in the template: it stays `ui-btn-secondary`** (see section 1, F3). 768 and 1280 keep today's look. Do not hide or restyle the Save row.

### Anchors (re-check each with `grep -nF`; if one is missing: STOP)

1. `App/app/templates/_property_editor.html`: `id="police-letter-check"` (330), `name="letter_ok_{{ row.name }}"` (345), `{{ text_field('uby_idub'` (355), `{{ text_field('uby_ws_user'` (358), `{{ text_field('uby_mark'` (376), `formaction="{{ base_url }}/test-connection"` (384), `id="automation_mode"` (395), `id="police-letter-form"` (476), `data-dirty-start="1"` (139).
2. `App/app/police_letter.py:386` `def confirmed_fields`.
3. `App/app/routes/admin.py`: `def _letter_rows_from_form` (2286), `if letter_unconfirmed:` (2376), `police_letter.confirmed_fields(form)` at 2378, 2612, 2825, 3494.
4. `App/app/host_i18n.py`: `"police_letter.confirm": "Matches my letter"` (4574) and `"police_letter.confirm": "Souhlasí s dopisem"` (5443); `App/app/host_vi_i18n.py:1928`; `"common.edit": "Edit"` (982); `"automation.mode_short.scheduled"` (8654, 8659; vi 3477).
5. `App/app/static/app2.css`: `body.v2 .help-tip-btn{` (1624), the `@media (max-width:1023px){body.v2 .help-tip-btn{width:44px` rule (1626), `body.v2 .property-settings-form .help-tip-btn{display:inline-flex` (2279), the `@media (max-width:1023px)` rule ending `.property-settings-form .help-tip-btn{width:44px;height:44px;min-width:44px;min-height:44px;margin:0 0 0 8px}}` (2284), `body.v2 .police-letter-row{` (3463). `App/app/templates/base.html:23` `app2.css?v=20261110-1086b`.
6. `App/tests/test_police_letter_flow.py` `def test_a_missing_tick_refuses_the_save_on_both_paths` (468) and `def test_two_missing_ticks_are_two_errors` (892); `App/tests/test_required_stars.py:70` `test_editor_police_fields_are_starred_and_aria_required`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/_property_editor.html` | edit | check block, three fields hidden while shown, select option keys (the test button's class does not change) |
| `App/app/police_letter.py` | edit | `confirmed_fields` reads the single `letter_ok` |
| `App/app/routes/admin.py` | edit | one `letter_ok` error and `letter_error` in `extra` (only the `if letter_unconfirmed:` block, 2376-2387) |
| `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` | edit | new `confirm_all`, reworded `confirm_missing`, removed `police_letter.confirm` (en, cs, vi); no `automation.*` change |
| `App/app/static/app2.css` | edit | section 2 CSS |
| `App/app/templates/base.html` | edit | line 23: `app2.css?v=20261110-1086b` becomes `app2.css?v=20261111-1097a` (a second change: `1097b`). The date is the day of the change, as every earlier key (`20261110-1086b` was committed on 11-10): use that day's date if you run later than 2026-11-11. `app.js` and `host.css` keys stay. |
| `App/tests/static_versions.json` | regenerate | from `App/`: `.venv/bin/python tests/test_static_versions.py --write` |
| `App/tests/test_police_letter_flow.py` | edit | single tick, section 4 step 3 |
| `App/tests/test_host_police_letter_browser.py`, `App/tests/test_host_police_letter_guard_browser.py` | edit | single tick, Edit, geometry, section 4 steps 4 and 5 |
| `App/tests/test_police_letter_parser.py` | edit only if it fails | it holds `letter_ok_` cases for `confirmed_fields`: move them to the single `letter_ok` |
| `App/tests/test_required_stars.py` | edit only if it fails | the police star assertions (the single tick keeps one `req-star`) |
| `docs/tasks/screenshots-1097/` | create | the PNGs (step 7) |
| `docs/tasks/1097-report.md` | create | the report; set `Status: review` here |

## 4. Steps (commit after each: `1097 step k`)

1. `git fetch origin main`, `git merge origin/main`. Confirm the anchors; a missing one: STOP. Then `grep -rn "letter_ok_\|police_letter.confirm\b\|police_letter.confirm\"" App/app App/tests | cut -c1-120 | head -60` to list every use you must change. Also `grep -rn "mode_short\|from completion\|od dokončení" App/tests | cut -c1-120 | head`: a test that asserts the long option text **on the property editor** changes to the short text; a hit in another feature's test (wizard, mail): leave it, and if it fails, STOP.
2. **Server and copy:** `police_letter.confirmed_fields`, the `admin.py` block, the i18n keys (cs, en, vi), then the template. Check block, Edit `details`, hidden duplicates, the single tick, the select option keys.
3. **`test_police_letter_flow.py`** (change the existing tests; do not delete coverage):
   - Replace every per-field `letter_ok_<name>: "1"` in posted data with `letter_ok: "1"`.
   - `test_a_missing_tick_refuses_the_save_on_both_paths` (468): with no `letter_ok` the save and `/test-connection` answer 400, nothing is saved (read the row with the db helper), and the page holds exactly one `letter_ok-error`.
   - `test_two_missing_ticks_are_two_errors` (892) becomes `test_one_missing_tick_is_one_error`: with two or three values listed and no tick, exactly **one** error and one `data-field-error`, and no `letter_ok_` anywhere in the page.
   - **New** `test_a_stale_per_field_tick_does_not_confirm`: posting old `letter_ok_uby_idub=1` etc. without `letter_ok` is refused (400).
   - **New** `test_the_check_block_shows_each_value_once`: after a paste, the page has exactly one `id="letter_ok"`, no `letter_ok_uby_`, each of the three values appears as an `<input ... value=...>` once and in `.police-letter-value` once (no second `text_field` copy: count `name="uby_idub"` == 1), each row has a `<details class="police-letter-edit">`, `req-star` count in the block is 1, and the three inputs sit **inside** the `details`. The same counts hold on the 400 page of a refused save (posted values, `name="uby_idub"` == 1, the tick not `checked`).
   - **New** `test_edit_value_is_saved_with_the_tick`: paste, post the three values with `uby_idub` changed to a new valid value and `letter_ok=1`: the saved IDUB is the new one (the edited value wins; the existing "saved now" and source behaviour is unchanged).
   - **New** `test_an_unfound_value_keeps_its_own_field`: a letter with no IDUB: the page still has the normal `uby_idub` field below (once), and only the found values are in the check block.
   - **New** `test_an_untouched_save_keeps_all_three_values`: paste, post exactly what the page holds (parse the inputs out of the HTML, add `letter_ok=1`): the three saved values equal the pasted ones, none blank, none doubled (posting from a closed `details` loses nothing).
   - **Credentials path unchanged:** the existing `/test-connection` tests (typed values saved first; a new login without a password is not tested, `letter_new_login_no_password`; the password never in the page) stay green with only the posted tick changed. If one needs any other change: STOP.
   - A save without a password still skips the client (`letter_saved_untested`); with a password exactly one read-only client: keep those tests, only the posted tick changes.
4. **`test_host_police_letter_browser.py`**, at 390, 768 and 1280, update the existing tests, and add:
   - Turbo and no-JavaScript (`java_script_enabled=False`): after "Read the letter" the block shows one tick (`#letter_ok`, `autofocus` without JavaScript) and **no** "Matches my letter" text; the three values appear once.
   - **No-JavaScript Edit:** click the "Edit" summary of the IDUB row (a `details` toggles with no script): the input `#uby_idub` becomes visible, the row's `.police-letter-value` is hidden and the "Edit" summary is gone (one-way: the row cannot be closed again), type a new value, tick, Save: the saved value is the new one (read it with the db helper).
   - Click Save with no tick: the browser blocks it (`required`). "Save and test connection" with no tick (`formnovalidate`): 400, one error under the tick, saved row unchanged.
   - Tick, type a password, Save with `fake_client`: flash "Saved. The login and password work."; exactly one client, read-only calls only. Save with no password: `letter_saved_untested`, no client built.
   - **Geometry:** one tick row and each Edit summary at least 44 px on the phone; 12 px or more between rows, Edit and tick; the three duplicated inputs are not visible below the block (`#uby_idub` is inside the check block only); no sideways scroll; no label cut off.
   - **F1** (390 and 768): in `#ubyport`, for `#uby_ws_password`'s label row: the help ring is 18 x 18 (+/- 1; `getComputedStyle(btn, '::after')`), the button's computed background is transparent, the button's box is at least 44 x 44, the label bottom to input top is 6 px (+/- 2), and the help button does not increase the label row height (row height <= label height + 2).
   - **F2** (390): the `#automation_mode` selected option text fits: measure with `page.evaluate` (a canvas `measureText` with the select's computed font, or a hidden span with the same font) and assert text width <= select `clientWidth` minus its padding and arrow (about 28 px), for each of the three options selected in turn and for both `cs` and `en` (the host language cookie as the model test sets it).
   - **F3** (390): the test button's width equals its container's width (+/- 1), height >= 44, one line of text, and it still has the class `ui-btn-secondary` (not coral); at 768 and 1280 it is not full width.
   - Screenshots only when `UBYHOST_SHOTS_1097=<dir>` is set (as 1086 did with `UBYHOST_SHOTS_1086`).
5. **`test_host_police_letter_guard_browser.py`:** the dirty-start test ticks `#letter_ok_uby_idub` at line 97 (the file's only `letter_ok_` use): change it to `#letter_ok`. Keep the 1096 tests (the Save row and the leave warning at load before any input) green and untouched in meaning. The discard-warning tests need no change.
6. **Cache keys and `static_versions.json`** (section 3), then **UX gate** (rules 7 and 10, [steps](../context/workflow.md#ux-gate)): from `App/` run `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30`: green, **0 skipped**, no new `ALLOW`, never silence a finding.
7. **Screenshots** into `docs/tasks/screenshots-1097/` (`UBYHOST_SHOTS_1097=docs/tasks/screenshots-1097`), taken as the model test's `shot` helper (`page.locator("#ubyport").screenshot`) at 390, 768 and 1280, each opened and inspected once:
   - `find-{390,768,1280}.png`: the "Where do I find these?" card open
   - `check-{390,768,1280}.png`: the check block (one tick, three values, Edit closed) and, in one extra file `check-edit-390.png`, one Edit opened
   - `error-{390,768,1280}.png`: after a save without the tick (one error under the tick)
   - `plain-390.png`: the Police section with no check block (F1, F2, F3 visible: help icons, Send timing, full-width test button)
8. Run section 6, then write the report (section 9), `Status: review`.

## 5. Do not touch

`App/app/static/app.js` and its key (`20261110-1096a`), `host.css` and its key, `reporting.py`, `validation.py`, `ubyport/*`, `db.py`, migrations, `police_letter.py` outside `confirmed_fields`, the paste parser (`parse*` in `police_letter.py`), the `POST .../police-letter` route and its 422 behaviour, the password handling and the connection-test branches in `admin.py` (2612 ff and 3494 ff except reading `letter_listed`), `_police_letter_figure.html`, the long keys `automation.mode.*` and every wizard template, the `setup_step` flow, `data-dirty-start` (1096), `ALLOW` in `test_layout_lint_browser.py`, any dependency, and the tests of other features. `docs/context/*` and `docs/design/*` are the orchestrator's.

## 6. Commands (each ends `2>&1 | tail -30`)

No full suite. From `App/` (test-map rows: Filing/police `test_police_*.py`, v2 pages, property editor, i18n):

1. Browser, 0 skipped: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_host_police_letter_browser.py tests/test_host_police_letter_guard_browser.py tests/test_police_letter_flow.py tests/test_0833_property_editor_browser.py tests/test_property_navigation_browser.py tests/test_host_geometry.py tests/test_layout_lint_browser.py tests/test_design_guardrails_browser.py -q --tb=short -rs 2>&1 | tail -30`
2. `.venv/bin/python -m pytest tests/test_police_letter_parser.py tests/test_required_stars.py tests/test_property_form_save.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_host_i18n.py tests/test_guide_coverage.py tests/test_no_em_dashes.py tests/test_privacy_first.py -q --tb=short -x 2>&1 | tail -30`
3. v2 row: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q --tb=short -rs 2>&1 | tail -30`

Repo root: `python3 scripts/design_lint.py 2>&1 | tail -30` and `python3 scripts/context_lint.py 2>&1 | tail -30`. CI runs the rest.

Known failures on clean main, not yours (name them in the report, do not fix): `test_design_guardrails_browser.py::test_every_host_page_passes_the_layout_guard` (`guest-new 390: tap-target-small "Cancel" 43 < 44`), `test_host_ux_acceptance.py` (guide page, `cs`, 390, a `help-tip-btn`) and `test_reporting_help_0097.py` (a fee help button). If the F1 change makes another help-tip test fail on a page other than the property editor: you changed too much; scope the rule to `.property-settings-form` and retry once.

## 7. Acceptance

- [ ] One tick, `letter_ok`, replaces the three; no `Matches my letter` or `Souhlasí s dopisem` text and no `police_letter.confirm` key remain (`grep -rn "police_letter.confirm\b" App | head` is empty apart from `confirm_all` and `confirm_missing`).
- [ ] Each found value is shown once, with its own Edit; Edit works without JavaScript (`details`), an edited value is saved, an untouched one is saved unchanged, and each of the three names posts exactly once. The three fields are not repeated below while the block is shown; an unfound value keeps its normal field.
- [ ] A save and a `/test-connection` without the tick answer 400 and save nothing (server test); an old per-field tick does not confirm.
- [ ] 1085/1086/1096 behaviour intact: no password means no client; with one, exactly one read-only client; discard warning; dirty at load; the password never in the page.
- [ ] F1, F2, F3 measured by browser tests at 390; F1 also at 768; 1280 unchanged in look; the test button is still `ui-btn-secondary`.
- [ ] cs and en keys together (vi too: parity is tested both ways); no new `automation.*` or `police_letter.edit` key; no unused key left; no em dash.
- [ ] Layout lint green, 0 skipped, no new `ALLOW`. Screenshots of find, check, error (and plain, edit-open) at 390/768/1280, one line per file in the report. The design-system checklist (section 5 of the design system) is ticked in the PR: rules 3, 4, 7, 8, 9 named.
- [ ] `app2.css` key bumped (`<date>-1097a`, then `1097b` per further change); `app.js` and `host.css` keys unchanged; `git diff --stat origin/main` touches only section 3 files.

PR text (the orchestrator opens the PR; you write it into the report): per page, what you saw at 390, 768 and 1280 in the find, check and error states; the checklist; the two outbound-request and personal-data lines: none (no new field, no new request).

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; the fix needs `app.js`, a parser change, a password-handling change, any edit to the credential save or connection-test code, a new route or a new dependency; the three inputs cannot post from inside a closed `details` (browser test shows the value missing); the layout lint shows a new finding you cannot fix inside section 3 files; a browser test skips; the same test fails twice on the same cause (attempt 3 of 3); **60 tool calls** or 60k tokens (finish the step, commit, write the partial report with what is done and what is left). Never silence a finding, never add an `ALLOW`, never ask the owner.

## 9. Report

`docs/tasks/1097-report.md`: files changed; commands run with pass, fail and skip counts; the acceptance list ticked; one line per screenshot; the design-system checklist; the F1 to F3 measured numbers (ring, hit box, label gap, select text width against room, button width); deviations; open questions (for example the vi wording).
