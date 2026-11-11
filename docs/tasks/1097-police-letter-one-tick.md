# 1097: police letter check step, one tick for all three values, one Edit per value, and the Police section phone fixes

Status: todo
Tier: B | Depends on: 1085, 1086, 1096 (all on main; base `c02b9510`) | Base: origin/main | Branch: claude/1097-police-one-tick
Executor: Opus (Tier B) | Attempts: 3 at most | Fits one session: stop at 60 tool calls (section 8); reads stay at 150 lines or fewer
Review: the orchestrator checks the diff, the screenshots and the PR notes before the PR opens.
Report: docs/tasks/1097-report.md

## 1. Objective

Owner decision (Josef, 2026-11-10 23:46) for the "Check what we found" step on the property settings page, Reporting & fees:

1. **One tick** for all three found values (IDUB, web-service login, short name "zkratka"). It replaces the three "Matches my letter" ticks.
2. **Each value is shown once**, with its own **Edit** control. Edit reveals or focuses that value's input. It must work **without JavaScript**.
3. The editable fields below no longer repeat those three values while the check block is shown.
4. The **server still refuses to save without the tick** (400, nothing saved).

Plus three phone fixes in the same Police section, from the design check (`/mnt/project-files/reviews/design-check-2026-11-10/findings.md`, findings 1 to 3; finding 4 is item 3 above). Rule numbers are from [design-system](../design/design-system.md) section 1:

- **F1 (rule 7, rule 3).** At 390 the help "?" is a 44 px white circle that pushes the input about 40 px down. Rule 7: "The '?' is a plain 18 px icon on the same line right after its label, never below it; the tap target is an invisible hit area." Rule 3: "A label sits 6 px above its input, never glued to it." Make it a plain 18 px icon with an invisible 44 px hit area and the label 6 px above the input.
- **F2 (rule 8).** At 390 the "Send timing" select text is cut off ("...from completior"). Rule 8: "Never truncate a label. Text that matters wraps or the layout changes."
- **F3 (rule 4).** At 390 "Save and test connection" is a grey pill on the right. Rule 4: "On phone the primary goes full width"; "no button wraps to two lines". Make it a full-width primary button on the phone.

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
  - Send timing select `#automation_mode` (394-401) uses `t('automation.mode.manual')` and `t('automation.mode.scheduled')` (and an `immediate` option at 401; read its key). Those two keys are also used by `setup_wizard/police.html:52-53` and `setup_wizard/automation.html:12-13`: do not change them.
- `App/app/police_letter.py:386` `confirmed_fields(form)` returns `(listed, unconfirmed)` from `letter_fields` and the per-field ticks `letter_ok_<name>`.
- `App/app/routes/admin.py`:
  - `_letter_rows_from_form` (2286-2312) builds the rows of a refused save, with `ticked` and `error` per row.
  - `_refuse_apartment_save` (2315ff): the `if letter_unconfirmed:` block (2376-2387) adds one `_save_error("police", f"letter_ok_{name}")` per name and sets `letter_check`.
  - Callers of `confirmed_fields`: 2378, 2612, 2825-2828 (the 400 refusal in the save route), 3494 (test-connection), 3508.
  - 3595: `extra["letter_check"] = result if filled else None` (the paste reply; read 3585-3600).
- i18n `App/app/host_i18n.py`: en `police_letter.confirm` (4574), `police_letter.confirm_missing` (4582), `police_letter.check_title` (4570), `police_letter.source*` (4571-4572); cs `police_letter.confirm` (5443), `police_letter.confirm_missing` (5451), `check_title` (5439). Vietnamese copies: `App/app/host_vi_i18n.py:1928` and `:1936`.
- CSS: `App/app/static/app2.css`: help tip 1623-1626 (the `@media (max-width:1023px)` rule at 1626 makes the button 44 x 44 and puts the 18 px ring `::after` at `left:0;top:13px`; the later settings-lane rules at 1829-1833 also touch it), check block 3461-3474, `.police-sample-link` 2320.
- Cache keys on main: `app2.css?v=20261110-1086b` (`base.html:23`), `app.js?v=20261110-1096a` (`base.html:47`), `host.css?v=20261108-1010a`.

### Design (decided; do not redesign)

**Template (the check block):**

- The block keeps `<h3>` (`check_title`), the hidden `letter_fields`, and one `.police-letter-row` per row.
- Each **filled** row shows once: the name as a `<label for="{{ row.name }}">` (class `police-letter-name`), the value text `.police-letter-value`, the source `<code>` line, the `saved_now` note, and an **Edit** control.
- **Edit without JavaScript** = a per-row `<details class="police-letter-edit">` with `<summary>` "Edit" (44 px high, a text link look, coral only as link per rule 9) whose body holds **the real input** (`id="{{ row.name }}"`, `name="{{ row.name }}"`, the value from the same prefill expression the removed `text_field` used, the same `maxlength` 14 / default / 6, `aria-required="true"`). A closed `details` still posts its inputs, so the value is saved even when Edit is never opened. When a row's `details` is open, hide its `.police-letter-value` text so the value is shown once (`body.v2 .police-letter-row:has(details[open]) .police-letter-value{display:none}`) and keep the source line. Opening Edit moves focus to the input only with JavaScript; no JavaScript is needed to see and type in it. Do not add JavaScript (`app.js` stays untouched; its key stays `1096a`). If you believe an `app.js` change is required: STOP.
- **Unfilled rows** (`row.filled` false: "not found"): keep today's text for the row and keep that field's normal `text_field` below, because the host must type it. Compute the shown set once, for example `{%- set letter_shown = (letter_rows | selectattr('filled') | map(attribute='name') | list) if letter_rows else [] -%}`, and render each of the three `text_field` blocks only `{% if 'uby_idub' not in letter_shown %}`. The `grid` wrappers (355-359, 375-378) must not leave an empty box or gap (hide the wrapper when its only field is hidden). When there is no check block, the page is exactly as today.
- **The single tick**, after the last row, inside `#police-letter-check`: `<div class="checkline"><input type="checkbox" id="letter_ok" name="letter_ok" value="1" required ...><label for="letter_ok">{{ t('police_letter.confirm_all') }}<span class="req-star" aria-hidden="true">*</span></label></div>` and, only on a refused save, `<p class="err-text" id="letter_ok-error" role="alert" data-field-error>{{ t('police_letter.confirm_missing') }}</p>` with `aria-invalid="true" aria-describedby="letter_ok-error"` on the input. Keep `autofocus` on the tick when it is not ticked (it is the one control left to answer). The tick is shown only when at least one row is filled (when no row is filled there is nothing to confirm; `letter_fields` is then empty and the server needs no tick).
- Do not render per-row `letter_ok_<name>` inputs, ids or errors any more.

**Server:**

- `police_letter.confirmed_fields(form)`: `listed` as today; if `listed` is non-empty and `letter_ok` is not exactly the str `"1"` then `unconfirmed` is the whole `listed`; else `[]`. Never raises. Posted old-style `letter_ok_<name>` keys are ignored (a stale page cannot confirm).
- `admin.py`: the `if letter_unconfirmed:` block (2376) adds **one** `_save_error("police", "letter_ok")` (not one per name). `_letter_rows_from_form` keeps `error`, but the template uses one `ticked` and one error for the block (pass `letter_ticked`/`letter_error` through `extra`, or derive in the template from `letter_unconfirmed`; keep it small). The refusal stays 400, saves nothing, and re-renders the rows with the posted (possibly edited) values, the three inputs inside their `details`.
- No route, flow-order, parser, password or `reporting.py` change.

**Copy (cs and en together; no em dash in UI copy; rule 9 of the brief rules: say it once):**

- New `police_letter.confirm_all`: en "These values match my letter"; cs "Tyto údaje souhlasí s dopisem". New `police_letter.edit`: en "Edit"; cs "Upravit". Check whether an `Edit` key already exists (`grep -n '"common.edit"\|\.edit"' App/app/host_i18n.py | head`); reuse one if it does.
- Reword `police_letter.confirm_missing` for one tick: en "Tick the box to confirm the three values."; cs "Zaškrtněte políčko, tím potvrdíte všechny tři údaje." (the block may list one, two or three values: if the count can be below three, write "Tick the box to confirm these values." / "Zaškrtněte políčko, tím potvrdíte tyto údaje.", the safe choice).
- **Remove** the now unused `police_letter.confirm` in en, cs and `host_vi_i18n.py`. Update the Vietnamese `confirm_missing` and add `confirm_all` and `edit` there only as the i18n parity test demands (`grep -n "host_vi_i18n\|police_letter" App/tests/test_host_i18n.py | head`); if parity is required, use plain Vietnamese equivalents and name them in the report for the owner to check.
- Send timing select: add new keys `automation.mode_short.manual`, `automation.mode_short.scheduled` (and `immediate` if its text is also long) with text that fits one line in a 390 px select, for example en "Only when I press send" / "After a delay" ; cs "Jen po stisknutí Odeslat" / "Po prodlevě". The long explanation stays in the existing help under the section "?" (`automation.timing_help`); if it does not say what "delay from completion" means, append one clause there in cs and en. Use the short keys only for the `<option>` text at `_property_editor.html:398,400,402`. The wizard keeps the long keys.

**CSS (`App/app/static/app2.css`, tokens only, every selector under `body.v2`):**

- Check block: a `.police-letter-edit` rule (summary 44 px, `--brand-ink` link colour, `--text-base`; open body has 12 px (`--space-3`) above the input; the input fills the column), the `:has(details[open])` rule above, and the single tick row reusing the `.checkline` rules (3468-3471; extend their selectors from `.police-letter-row .checkline` to `.police-letter-check .checkline`). 12 px between rows, the Edit summary and the tick (rule 3).
- **F1:** scope to the property settings form so other pages do not move: `body.v2 .property-settings-form .help-tip-btn` (check that the editor form class is `property-settings-form`, `_property_editor.html:139`). At `max-width:1023px`: the visible mark is the 18 px ring (`::after`, 18 x 18, centred) with no white fill (`background:transparent`); the hit area is an invisible 44 x 44 box that does **not** add height to the label row (negative margins `-13px` top and bottom as 1626 already does, but keep `margin-right` so the box does not push the label or overlap the next control); the `?` sits on the label line, and the label is 6 px above its input (`.field-label-row{margin-bottom:6px}` for this form, below 1024 px; today 1859 sets 12 px for settings lanes: check which rule wins with a grep, then override under `body.v2 .property-settings-form`). Measure with the browser test (below): the gap from the label's bottom to the input's top is 6 px (tolerance 2), the "?" ring is 18 x 18, its tappable box is at least 44 x 44, and the first input in `#ubyport` starts no lower than at 1280 plus the label's own height.
- **F2:** `#automation_mode` shows its full selected text at 390 (see the short keys); `min-width:0;width:100%;text-overflow:clip` (never an ellipsis); `padding-inline` from tokens. The test measures it.
- **F3:** below 1024 px, `body.v2 .property-settings-form #ubyport .actions .ui-btn` (the test button) is `display:flex;width:100%;min-height:44px;justify-content:center;white-space:normal` and uses the primary look (class change in the template: `ui-btn-primary` instead of `ui-btn-secondary`, on all widths, so it is one look). Check `grep -n "ui-btn-primary" App/app/static/*.css | head -5` for the primary class name. The page's Save row (end of the form) stays the form's one Save; if the layout lint or the screenshots show two coral primaries competing in the Police section at 390, STOP and report (this is a rule 4 and 5 call for the orchestrator); do not hide either button.

### Anchors (re-check each with `grep -nF`; if one is missing: STOP)

1. `App/app/templates/_property_editor.html`: `id="police-letter-check"` (330), `name="letter_ok_{{ row.name }}"` (345), `{{ text_field('uby_idub'` (355), `{{ text_field('uby_ws_user'` (358), `{{ text_field('uby_mark'` (376), `formaction="{{ base_url }}/test-connection"` (384), `id="automation_mode"` (395), `id="police-letter-form"` (476), `data-dirty-start="1"` (139).
2. `App/app/police_letter.py:386` `def confirmed_fields`.
3. `App/app/routes/admin.py`: `def _letter_rows_from_form` (2286), `if letter_unconfirmed:` (2376), `police_letter.confirmed_fields(form)` at 2378, 2612, 2825, 3494.
4. `App/app/host_i18n.py`: `"police_letter.confirm": "Matches my letter"` (4574) and `"police_letter.confirm": "Souhlasí s dopisem"` (5443); `App/app/host_vi_i18n.py:1928`.
5. `App/app/static/app2.css`: `body.v2 .help-tip-btn{` (1624), the `@media (max-width:1023px){body.v2 .help-tip-btn{width:44px` rule (1626), `body.v2 .police-letter-row{` (3463). `App/app/templates/base.html:23` `app2.css?v=20261110-1086b`.
6. `App/tests/test_police_letter_flow.py` `def test_a_missing_tick_refuses_the_save_on_both_paths` (468) and `def test_two_missing_ticks_are_two_errors` (892); `App/tests/test_required_stars.py:70` `test_editor_police_fields_are_starred_and_aria_required`.

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/templates/_property_editor.html` | edit | check block, three fields hidden while shown, test button class, select option keys |
| `App/app/police_letter.py` | edit | `confirmed_fields` reads the single `letter_ok` |
| `App/app/routes/admin.py` | edit | one `letter_ok` error; pass the single tick state to the template (only the `letter_unconfirmed` block and `_letter_rows_from_form`) |
| `App/app/host_i18n.py`, `App/app/host_vi_i18n.py` | edit | new keys, reworded `confirm_missing`, removed `police_letter.confirm`, short select keys |
| `App/app/static/app2.css` | edit | section 2 CSS |
| `App/app/templates/base.html` | edit | line 23: `app2.css?v=20261110-1086b` becomes `app2.css?v=20261111-1097a` (a second change: `1097b`). `app.js` and `host.css` keys stay. |
| `App/tests/static_versions.json` | regenerate | from `App/`: `.venv/bin/python tests/test_static_versions.py --write` |
| `App/tests/test_police_letter_flow.py` | edit | single tick, section 4 step 3 |
| `App/tests/test_host_police_letter_browser.py`, `App/tests/test_host_police_letter_guard_browser.py` | edit | single tick, Edit, geometry, section 4 steps 4 and 5 |
| `App/tests/test_required_stars.py` | edit only if it fails | the police star assertions (the single tick keeps one `req-star`) |
| `docs/tasks/screenshots-1097/` | create | the PNGs (step 7) |
| `docs/tasks/1097-report.md` | create | the report; set `Status: review` here |

## 4. Steps (commit after each: `1097 step k`)

1. `git fetch origin main`, `git merge origin/main`. Confirm the anchors; a missing one: STOP. Then `grep -rn "letter_ok_\|police_letter.confirm\b\|police_letter.confirm\"" App/app App/tests | cut -c1-120 | head -60` to list every use you must change.
2. **Server and copy:** `police_letter.confirmed_fields`, the `admin.py` block, the i18n keys (cs, en, vi), then the template. Check block, Edit `details`, hidden duplicates, the single tick, the test button class, the select option keys.
3. **`test_police_letter_flow.py`** (change the existing tests; do not delete coverage):
   - Replace every per-field `letter_ok_<name>: "1"` in posted data with `letter_ok: "1"`.
   - `test_a_missing_tick_refuses_the_save_on_both_paths` (468): with no `letter_ok` the save and `/test-connection` answer 400, nothing is saved (read the row with the db helper), and the page holds exactly one `letter_ok-error`.
   - `test_two_missing_ticks_are_two_errors` (892) becomes `test_one_missing_tick_is_one_error`: with two or three values listed and no tick, exactly **one** error and one `data-field-error`, and no `letter_ok_` anywhere in the page.
   - **New** `test_a_stale_per_field_tick_does_not_confirm`: posting old `letter_ok_uby_idub=1` etc. without `letter_ok` is refused (400).
   - **New** `test_the_check_block_shows_each_value_once`: after a paste, the page has exactly one `id="letter_ok"`, no `letter_ok_uby_`, each of the three values appears as an `<input ... value=...>` once and in `.police-letter-value` once (no second `text_field` copy: count `name="uby_idub"` == 1), each row has a `<details class="police-letter-edit">`, `req-star` count in the block is 1, and the three inputs sit **inside** the `details`.
   - **New** `test_edit_value_is_saved_with_the_tick`: paste, post the three values with `uby_idub` changed to a new valid value and `letter_ok=1`: the saved IDUB is the new one (the edited value wins; the existing "saved now" and source behaviour is unchanged).
   - **New** `test_an_unfound_value_keeps_its_own_field`: a letter with no IDUB: the page still has the normal `uby_idub` field below (once), and only the found values are in the check block.
   - A save without a password still skips the client (`letter_saved_untested`); with a password exactly one read-only client: keep those tests, only the posted tick changes.
4. **`test_host_police_letter_browser.py`**, at 390, 768 and 1280, update the existing tests, and add:
   - Turbo and no-JavaScript (`java_script_enabled=False`): after "Read the letter" the block shows one tick (`#letter_ok`, `autofocus` without JavaScript) and **no** "Matches my letter" text; the three values appear once.
   - **No-JavaScript Edit:** click the "Edit" summary of the IDUB row (a `details` toggles with no script): the input `#uby_idub` becomes visible, the row's `.police-letter-value` is hidden, type a new value, tick, Save: the saved value is the new one (read it with the db helper).
   - Click Save with no tick: the browser blocks it (`required`). "Save and test connection" with no tick (`formnovalidate`): 400, one error under the tick, saved row unchanged.
   - Tick, type a password, Save with `fake_client`: flash "Saved. The login and password work."; exactly one client, read-only calls only. Save with no password: `letter_saved_untested`, no client built.
   - **Geometry:** one tick row and each Edit summary at least 44 px on the phone; 12 px or more between rows, Edit and tick; the three duplicated inputs are not visible below the block (`#uby_idub` is inside the check block only); no sideways scroll; no label cut off.
   - **F1** (390): in `#ubyport`, for `#uby_ws_password`'s label row: the help ring is 18 x 18 (+/- 1), the button's box is at least 44 x 44, the label bottom to input top is 6 px (+/- 2), and the help button does not increase the label row height (row height <= label height + 2).
   - **F2** (390): the `#automation_mode` selected option text fits: measure with `page.evaluate` (a canvas `measureText` with the select's computed font, or a hidden span with the same font) and assert text width <= select `clientWidth` minus its padding and arrow (about 28 px), for every option and for both `cs` and `en` (the host language cookie as the model test sets it).
   - **F3** (390): the test button's width equals its container's width (+/- 1), height >= 44, and it is not `ui-btn-secondary` coloured (assert the class `ui-btn-primary`); at 1280 it is not full width.
   - Screenshots only when `UBYHOST_SHOTS_1097=<dir>` is set (as 1086 did with `UBYHOST_SHOTS_1086`).
5. **`test_host_police_letter_guard_browser.py`:** the dirty-start test (line 88) ticks `letter_ok_*` boxes today: change it to the single `#letter_ok`. Keep the 1096 tests (the Save row and the leave warning at load before any input) green and untouched in meaning. The discard-warning tests need no change.
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
2. `.venv/bin/python -m pytest tests/test_police_letter_parser.py tests/test_required_stars.py tests/test_property_form_save.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_host_i18n.py tests/test_privacy_first.py -q --tb=short -x 2>&1 | tail -30`
3. v2 row: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q --tb=short -rs 2>&1 | tail -30`

Repo root: `python3 scripts/design_lint.py 2>&1 | tail -30` and `python3 scripts/context_lint.py 2>&1 | tail -30`. CI runs the rest.

Known failures on clean main, not yours (name them in the report, do not fix): `test_design_guardrails_browser.py::test_every_host_page_passes_the_layout_guard` (`guest-new 390: tap-target-small "Cancel" 43 < 44`), `test_host_ux_acceptance.py` (guide page, `cs`, 390, a `help-tip-btn`) and `test_reporting_help_0097.py` (a fee help button). If the F1 change makes another help-tip test fail on a page other than the property editor: you changed too much; scope the rule to `.property-settings-form` and retry once.

## 7. Acceptance

- [ ] One tick, `letter_ok`, replaces the three; no `Matches my letter` or `Souhlasí s dopisem` text and no `police_letter.confirm` key remain (`grep -rn "police_letter.confirm\b" App | head` is empty apart from `confirm_all` and `confirm_missing`).
- [ ] Each found value is shown once, with its own Edit; Edit works without JavaScript (`details`), and an edited value is saved. The three fields are not repeated below while the block is shown; an unfound value keeps its normal field.
- [ ] A save and a `/test-connection` without the tick answer 400 and save nothing (server test); an old per-field tick does not confirm.
- [ ] 1085/1086/1096 behaviour intact: no password means no client; with one, exactly one read-only client; discard warning; dirty at load; the password never in the page.
- [ ] F1, F2, F3 measured by browser tests at 390; 768 and 1280 unchanged in look.
- [ ] cs and en keys together (vi as the parity test demands); no unused key left; no em dash.
- [ ] Layout lint green, 0 skipped, no new `ALLOW`. Screenshots of find, check, error (and plain, edit-open) at 390/768/1280, one line per file in the report. The design-system checklist (section 5 of the design system) is ticked in the PR: rules 3, 4, 7, 8, 9 named.
- [ ] `app2.css` key bumped (`1097a`, then `1097b` per further change); `app.js` and `host.css` keys unchanged; `git diff --stat origin/main` touches only section 3 files.

PR text (the orchestrator opens the PR; you write it into the report): per page, what you saw at 390, 768 and 1280 in the find, check and error states; the checklist; the two outbound-request and personal-data lines: none (no new field, no new request).

## 8. Stop and ask

STOP and report `blocked` if: an anchor is missing; the fix needs `app.js`, a parser change, a password-handling change, a new route or a new dependency; the three inputs cannot post from inside a closed `details` (browser test shows the value missing); the layout lint shows two competing primaries (F3) or a new finding you cannot fix inside section 3 files; a browser test skips; the same test fails twice on the same cause (attempt 3 of 3); **60 tool calls** or 60k tokens (finish the step, commit, write the partial report with what is done and what is left). Never silence a finding, never add an `ALLOW`, never ask the owner.

## 9. Report

`docs/tasks/1097-report.md`: files changed; commands run with pass, fail and skip counts; the acceptance list ticked; one line per screenshot; the design-system checklist; the F1 to F3 measured numbers (ring, hit box, label gap, select text width against room, button width); deviations; open questions (for example the vi wording).
