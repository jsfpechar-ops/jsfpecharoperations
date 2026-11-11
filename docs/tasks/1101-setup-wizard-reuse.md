# 1101: a new property walks through the setup wizard to "You're ready"

Status: todo
Tier: B | Depends on: 1100 (police paste and autofill, branch `claude/1100-police-autofill`, brief at c75db35d; must be merged to main first) | Base commit: 169ee203 (anchors below are at this commit; 1100 shifts them, so re-grep by the quoted text) | Branch: claude/1101-setup-wizard-reuse
Executor: Haiku 5.5 | Attempts: 3 at most | Likely two sessions: stop at 30 tool calls (executor.md), commit, report `Done: steps 1 to k`
Report: docs/tasks/1101-report.md

## 1. Objective

Owner feedback (Josef, 2026-11-11, testing live after #899): the short editor does not lead a new host anywhere; after police it stops and he had to pick police and calendar himself. "No need to build it all new, just use the code from the last wizard, it walked them very well." Also: no "Archive property" during setup, and say "property", never "apartment", in copy.

So: a new property goes back into the existing step wizard (`/apartments/{id}/setup/{step}`), which is walked step by step to the end, and the end is the 1099 "You're ready" card. Nothing new is built where the wizard already does it. The short editor stays for editing a property that is set up.

### Orchestrator decisions (2026-11-11)

- **Q1 (decided):** the guest message template on the guest link step drops "apartment" too (en and cs, wording in D7). It is part of the wording check; nothing on the setup pages is excluded.
- **Q2 (decided):** keep the existing order: property (if needed) → calendar → police → guest link → done.
- **Q3 (decided):** wizard pages keep having no unsaved-changes guard (no `data-unsaved-guard`, no `data-dirty-start` on any wizard form, as today). Each wizard step saves on its own button; a paste that fills the police boxes and is then left by Back is not guarded, the same as any other wizard step today. The editor's 1100 dialog behaviour is untouched.

## 2. Context (verified with grep at 169ee203)

- **Wizard steps:** `App/app/property_setup.py` `STEPS = (` (line 16: property, calendar, police, guest_link); `RETIRED_STEPS` (23) stay retired. `mark` (141) returns early on a finished state. `finish` (160). `mark_tested` (182) returns early on a finished state. `wizard_url` (224). `next_applicable_step` (257) and `prev_applicable_step` (274) skip `property` when `property_details_complete` (320) is true. `may_view_step` (291). `_resolved` (330): police is resolved by `facts["report_complete"]` alone, not by its mark. `step_status` (351): police is `waiting` only while marked waiting **and** not report-complete.
- **Wizard routes:** `App/app/routes/onboarding_wizard.py`: `wizard_setup_prefix` (32, `/apartments/{id}/setup/`), `_wizard_context` (63; has `report_complete` local, `permalink`, `pin`, `has_password`, `celebrate`, `checklist`, `prev_step`, `wizard_next_return_to`; `payments` is already imported), `render_wizard` (193), `refuse_setup_save` (220; renders the step with `draft` and `police_errors`, status 400), `setup_step` (301; a step after the guide's current step redirects to `guide["url"]`), `setup_action` (336; Wait marks police `waiting` only when the guide's current step is police).
- **Wizard layout:** `templates/setup_wizard/_layout.html`: the count line `wiz-count` comes from `wizard_number` (the step's place in `STEPS`, so with property skipped calendar reads "Step 2 of 4"; as today, not changed) and is empty on `done`; the meter `setup-wizard-progress` shows while a guide exists; the Back link `setup-wizard-back` from `prev_step` (none on the first applicable step). `values = draft if draft is defined else apartment`.
- **Wizard police step:** `templates/setup_wizard/police.html` (76 lines): head row `<div class="field-label-row police-section-head">` with an `<h2>` whose `help_tip('wizard-police-credentials-help', t('apartment.form.ubyport.no_credentials'), ...)` and the sample link; `<form ... id="police-form">` posting to `/apartments/{id}` with hidden `_csrf`, `return_to` (`wizard_next_return_to`), `setup_step=police`, `internal_name`, `legal_entity_id`, `city_en`, `default_purpose`, `step=police`; its own `text_field` macro (with `required`) and the IDUB, login, password (`type="password"`), zkratka, facility (`facility_help`) and contact boxes; then the automation choice cards; footer: "Wait" (`setup-wizard-wait`, `formaction=".../setup"`, `value="wait"`, `formnovalidate`) then "Save and continue" (`wizard.save_continue`).
- **Wizard save in `admin.py`:** `_save_apartment_form` (2852) saves only the step's fields (`_wizard_step_payload`) when `setup_step` is posted, and a refused save goes to `refuse_setup_save`. `_setup_after_save(request, apartment_id, form, return_to, *, saved_message="")` (about 2716-2798): for `setup_step=police` it marks `automation` done, marks police done only when report-complete, re-renders the police step with the missing labels when police is not resolved, returns `_back(return_to, msg=saved_message)` when it is, and returns `_back(return_to, ...)` at once for a finished or hidden setup.
- **The #899 change to undo:** `apartment_create` (`admin.py:1827`), just after `# 0096: a new property starts its guided setup at the calendar.`, redirects to `f"/apartments/{apartment_id}?view=settings",` (1877). Before #899 (commit 66785344) it was `f"/apartments/{apartment_id}/setup/calendar",`. `setup_step` sends a property whose details are incomplete from `/setup/calendar` to the `property` step (guide redirect), so the revert is safe.
- **Connection test:** `test_connection` (`admin.py:3521`): `return_to = _form_return_to(...)`; saves posted credentials through `_save_apartment_form` (a refusal returns the wizard page when `setup_step` is posted); the 1085 lockout branch and a failed test both `_back(return_to, ...)`; on `ok` `property_setup.mark_tested(apartment_id)` (3557) then `_back(return_to, msg=_flash(request, "flash.apartments.connection_ok"))`.
- **No-JS letter read:** `police_letter_read` (`POST /apartments/{id}/police-letter`, `admin.py:3608`). 1100 keeps its HTML path for no JavaScript and adds a JSON path for `Accept: application/json` (P2 of 1100); the HTML path ends with `_render_property_detail(apartment_id, request, extra=extra, status_code=422)` and `Cache-Control: no-store`; it reads the form, then `del letter_text, form`.
- **1100's police partial:** `App/app/templates/_police_fields.html` (created by 1100, P3): the paste `details` (`textarea#letter_text` with `form="police-letter-form"` and `data-letter-paste`, read button `data-letter-read`), the status line `#police-letter-status` (`data-letter-status`), the hidden `letter_fields` (`data-letter-fields`, `data-letter-fields-initial`), the IDUB, login, password (`type="text"`, no `value` on a GET), zkratka, facility and contact boxes, and the "Save and test connection" button (`formaction="{{ base_url }}/test-connection"`). Its top comment lists the variables it reads (1100: `apartment`, `letter_fill`, `letter_status`, `has_password`, `base_url`, `letter_first`, `facility_help` or how it builds it). The page must render a separate `form#police-letter-form` outside the form that holds the boxes (no nested forms). 1100's JS finds the target form from the boxes (`document.getElementById("uby_idub").form`) and uses only `data-letter-*` hooks. The editor's section head, sample link, `why.police` and `#automation` stay in the editor. 1100 leaves `setup_wizard/police.html` alone.
- **Ready card (1099):** `_property_editor.html` 141-157: `{% if ready_card %}` then `<section class="ui-section-card ready-card" id="setup-ready" ... data-ready-card>` (reads `ready_qr`, `permalink`, `pin`, `t`) then `{% endif %}`. CSS `body.v2 .ready-card*` in `app2.css` (about 3490) is page-independent. `_render_apartment_detail` (about 2154-2179) sets `ready_card` from `celebrate_once` only while first setup is complete.
- **Archive:** `_property_editor.html` 237-252 `<div class="prop-archive-row" id="sec-archive">` (Archive, or Restore when `apartment.archived_at`). No wizard template has an archive control. The property list row menu (`apartments.html`) is not a setup page: out of scope.
- **Continue setup card:** `_property_editor.html` 90: `href="{% if first_setup %}/apartments/{{ apartment.id }}?view=settings{% else %}{{ setup_progress.continue_url }}{% endif %}"` (1099).
- **Wording:** `wizard.guest_link.message_template` (`host_i18n.py` en 8554, cs 8623; no vi key) says "Find your apartment", "signs to your apartment", "in the apartment"; cs "apartmán" three times. It renders in `setup_wizard/guest_link.html` `textarea#wizard-guest-message` (35). No test pins that text. `App/app/onboarding.py` `WIZARD_STEPS` is the account onboarding: do not touch it.
- **Existing tests that pin what changes:** `test_first_setup_open_section.py:152` `test_create_redirects_to_the_editor`; `test_onboarding_wizard_browser.py:112` (`?view=settings` in the location), `:129` `test_create_lands_on_the_editor_in_first_setup`, and the walk at about 190-200 that clicks the police primary (`button[form="police-form"]:not([value=wait])`) with no fake client; `test_property_create_browser.py:127`, `:441`, `:471`; `test_property_navigation_browser.py:496`, `:529`; `test_required_stars.py` (`AUDITED` list and `test_editor_police_fields_are_starred_and_aria_required`, which reads the template that holds `text_field('uby_idub'`; 1100 may already point it at `_police_fields.html`).

## 2b. Design

**D1. Step order (Q2, unchanged `STEPS`):** 1 Property details (skipped when the create form completed them, as today), 2 Connect your calendar, 3 Police reporting, 4 Guest link and PIN, then `done` = the ready card. Stay fee, door lock and test run stay off the wizard (0884) and stay on the done page's "next" list. The count line and meter stay as today.

**D2. Every step leads on.** Property, calendar and guest link keep their current buttons and targets (`wizard_next_return_to`). Police (D4) goes to the next step after a passing test. Back: the existing `prev_step` link on every step after the first applicable one. The count line shows on every step except `done` (as today).

**D3. Create lands in the wizard.** Revert the #899 redirect to `f"/apartments/{apartment_id}/setup/calendar",`. `property_setup.start()` stays.

**D4. Police step = 1100's `_police_fields.html`, then the test.**
- **Partial flag (the only change to the partial):** wrap the partial's "Save and test connection" `<div class="actions">...</div>` in `{% if not police_in_wizard %}...{% endif %}`. Nothing else in the partial changes; the editor sets nothing, so it renders the same HTML as before (the editor tests prove it). If the partial cannot render in the wizard without another change (it uses an id of the editor's settings form, a macro or variable it does not define or list, or the JS needs `#property-settings-form`): STOP (section 8).
- **`setup_wizard/police.html`:**
  - Keep the head row but drop the `help_tip('wizard-police-credentials-help', ...)` from the `<h2>` (the partial already shows `apartment.form.ubyport.no_credentials` as a line; rule 9). Keep the sample link and `wizard_help`.
  - Inside `#police-form`, after the hidden inputs, replace the IDUB, login, password, zkratka, facility and contact boxes (from `<div class="grid">{{ text_field('uby_idub'` to the `</div>` after `uby_contact`) with:
    ```jinja
    {% set police_in_wizard = true %}
    {% set base_url = '/apartments/' ~ apartment.id %}
    {% set letter_fill = letter_prefill or {} %}
    {% set letter_first = not letter_rows and not letter_status %}
    {% with apartment = values %}{% include "_police_fields.html" %}{% endwith %}
    ```
    plus a `set` for any other variable named in the partial's top comment that the editor builds in the template (for example `facility_help`: keep the wizard's existing `{%- set facility_help -%}` block above the include). `values` keeps typed values on a refused save (the partial reads `apartment`). Delete the wizard's own `text_field` macro if nothing else in the file uses it. Keep every hidden input and the automation choice cards.
  - `return_to` hidden input: `/apartments/{{ apartment.id }}/setup/police` (was `wizard_next_return_to`), so a failed test, the lockout message and a refused save all show on the police step.
  - After `</form>` of `#police-form`, still inside `wizard_content`, add the letter form the partial needs:
    ```html
    <form id="police-letter-form" method="post" action="/apartments/{{ apartment.id }}/police-letter" data-discard-warning="{{ t('police_letter.discard_warning') }}">
      <input type="hidden" name="_csrf" value="{{ csrf_token }}">
      <input type="hidden" name="setup_step" value="police">
    </form>
    ```
    (copy any other attribute or hidden input 1100 gives the editor's `form#police-letter-form`).
  - Footer: keep "Wait" first, as it is. Replace "Save and continue" with `<button class="ui-btn ui-btn-primary" type="submit" form="police-form" formaction="/apartments/{{ apartment.id }}/test-connection" formmethod="post" formnovalidate>{{ t('apartment.form.test_connection') }}</button>`.
- **`test_connection`:** after the existing `property_setup.mark_tested(apartment_id)` line and before its `return _back(return_to, ...)`, add only this branch (the save, the lockout guard and the test are not touched):
  ```python
  from .onboarding_wizard import wizard_setup_prefix

  if return_to.startswith(wizard_setup_prefix(apartment_id)) and _form_str(form, "setup_step") == "police":
      property_setup.mark_tested_in_wizard(apartment_id)
      stored = property_setup.load(apartment_id)
      nxt = "done" if stored and stored["finished"] else (
          property_setup.next_applicable_step("police", apartment, lock_available=False) or "done"
      )
      advanced = _setup_after_save(
          request,
          apartment_id,
          form,
          property_setup.wizard_url(apartment_id, nxt),
          saved_message=_flash(request, "flash.apartments.connection_ok"),
      )
      if advanced is not None:
          return advanced
  ```
  `_setup_after_save` is the wizard's existing advance: it marks automation and police exactly as "Save and continue" did (police done only when report-complete; once each), and when a box is still missing it shows the police step with the missing labels instead of moving on. A finished setup (Wait, finish, test later) goes to `done`. Failures never reach the branch, so they stay on police.
  New in `property_setup.py`, after `mark_tested`: `def mark_tested_in_wizard(apartment_id: int) -> None:` with docstring `"""1101: a passing test from the wizard police step, finished or not."""`; `state = load(apartment_id)`; `if state is None: return`; `state["tested"] = True`; `_save(apartment_id, state)`. `mark_tested` is not changed.
- **No JavaScript (1100 keeps the server read):** in `police_letter_read`, read `wizard = _form_str(form, "setup_step") == "police"` **before** `del letter_text, form`. In the HTML path only (never the JSON path), replace the final render with: `response = render_wizard(request, apartment_id, "police", extra=extra, status_code=422) if wizard else _render_property_detail(...)` (import `render_wizard` from `.onboarding_wizard` inside the function, as other routes do), then the same `Cache-Control: no-store`. The extra keys `property_view`/`settings_section` are harmless in the wizard.
- `_wizard_context`: when `step == "police"`, add any context default the partial needs that is not set in `police.html` and not handled by Jinja's lenient undefined (attribute access like `section_done.police` on an undefined name fails). List the names with `grep -oE '\b(letter_[a-z_]+|first_setup|section_done|police_[a-z_]+|has_password|base_url)\b' App/app/templates/_police_fields.html | sort -u` and give each a safe default (`letter_rows: []`, `letter_prefill: {}`, `letter_status: ""`, `first_setup: True`, `section_done: {"police": False}`), then `ctx.update(extra)` overrides them as today.

**D5. Done step = the ready card.** Move the editor's `<section class="ui-section-card ready-card" ...>...</section>` (inside `{% if ready_card %}`) into `App/app/templates/_setup_ready_card.html` unchanged; the editor keeps `{% if ready_card %}{% include "_setup_ready_card.html" %}{% endif %}`. In `_wizard_context` for `step == "done"`: `wizard_ready = bool(state and state.get("tested") and report_complete)` and `ready_qr = payments.qr_data_uri(ctx["permalink"]) if wizard_ready else ""` (add both keys to `ctx`; for other steps `wizard_ready=False`, `ready_qr=""`). In `done.html`, when `wizard_ready and not missing_row`, include the partial in place of the `setup-wizard-celebrate` banner (keep the confetti `span` only if `celebrate`, inside nothing else); keep the workflow details, the summary list, the "next" list, the finish note and the actions. When police is waiting (Wait, no values), `done.html` stays as today ("almost", the link back to police). A reload shows the card again (the done page is a summary; the editor's once-only rule is not used here).

**D6. Short editor.** Stays at `/apartments/{id}?view=settings` for every property. Continue setup card href: `{{ setup_progress.continue_url }}` always (drop the 1099 `first_setup` branch). The archive row `#sec-archive` renders only when `not first_setup or apartment.archived_at` (an archived property always keeps Restore). All other 1099 behaviour stays.

**D7. Wording (Q1).** No visible "apartment" on any wizard page (en), including the guest message. In `host_i18n.py` `wizard.guest_link.message_template` change only these parts (keys and placeholders stay):
- en: `3. Find your apartment` → `3. Find your property`; `follow the signs to your apartment` → `follow the signs to the property`; `keep noise down in the apartment and shared areas` → `keep noise down at the property and in shared areas`.
- cs: `3. Najděte svůj apartmán` → `3. Cesta k ubytování`; `podle označení apartmánu` → `podle označení ubytování`; `Prosíme o ticho v apartmánu i společných prostorách` → `Prosíme o ticho v ubytování i ve společných prostorách`.
If a test finds the word in another en string on a setup page, change that en value to "property" (key stays) and list it in the report. URLs (`/apartments/...`) are not copy.

## 3. Files

| Path | Action |
|---|---|
| `App/app/property_setup.py` | add `mark_tested_in_wizard` (D4) |
| `App/app/routes/admin.py` | `apartment_create` redirect (D3); the branch in `test_connection` (D4); the wizard render in `police_letter_read` (D4). No other function. |
| `App/app/routes/onboarding_wizard.py` | `_wizard_context`: police defaults (D4), `wizard_ready`, `ready_qr` (D5) |
| `App/app/templates/_police_fields.html` | the `police_in_wizard` wrap around its test button only (D4) |
| `App/app/templates/_setup_ready_card.html` | create (D5) |
| `App/app/templates/_property_editor.html` | ready-card include; archive row condition; Continue setup href |
| `App/app/templates/setup_wizard/police.html`, `done.html` | D4, D5 |
| `App/app/host_i18n.py` | D7 message template (en, cs) |
| `App/app/static/app2.css`, `base.html`, `tests/static_versions.json` | only if a layout finding needs a wizard-side rule (tokens, under `body.v2`); then bump the `app2.css?v=` key to `20261112-1101a` and regenerate with `.venv/bin/python tests/test_static_versions.py --write` |
| `App/tests/test_setup_wizard_reuse_1101.py` | create (server, no JS) |
| `App/tests/test_setup_wizard_reuse_1101_browser.py` | create (browser, geometry, screenshots) |
| existing tests (step 7) | only the expectations listed there |
| `docs/tasks/screenshots-1101/`, `docs/tasks/1101-report.md` | create |

## 4. Steps (commit after each: `1101 step k`)

1. `git fetch origin main && git merge origin/main`. `git log origin/main --oneline | grep -i 1100 | head -3`: **empty means 1100 has not merged: STOP**, write the report `Status: blocked: 1100 not merged`, commit, end. `ls App/app/templates/_police_fields.html` and `sed -n 1,20p` it (the variable comment); missing: STOP. Re-grep each anchor in section 2 by its quoted text (`STEPS = (`, `def mark_tested`, `def _setup_after_save`, `0096: a new property starts`, `async def test_connection`, `async def police_letter_read`, `id="police-form"`, `data-ready-card`, `id="sec-archive"`, `"wizard.guest_link.message_template"`, `formaction="{{ base_url }}/test-connection"` in `_police_fields.html`, `getElementById("uby_idub")` in `app.js`); a missing one: STOP.
2. Write `test_setup_wizard_reuse_1101.py` (list in step 6) and run it once: it must fail on the unchanged code; put the count in the report.
3. D3 (redirect) and D6 (archive condition, Continue setup href).
4. D4 partial flag; D5 ready-card partial in the editor. Run command 1 (section 6) before going on: the editor must be unchanged.
5. D4 wizard police step: `police.html`, the letter form, footer, `return_to`, `_wizard_context` defaults, `mark_tested_in_wizard`, the `test_connection` branch, the `police_letter_read` wizard render.
6. D5 `done.html` and context; D7 wording. Then make the new server test green. Use `fake_client` with `from tests.test_police_letter_flow import fake_client  # noqa: F401` (a failing test: `fake_client["error"] = UbyportAuthError("refused")`, imported as in that file) and the `host` fixture as `test_wizard_old_look_0953.py` imports it. It covers (plain `TestClient` = no JavaScript):
   - `POST /apartments` (complete form) redirects to `/apartments/{id}/setup/calendar`; with incomplete details the GET of `/setup/calendar` lands on the `property` step.
   - Property, calendar, police and guest link GETs show `wiz-count`; calendar has no `setup-wizard-back` when property was skipped; police and guest link have a Back link to the previous step.
   - Calendar skip goes to `/setup/police`. Police posted to `/apartments/{id}/test-connection` with the wizard form fields (`setup_step=police`, `return_to=/apartments/{id}/setup/police`, the five boxes, a password, `automation_mode=manual`): `ok` → 303 to `/setup/guest_link`, `load(id)["tested"]` true, `steps["police"] == "done"` and `steps["automation"] == "done"`; `auth` → 303 to `/setup/police` with the error, `tested` false, police not done; an `ok` test with `uby_name` empty stays on the police step (`data-setup-step="police"`: a 400 refusal or the 200 missing-fields notice, whichever the code gives), police not done; an invalid IDUB → 400 police step that keeps the typed login (draft) and has no `value=` on `#uby_ws_password`. Wait → `/setup/guest_link`, `tested` false.
   - Guest link done → `/setup/done`; done shows `data-ready-card`, the permalink, the PIN and `<img class="ready-card-qr" src="data:image/png;base64,` only when tested and report-complete, and no `setup-wizard-celebrate` then; after Wait (police empty) done shows the "almost" banner and the `/setup/police` link, no card; a reload of done still shows the card.
   - Wait, finish, then type the values and test from the police step: 303 to `/setup/done`, `tested` true, done shows the card.
   - Police step HTML: `data-letter-paste`, `data-letter-read`, `data-letter-status`, `data-letter-fields` present; one `id="police-letter-form"` outside `#police-form` with `setup_step` = police; `#uby_ws_password` is `type="text"`; no `letter_ok`; no "Save and test connection" inside `#police-form` (only the footer test button, `formaction` ending `/test-connection`); the stored password is not in the page.
   - No-JS letter read: `POST /apartments/{id}/police-letter` with the sample letter text (1100's tests use it) and `setup_step=police` → 422, `data-setup-step="police"`, the boxes filled, `Cache-Control: no-store`; without `setup_step` it still renders the editor.
   - No `/archive` form action on any setup page or on the editor of a first-setup property; a finished property's editor still has `#sec-archive`; an archived first-setup property's editor shows Restore.
   - No visible "apartment" (en) on property, calendar, police, guest link and done: strip `<script>`, `<style>`, tags and attribute values (keep textarea text), then `assert "apartment" not in text.lower()`.
   - The editor of a finished property still opens at `?view=settings`, its police section still has the "Save and test connection" button.
7. Existing tests: change only these expectations (wizard instead of editor; `/setup/calendar` in the location, page URL contains `/setup/`): `test_first_setup_open_section.py::test_create_redirects_to_the_editor` (invert, rename `test_create_redirects_to_the_wizard`); `test_onboarding_wizard_browser.py` (line about 112, `test_create_lands_on_the_editor_in_first_setup`: assert the wizard and rename `..._lands_in_the_wizard`; the walk at about 190-200: install the fake client as in `test_police_letter_flow.py` before clicking the police primary, which is now the test button); `test_property_create_browser.py` (127, 441, 471; drop the extra `page.goto(.../setup/calendar)` that #899 added); `test_property_navigation_browser.py` (496, 529); `test_required_stars.py` only if it still reads the police boxes from `_property_editor.html` or does not list `_police_fields.html` in `AUDITED` (1100 may have done it). `test_host_ux_acceptance.py` and `test_host_unsaved_changes_browser.py`: run them, change nothing unless they fail on the redirect. More than 7 files need edits: STOP.
8. `test_setup_wizard_reuse_1101_browser.py` (`UBYHOST_REQUIRE_BROWSER=1`; widths 390, 768, 1280; model the server thread and the fake client on `test_host_police_paste_browser.py` from 1100): create a property in the browser and walk calendar → police (paste the sample letter text into `#letter_text` as 1100's browser test does; within 2 s the five boxes fill and the status line shows, no page load; press the footer test button with the fake client) → guest link → done with the card. Checks per width: no sideways scroll; footer buttons at least 44 px tall; Back and the primary do not overlap; QR at least 120 px wide and inside the viewport; on police, pasting does not open `#unsaved-dialog` and clicking Back leaves without a dialog (Q3). Once with `java_script_enabled=False` at 390: every step is reachable by its buttons, the read button is visible and its post returns the police step filled, the footer test passes, the card shows. Screenshots `docs/tasks/screenshots-1101/{calendar,police,guest_link,done}-{390,768,1280}.png` (12, `full_page=True`, police after the paste fill) plus `editor-first-setup-390.png` (the editor of a first-setup property, no archive row).
9. UX gate (rules 7 and 10): from `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -rs -x 2>&1 | tail -30`: green, 0 skipped, no new `ALLOW`. Open the 13 screenshots once each. In the report **and the PR** write per page (calendar, police, guest link, done, editor of a first-setup property) and per width what you saw. Paste and tick the design-system checklist (`docs/design/design-system.md`: `grep -n '^## ' docs/design/design-system.md`, read the checklist section only). A finding is fixed in the template or `app2.css`, never silenced.
10. Section 6 commands, then the report.

## 5. Do not touch

`_run_connection_test`, the save, lockout guard and test logic of `test_connection` (only the added branch), `_setup_after_save` (called, not edited), credential handling (`uby_ws_password*`, encryption; the stored password is never rendered), `App/app/ubyport/`, `reporting.py`, `police_letter.py`, filing and `submit_state`, 1100's paste/autofill code and JS and `_police_fields.html` beyond the one flag, `app.js`, `STEPS`/`RETIRED_STEPS`, `setup_action`, `mark`, `mark_tested`, `onboarding.py`, `db.py`, migrations, `retention.py` (`tested` is a non-personal boolean), any dependency, `ALLOW` in `test_layout_lint_browser.py`. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`; never the full suite)

From `App/` (test-map rows: Onboarding and properties, Host pages, Copy and translations, Static files, Any host template, Design system; plus the new files):

1. Server and browser, 0 skipped: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_setup_wizard_reuse_1101.py tests/test_setup_wizard_reuse_1101_browser.py tests/test_onboarding*.py tests/test_property_*.py tests/test_first_*.py tests/test_wizard_*.py tests/test_finish_moment_0274.py tests/test_setup_banner.py tests/test_required_stars.py tests/test_police_letter_flow.py -q --tb=short -rs`.
2. Host pages and design, 0 skipped: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_*.py tests/test_host_geometry.py tests/test_design_*.py tests/test_design_guardrails_browser.py tests/test_0884_wizard_geometry_browser.py tests/test_0710_v2_mockup_match_browser.py -q --tb=short -rs`.
3. Copy and static: `.venv/bin/python -m pytest tests/test_*_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py tests/test_icons_marks_1061.py tests/test_remove_legacy_actions.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_privacy_first.py -q --tb=short -x`.
4. Filing row once, read-only proof that the connection test is unchanged: `.venv/bin/python -m pytest tests/test_police_*.py tests/test_ubyport_*.py tests/test_submission_*.py -q --tb=short`.

Repo root: `python3 scripts/design_lint.py 2>&1 | tail -30` and `python3 scripts/context_lint.py 2>&1 | tail -30`.

Known failures on clean main (name them, do not fix): `test_host_ux_acceptance.py` guide page, `test_reporting_help_0097.py`.

## 7. Acceptance

- [ ] `POST /apartments` lands on the wizard; a new property is walked property (if needed) → calendar → police → guest link → done, each step's button going to the next, with Back on every step after the first applicable one.
- [ ] The police step shows 1100's `_police_fields.html` (the same partial as the editor, no copy), with its own `form#police-letter-form`; no Read button with JS, no letter tick; a passing test sets `tested` and goes to the next step (or shows the missing boxes); a failed test, the lockout message and a refused save stay on police.
- [ ] Done shows the 1099 ready card (link, PIN, QR) once police is tested and complete; after Wait it shows "almost" with the way back to police; Wait, finish, test later reaches the card.
- [ ] No archive control on any setup page or on a first-setup editor (Restore kept for an archived property); no visible "apartment" on setup pages (en), guest message included; cs message template updated.
- [ ] Works without JavaScript end to end (server test plus the no-JS browser run, letter read included).
- [ ] The editor still opens for a set-up property and renders as before (editor tests unchanged and green).
- [ ] `git diff origin/main -- App/app/ubyport App/app/reporting.py App/app/police_letter.py App/app/onboarding.py App/app/static/app.js` is empty; in `admin.py` only the three named places changed; `_police_fields.html` differs only by the `police_in_wizard` wrap.
- [ ] New server test failed before (count in report) and passes after; browser tests 0 skipped; layout lint green, no new `ALLOW`; 13 screenshots and per-page, per-width notes in the report and PR; checklist ticked; no new dependency, no schema change, no outbound request.

## 8. Stop and ask

STOP and report `blocked` if: 1100 has not merged or `_police_fields.html` does not exist; an anchor is missing; the partial cannot render inside `#police-form` without a change beyond the one flag (a variable or macro it does not list, an id of the editor's settings form, or JS that needs `#property-settings-form`); a step needs `app.js`, a migration, a dependency or a change to the test logic; `permalink` or `pin` is missing from the done context; a test fails twice on the same cause; more than 7 existing test files need edits; 30 tool calls (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to 10.`).

## 9. Report

`docs/tasks/1101-report.md` (executor.md format): files changed, each command with its last 5 lines and counts (0 skipped), the failing count from step 2, the per-page and per-width notes, the ticked checklist, the 13 screenshot names, every existing test expectation changed (names), and anything left.

## 10. Owner questions

None open. Q1 to Q3 were decided by the orchestrator on 2026-11-11 (section 1).
