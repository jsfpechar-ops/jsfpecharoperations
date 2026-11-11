# 1101: a new property walks through the setup wizard to "You're ready"

Status: todo
Tier: B | Depends on: 1100 (police paste and autofill, branch `claude/1100-police-autofill`; must be merged to main first) | Base commit: 169ee203 (anchors below are at this commit; 1100 shifts them, so re-grep by the quoted text) | Branch: claude/1101-setup-wizard-reuse
Executor: Haiku 5.5 | Attempts: 3 at most | Likely two sessions: stop at 30 tool calls (executor.md), commit, report `Done: steps 1 to k`
Report: docs/tasks/1101-report.md

## 1. Objective

Owner feedback (Josef, 2026-11-11, testing live after #899): the short editor does not lead a new host anywhere; after police it stops and he had to pick police and calendar himself. "No need to build it all new, just use the code from the last wizard, it walked them very well." Also: no "Archive property" during setup, and say "property", never "apartment", in copy.

So: a new property goes back into the existing step wizard (`/apartments/{id}/setup/{step}`), which is walked step by step to the end, and the end is the 1099 "You're ready" card. Nothing new is built where the wizard already does it. The short editor stays for editing a property that is set up.

## 2. Context (verified with grep at 169ee203)

- **Wizard steps:** `App/app/property_setup.py` `STEPS = ("property", "calendar", "police", "guest_link")` (line 16); `RETIRED_STEPS` (23) stay retired. `wizard_url` (224) builds `/apartments/{id}/setup/{step}`. `next_applicable_step` (257) and `prev_applicable_step` (274) skip `property` when `property_details_complete` (320) is true. `may_view_step` (291) is the can-render check. 1099 added `mark_tested` (182), `is_first_setup`, `section_done`, `setup_complete`.
- **Wizard routes:** `App/app/routes/onboarding_wizard.py`: `_wizard_context` (63; gives `prev_step`, `wizard_next_return_to`, `permalink`, `pin`, `has_password`, `celebrate`, `checklist`), `render_wizard` (193), `_posted_setup_step` (212), `refuse_setup_save` (220), `GET /apartments/{id}/setup` `setup_entry` (278, sends to `/setup/calendar` or the current guide step), `GET .../setup/{step}` `setup_step` (301), `POST .../setup` `setup_action` (336; marks the step, goes to the next, `finish()` then `/setup/done`).
- **Wizard layout:** `templates/setup_wizard/_layout.html` already has the step indicator (`wiz-count` "Step n of total · name", `setup-wizard-progress` meter, `wizard.done_count`) and the Back link (`setup-wizard-back`, from `prev_step`). Steps: `property.html`, `calendar.html`, `police.html` (76 lines, its own IDUB/login/password/zkratka/facility fields, no paste, no test), `guest_link.html`, `done.html`.
- **Wizard saves in `admin.py`:** `_wizard_setup_step` (1709), `_wizard_step_payload`, and the advance path after a save (about 2725-2790, starts `from .onboarding_wizard import wizard_return_to, wizard_setup_prefix`). `_setup_progress` (2019; `continue_url` = `wizard_url(id, "calendar")`).
- **The #899 change to undo:** `apartment_create` (`admin.py:1827`), just after the comment `# 0096: a new property starts its guided setup at the calendar.`, redirects to `f"/apartments/{apartment_id}?view=settings",` (line 1877). Before #899 it was `f"/apartments/{apartment_id}/setup/calendar",`. A property whose details are incomplete is sent from `/setup/calendar` to the `property` step by `may_view_step`, so the revert is safe.
- **Connection test:** `test_connection` (`admin.py:3521`) saves the posted police fields first, tests, and on `ok` calls `property_setup.mark_tested` (3557) then redirects to `return_to`. `apartment_update` never auto-tests when `setup_step` is posted (2649). `mark_tested` returns early on a finished state.
- **No-JS letter read:** `police_letter_read` (`POST /apartments/{id}/police-letter`, `admin.py:3607`) renders the property page (`_render_property_detail(..., extra=extra, status_code=422)`) with `letter_rows`, `letter_prefill`, `letter_check`, `letter_status`. 1100 may change this route; re-read it after the merge.
- **Short editor police section:** inline in `templates/_property_editor.html` (618 lines): `<section class="panel property-section ui-section" id="ubyport">` (337) to its `</section>` (about 434), using the editor macro `text_field` (31; `aria-required`, no `required`), `base_url` (29), `letter_*`, `first_setup`, `section_done`, `has_password`. The test button is `formaction="{{ base_url }}/test-connection"` (431). There is no police partial on main; check again after 1100.
- **Ready card (1099):** `_property_editor.html` 142-157, `{% if ready_card %}<section class="ui-section-card ready-card" id="setup-ready" ...>` with `ready_qr` (`payments.qr_data_uri`), `permalink`, `pin`, `copy` buttons. Shown by `_render_apartment_detail` only while `is_first_setup` (about 2154-2179).
- **Archive:** `_property_editor.html` 237-252, `<div class="prop-archive-row" id="sec-archive">`. No wizard template has an archive control (grep `archive` in `templates/setup_wizard/`: none).
- **Continue setup card:** `_property_editor.html` 90, the href `{% if first_setup %}/apartments/{{ apartment.id }}?view=settings{% else %}{{ setup_progress.continue_url }}{% endif %}` (1099).
- **Wording:** no `wizard.*` / `setup_guide.*` en value says "apartment" except the guest message template `wizard.guest_link.message_template` (`host_i18n.py` 8554; open question Q1). `App/app/onboarding.py` `WIZARD_STEPS` is the account onboarding (welcome, name, address, bookings), not this wizard: do not touch it.

## 2b. Design

**D1. Step order (unchanged `STEPS`, no reorder):** 1 Property details (operator, address, accommodation; skipped when the create form already completed them, as today), 2 Connect your calendar, 3 Police reporting, 4 Guest link and PIN, then `done` = the ready card. Stay fee, door lock and test run stay off the wizard (0884) and stay on the done page's "next" list. The indicator counts only applicable steps, as today.

**D2. Every step leads on.** Property, calendar and guest link keep their current Save/continue buttons and targets (they already go to `wizard_next_return_to`). Police (D4) goes to the next step after a passing test. Back: the existing `prev_step` link on every step after the first applicable one; the first step has none (nothing before it). The step indicator shows on every step and on `done`.

**D3. Create lands in the wizard.** Revert the #899 redirect (2. Context). `property_setup.start()` stays.

**D4. Police step = the 1100 police block, then the test.**
- One shared partial `App/app/templates/_police_connection.html`, rendered by the editor and by `setup_wizard/police.html`. If 1100 already made a partial that holds the paste box and the police fields, use that one and skip the extraction. Otherwise move the `<section ... id="ubyport">` block from `_property_editor.html` into the partial unchanged, put `{% include "_police_connection.html" %}` in its place, and copy the editor's `text_field` macro into the top of the partial under the name `police_text_field` (do not rely on the caller's macros). The editor page must render the same HTML as before (the editor tests prove it).
- The partial reads one new flag, `police_in_wizard` (default false). When true it leaves out its own "Save and test connection" button and the "automation timing" link (the wizard has the timing choice cards on the same page and the button in its footer). Nothing else differs.
- `setup_wizard/police.html`: replace the IDUB, login, password, zkratka, facility and contact fields with `{% set police_in_wizard = true %}{% include "_police_connection.html" %}` inside `#police-form`. Keep every hidden input of `#police-form` and the automation choice cards below. The paste box, instant autofill, visible password, facility name, zkratka and property name all come from 1100: no "Read the letter" button, no "values match my letter" tick, nothing re-built here.
- Wizard footer for police: primary `<button class="ui-btn ui-btn-primary" type="submit" form="police-form" formaction="/apartments/{{ apartment.id }}/test-connection" formmethod="post">{{ t('apartment.form.test_connection') }}</button>`, replacing "Save and continue". Keep the "Wait" button (no letter yet) as it is. The `return_to` hidden input of `#police-form` becomes the police step URL (`/apartments/{id}/setup/police`), so a failed test shows its error on the police step.
- `test_connection`: after the existing `property_setup.mark_tested(apartment_id)` line, add only this branch (redirect only; the test logic and the save are not touched):
  ```python
  from .onboarding_wizard import wizard_setup_prefix
  if return_to.startswith(wizard_setup_prefix(apartment_id)):
      property_setup.mark_tested_in_wizard(apartment_id)
      property_setup.mark(apartment_id, "police", "done")
      nxt = property_setup.next_applicable_step("police", apartment, lock_available=False) or "done"
      return _back(property_setup.wizard_url(apartment_id, nxt), msg=_flash(request, "flash.apartments.connection_ok"))
  ```
  New in `property_setup.py`: `mark_tested_in_wizard(id)`: `state = load(id)`; `None` returns; else `state["tested"] = True` and `_save`. It writes only an existing stored blob, finished or not (a host who chose Wait, finished, and tests later still reaches the card). `mark_tested` is not changed.
- No JavaScript: if 1100 keeps a server read (`police_letter_read`) as the no-JS path, the wizard's letter form posts a hidden `setup_step=police`, and `police_letter_read` reads it **before** `del letter_text, form` and, when it equals `police`, returns `render_wizard(request, apartment_id, "police", extra=extra, status_code=422)` instead of `_render_property_detail`. If 1100 has no no-JS read, nothing here: the host types the values. `_wizard_context` for `step == "police"` adds the defaults the partial needs (`base_url`, `letter_rows: []`, `letter_prefill: {}`, `letter_status: ""`, `letter_check: None`, `first_setup: True`, `section_done: {"police": False}`, plus any variable 1100 added: list them with `grep -oE '\b(letter_[a-z_]+|first_setup|section_done|police_[a-z_]+)\b' App/app/templates/_police_connection.html | sort -u`).

**D5. Done step = the ready card.** Move the editor's ready-card `<section ...>` (inside `{% if ready_card %}`) into `App/app/templates/_setup_ready_card.html` unchanged; the editor includes it inside its `{% if ready_card %}`. In `_wizard_context` for `step == "done"`: `wizard_ready = bool(state and state.get("tested") and report_complete)` and `ready_qr = payments.qr_data_uri(permalink) if wizard_ready else ""`. In `done.html`, when `wizard_ready and not missing_row`, render the partial in place of the "all set" `setup-wizard-celebrate` banner; keep the summary list, the "next" list and the actions. When police is waiting or untested, `done.html` stays as today ("almost", with the link back to the police step). The done page is a summary: a reload shows the card again (the editor's once-only rule is not used here).

**D6. Short editor.** Stays reachable at `/apartments/{id}?view=settings` for every property. Continue setup card href goes back to `{{ setup_progress.continue_url }}` always (drop the 1099 `first_setup` branch). The archive row `#sec-archive` renders only when `not first_setup`. All other 1099 behaviour stays.

**D7. Wording.** No visible "apartment" on any wizard page (en). URLs (`/apartments/...`) are not copy. If a test finds the word in a string, change the en value to "property" in `host_i18n.py` (the key stays); the guest message textarea is excluded (Q1).

## 3. Files

| Path | Action |
|---|---|
| `App/app/property_setup.py` | add `mark_tested_in_wizard` (D4) |
| `App/app/routes/admin.py` | `apartment_create` redirect (D3); the wizard branch in `test_connection` (D4); `police_letter_read` wizard render branch (D4, only if 1100 kept a server read). No other function. |
| `App/app/routes/onboarding_wizard.py` | `_wizard_context`: police defaults (D4), `wizard_ready`, `ready_qr` (D5) |
| `App/app/templates/_police_connection.html` | create (or reuse 1100's partial) |
| `App/app/templates/_setup_ready_card.html` | create |
| `App/app/templates/_property_editor.html` | include both partials; archive row only when `not first_setup`; Continue setup href |
| `App/app/templates/setup_wizard/police.html`, `done.html` | D4, D5 |
| `App/app/host_i18n.py` | only if D7 finds a string |
| `App/app/static/app2.css`, `base.html`, `tests/static_versions.json` | only if the card or partial needs a wizard-side rule (tokens, under `body.v2`); then bump the `app2.css?v=` key to `20261112-1101a` and regenerate with `.venv/bin/python tests/test_static_versions.py --write` |
| `App/tests/test_setup_wizard_reuse_1101.py` | create (server, no JS) |
| `App/tests/test_setup_wizard_reuse_1101_browser.py` | create (browser, geometry, screenshots) |
| existing tests (section 6) | revert the #899 create-redirect expectations only |
| `docs/tasks/screenshots-1101/`, `docs/tasks/1101-report.md` | create |

## 4. Steps (commit after each: `1101 step k`)

1. `git fetch origin main && git merge origin/main`. `git log origin/main --oneline | grep -i 1100 | head -3`: **empty means 1100 has not merged: STOP**, write the report `Status: blocked: 1100 not merged`, commit, end. Re-grep each anchor in section 2 by its quoted text; a missing one: STOP.
2. Write `test_setup_wizard_reuse_1101.py` (list in step 6) and run it once: it must fail on the unchanged code; put the count in the report.
3. D3 (redirect) and D6 (archive, Continue setup href).
4. D4 partial: reuse or extract; editor includes it. Run the editor rows (section 6, command 1) before going on: the editor must be unchanged.
5. D4 wizard police step: `police.html`, footer, `return_to`, `_wizard_context` defaults, `mark_tested_in_wizard`, the `test_connection` branch, the no-JS `police_letter_read` branch.
6. D5 ready card partial and `done.html`. Then make the new server test green. It covers (plain `TestClient` = no JavaScript):
   - `POST /apartments` (complete form) redirects to `/apartments/{id}/setup/calendar`; with incomplete details the GET lands on the `property` step.
   - Each step GET shows the step indicator (`wiz-count`); calendar has no Back when property was skipped; police and guest link have a Back link to the previous step.
   - Calendar Save/skip goes to `/setup/police`. Police: `fake_client` (from `tests/test_police_letter_flow.py`) `ok` → redirect to `/setup/guest_link`, `load(id)["tested"]` true; `auth` → back to `/setup/police` with the error, `tested` false. Wait → `/setup/guest_link`, `tested` false.
   - Guest link done → `/setup/done`; done shows `data-ready-card`, the guest link, the PIN and `<img src="data:image/png;base64,` only when tested; untested shows the "almost" banner and the police link, no card.
   - Wait, finish, then test from the police step: `tested` becomes true and done shows the card.
   - Police step HTML: the 1100 paste box is there, no "Read the letter" button, no letter tick, the password field is there, the stored password is not in the page.
   - No-JS letter read with `setup_step=police` renders the wizard police step (only if 1100 kept the server read).
   - No `archive` form action on any setup page or on the editor of a first-setup property; a finished property's editor still has `#sec-archive`.
   - No visible "apartment" (en) on property, calendar, police, guest link and done: strip `<script>`, `<style>`, tags, attribute values and the `#wizard-guest-message` textarea, then `assert "apartment" not in text.lower()`.
   - The editor of a finished property still opens at `?view=settings`, police section included.
7. Existing tests: revert the #899 create-redirect expectations to the wizard (`/setup/calendar` in the location, page URL contains `/setup/`), and change only those lines: `test_first_setup_open_section.py::test_create_redirects_to_the_editor` (invert, rename `test_create_redirects_to_the_wizard`), `test_onboarding_wizard_browser.py` (line about 112 and `test_create_lands_on_the_editor_in_first_setup`: assert the wizard instead), `test_property_create_browser.py` and `test_property_navigation_browser.py` (the `"view=settings" in page.url and "/setup/" not in page.url` lines; drop the extra `page.goto(.../setup/calendar)` that #899 added). `test_host_ux_acceptance.py` and `test_host_unsaved_changes_browser.py` use set-up properties: run them, change nothing unless they fail on the redirect. More than 6 files need edits: STOP.
8. `test_setup_wizard_reuse_1101_browser.py` (`UBYHOST_REQUIRE_BROWSER=1`; widths 390, 768, 1280; model the server thread on `test_onboarding_wizard_browser.py`): create a property in the browser and walk calendar → police (paste the sample letter text 1100's tests use, see the fields fill, test with the fake client) → guest link → done with the card; no sideways scroll; footer buttons at least 44 px tall; Back and primary do not overlap; QR at least 120 px and inside the viewport. Once with `java_script_enabled=False` at 390: every step is reachable by its buttons, police is filled by hand, the test passes, the card shows. Screenshots `docs/tasks/screenshots-1101/{calendar,police,guest_link,done}-{390,768,1280}.png` (12, `full_page=True`).
9. UX gate (rules 7 and 10): from `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -rs -x 2>&1 | tail -30`: green, 0 skipped, no new `ALLOW`. Open the 12 screenshots once each. In the report **and the PR** write per page (calendar, police, guest link, done, and the editor of a first-setup property) and per width what you saw. Paste and tick the design-system checklist (`docs/design/design-system.md`, grep the checklist heading, read that range only). A finding is fixed in the template or `app2.css`, never silenced.
10. Section 6 commands, then the report.

## 5. Do not touch

`_run_connection_test` and the save/test logic of `test_connection` (only the added branch), credential handling (`uby_ws_password*`, encryption, the password never rendered), `App/app/ubyport/`, `reporting.py`, `police_letter.py` parsing, filing and `submit_state`, 1100's paste/autofill code and JS, `app.js`, `STEPS`/`RETIRED_STEPS`, `setup_action`, `mark_tested`, `onboarding.py`, `db.py`, migrations, `retention.py` (`tested` is a non-personal boolean), any dependency, `ALLOW` in `test_layout_lint_browser.py`. Never push to `main`.

## 6. Commands (each ends `2>&1 | tail -30`; never the full suite)

From `App/`:

1. Server (rows: Onboarding and properties, Copy and translations, Static files): `.venv/bin/python -m pytest tests/test_setup_wizard_reuse_1101.py tests/test_first_setup_open_section.py tests/test_onboarding.py tests/test_onboarding_wizard_survival.py tests/test_wizard_four_steps_0884.py tests/test_wizard_friendly_0273.py tests/test_wizard_old_look_0953.py tests/test_wizard_try_it_0884.py tests/test_finish_moment_0274.py tests/test_setup_banner.py tests/test_police_letter_flow.py tests/test_property_readiness.py tests/test_property_form_save.py tests/test_0534_property_page_v2.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_privacy_first.py -q --tb=short -x` (add 1100's new server test file).
2. Browser, 0 skipped (Host pages row): `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_setup_wizard_reuse_1101_browser.py tests/test_onboarding_wizard_browser.py tests/test_property_create_browser.py tests/test_property_navigation_browser.py tests/test_host_ux_acceptance.py tests/test_host_unsaved_changes_browser.py tests/test_host_short_editor_browser.py tests/test_host_police_letter_browser.py tests/test_0884_wizard_geometry_browser.py tests/test_design_setup_wizard_browser.py tests/test_wizard_old_look_0953_browser.py tests/test_host_geometry.py tests/test_layout_lint_browser.py tests/test_design_guardrails_browser.py -q --tb=short -rs` (add 1100's browser file).
3. v2 row: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q --tb=short -rs`.

Repo root: `python3 scripts/design_lint.py 2>&1 | tail -30` and `python3 scripts/context_lint.py 2>&1 | tail -30`.

Known failures on clean main (name them, do not fix): `test_host_ux_acceptance.py` guide page, `test_reporting_help_0097.py`.

## 7. Acceptance

- [ ] `POST /apartments` lands on the wizard; a new property is walked property (if needed) → calendar → police → guest link → done, each Save going to the next step, with Back and the step indicator on every step after the first.
- [ ] The police step shows 1100's paste-and-autofill block from the same partial as the editor (no copy of it); no Read button, no letter tick; a passing test goes to the next step and sets `tested`; a failed test stays on police with the error.
- [ ] Done shows the 1099 ready card (link, PIN, QR) once police is tested; otherwise "almost" with the way back to police.
- [ ] No archive control on any setup page or on a first-setup editor; no visible "apartment" on setup pages (en).
- [ ] Works without JavaScript end to end (server test plus the no-JS browser run).
- [ ] The editor still opens for a set-up property and renders as before (editor tests unchanged and green).
- [ ] `git diff origin/main -- App/app/ubyport App/app/reporting.py App/app/police_letter.py App/app/onboarding.py` is empty; in `admin.py` only the three named places changed.
- [ ] New server test failed before (count in report) and passes after; browser tests 0 skipped; layout lint green, no new `ALLOW`; 12 screenshots and per-page notes in the report and PR; checklist ticked; no new dependency, no schema change, no outbound request.

## 8. Stop and ask

STOP and report `blocked` if: 1100 has not merged; an anchor is missing; 1100's police block cannot be included in the wizard form without changing 1100's JS or field names; a step needs `app.js`, a migration, a dependency or a change to the test logic; `permalink` or `pin` is missing from the done context; a test fails twice on the same cause; more than 6 existing test files need edits; 30 tool calls (finish the step, commit, `Done: steps 1 to k. Left: steps k+1 to 10.`).

## 9. Report

`docs/tasks/1101-report.md` (executor.md format): files changed, each command with its last 5 lines and counts (0 skipped), the failing count from step 2, the per-page and per-width notes, the ticked checklist, the 12 screenshot names, every existing test expectation changed (names), and anything left.

## 10. Open questions for the owner (do not block the build)

- Q1: The guest message template on the guest link step says "Find your apartment" and "in the apartment" (it is text the host sends to guests). Change it to "property" too, or keep it as guest-facing wording?
- Q2: The wizard asks for the calendar before police (its 0270 order). Keep that, or police first?
