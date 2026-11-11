# 1099: one short property editor for everyone, first setup included

Status: todo
Tier: B | Depends on: 1097 (police check step and phone layout; branch claude/1097-police-one-tick; must be merged to main first) | Base commit: b7e65d3e (anchors below are at this commit; they shift after 1097, so re-grep by the quoted text) | Branch: claude/1099-short-editor
Executor: Opus (Tier B) | Attempts: 3 at most | Fits one session: stop at 60 tool calls (section 8); reads stay at 150 lines or fewer
Report: docs/tasks/1099-report.md

## 1. Objective

Owner decision (Josef, 2026-11-11): one short property editor for everyone, first setup included. No separate guided 9-screen flow. Sources: `/mnt/project-files/mockups/README.md` "Part 2: host setup" and the shots `short-editor-*.png` and `today-*.png` in `/mnt/project-files/mockups/host-setup/` (the `guided-*.png` are reference only; do not build them). Read the README with `sed -n 14,24p`. Open `short-editor-390-full.png` once.

What this brief builds, on top of the editor that exists (`_property_editor.html`):

1. **Short editor (all states).** Sections start closed. Each header shows its state (done, or what is missing) and an estimate in minutes. Labels in plain words. The police letter picture is inline in the police section. Help stays behind the existing "?" at each field; no new always-visible help text.
2. **First-setup mode** (a new property, or setup not complete). Only the first incomplete section is open. Saving it opens the next incomplete one. Server-driven, so it works without JavaScript.
3. **Police section first.** In first-setup mode the police section opens with the letter paste box and the letter picture at the top. The 1085/1086 paste flow stays as it is.
4. **Complete only after the test passes.** "Save and test connection" (the existing UbyPort route) must pass before setup counts as complete.
5. **"You're ready" card**, once, with the guest link and a QR code.
6. **Later edits:** every section closed, each with its state.

### Builds on 1097 (do not re-specify it)

1097 changes the police section's check step and the phone layout of the police fields. This brief builds on top of 1097 after 1097 merges. Step 1 merges `origin/main` and STOPs if 1097 is not in it. Whatever 1097 did to `#ubyport`, `#police-letter-check`, the tick rows and `app2.css` stays as 1097 left it; this brief only changes which things are open, the header text, the labels, and the ready card.

## 2. Context (verified with grep at b7e65d3e)

### What exists

- **Editor:** `App/app/templates/_property_editor.html` (571 lines). Sections are `details.prop-sec`: `sec-basics` (152), `sec-messages` (223), `sec-police` (301), `sec-fee` (423), `sec-calendars` (479), `sec-lock` (487). Each header is `<summary><span class="dot ..."><div><b>title</b></div><small class="sec-state">state</small></summary>`. Today each `open` attribute comes from `inline_flash_section`, `settings_section` or `save_errors`. Quirk: `sec-basics` opens whenever `settings_section` is empty or `property`, and `_property_view_state` (`routes/admin.py:1906`) maps a missing `?section=` to `property`. So today Basic details is open by default.
- **Desktop:** at 768 px and up, `app.js` (`initPropertyLayout`, the `apply()` block near line 2723) shows one section at a time as tabs (`is-tabbed`), starting at `data-start-section` (template line 130), else the first `[open]`, else the first section. That 1030 design stays. "Sections start closed" is the phone accordion (`app2.css:1035`, `details.prop-sec:not([open])>:not(summary)` hidden). On desktop the server's open section is the starting tab, via `data-start-section`.
- **Police section** (`sec-police`, line 301): `#ubyport` (305); `details.police-letter-find` (313, includes `_police_letter_figure.html`); `details.police-letter-paste#police-letter-paste` (317, `open` only on `letter_status` empty/too_long/failed); check block `#police-letter-check`; fields (IDUB, login, password `#uby_ws_password` 360, short name, facility name, contact); the button `formaction="{{ base_url }}/test-connection"` (385, key `apartment.form.test_connection`); `#police-letter-form` (476). Do not change names, hidden inputs, `required`, `autofocus`, `form` or `data-*` attributes.
- **Setup state** (no schema): `App/app/property_setup.py` keeps a JSON blob per property in `db.get_setting("property_setup:<id>")` (`_key` 78, `load` 86, `_save` 119, `start` 135, `mark` 139, `finish` 158, `celebrate_once` 165). Fields: `steps`, `finished`, `hidden`, `legacy`, `celebrated`. `STEPS = (property, calendar, police, guest_link)` (16). `property_details_complete` (271) is the "Basic details done" test. `routes/admin.py`: `_setup_state` (1945), `_setup_guide_bundle` (1968; gives `state`, `report_complete`, `feeds`, `facts_payload`), `apartment_detail` render context (about 2140-2210; it already passes `setup_progress`, `setup_checklist`, `setup_finished`, `permalink`, `pin`, `has_password`).
- **Old guided wizard:** `routes/onboarding_wizard.py` (`/apartments/{id}/setup/{step}`, line 301) and `apartment_create` (`routes/admin.py:1877`) redirect a new property to `/setup/calendar`. The "Continue setup" card is in `_property_editor.html:70-86`. This brief does not delete the wizard. It stops sending new properties there (step 5) and leaves its routes and tests alone.
- **Connection test:** `test_connection` (`routes/admin.py:3483`) calls `_run_connection_test` (3523, returns `ok|auth|unreachable`). `apartment_update` auto-runs it (call at 2619, `ok` at 2621) only with `letter_fields` and a password, and never with `setup_step`. Flashes: `letter_test_ok`, `letter_saved_untested`, `connection_ok`.
- **QR:** `payments.qr_data_uri(payload) -> "data:image/png;base64,..."` (`App/app/payments.py:162`, uses `qrcode[pil]`, already in `requirements.txt:14`). `guide_token.qr_png` (`guide_token.py:65`) is the PNG variant. Use `payments.qr_data_uri`. No new dependency, no outbound request, no new route.
- **Guest link:** context `permalink` (`.../l/<key>`) and `pin`; `copy_inline` macro in `_components.html:337`.
- **i18n:** host strings live in `App/app/host_i18n.py` (per-language dicts, blocks such as `_PROPERTY_NAV_0094_STRINGS` at about 8067 that end with `for _lang, _strings in ...: STRINGS[_lang].update(_strings)`). Host languages for the parity test: **en and cs** (`test_english_and_czech_carry_the_same_keys`, `App/tests/test_host_i18n.py:57`). Vietnamese (`host_vi_i18n.py`) falls back to English; do not add vi keys (`test_every_vietnamese_key_exists_in_english...` only checks keys that exist).
- **Cache keys on main:** `app2.css?v=20261110-1086b` (`base.html:23`), `app.js?v=20261110-1096a` (`base.html:47`), `host.css?v=20261108-1010a`. Re-read them after merging 1097.
- **CSS:** `App/app/static/app2.css`, every rule under `body.v2`. Existing hooks: `.sec-state` (line 1000 hides it at wide, 1012 shows it on phone), summary grid (1013-1019), `prop-sec` card styling (2860-2864, 3051).

### Data model decision: no schema change

Everything fits the existing settings blob and existing facts. No migration (next free would be 0044; not needed). The blob gains two booleans, `tested` and `ready_shown`... but `celebrated` already exists and is the "shown once" flag, so only **`tested`** is new. These are non-personal booleans: no `retention.py` line.

## 2b. Design

### 3a. "Section done" state (pure function, no new queries)

Add to `property_setup.py`:

```
SECTION_MINUTES = {"basics": 2, "police": 3, "calendars": 1, "messages": 2, "fee": 3, "lock": 5}
SETUP_ORDER = ("basics", "police")      # sections that open one after another; calendar, guest link, fee, lock never gate
def mark_tested(apartment_id)            # load(...) or legacy_state(); set state["tested"] = True; _save (not when finished)
def is_first_setup(state)                # state is not None and not finished and not hidden  (legacy included: "setup not complete")
def section_done(key, apartment, facts, state) -> bool
def open_section(apartment, facts, state) -> Optional[str]   # "basics" | "police" | None
def setup_complete(apartment, facts, state) -> bool          # basics done and police done
```

`load` and `_save` carry `tested` (default False), like `celebrated`. `section_done`:

| Section | Done when | Existing source |
|---|---|---|
| basics | `property_details_complete(apartment)` | line 271 |
| police | `facts["report_complete"]` **and** `state["tested"]` (first-setup mode); `facts["report_complete"]` alone (not first-setup) | `_setup_guide_bundle` `report_complete` |
| calendars | `feeds > 0` or `stays > 0` (display only) | `facts_payload` |
| messages (guest link) | display only, no done state: "Optional" | n/a |
| fee | `apartment.stay_fee_rate_czk` > 0 | |
| lock | `door_code.state == "on"` | template `door_code` |

`open_section` returns the first key of `SETUP_ORDER` that is not done, or None when both are done. Unit-test it as a pure function.

### 3b. Where `tested` is set (the test logic is not changed)

Do not edit `_run_connection_test`. Call `property_setup.mark_tested(apartment_id)` only at the two call sites that already hold `outcome == "ok"`:
- `test_connection` just before its `connection_ok` redirect (`routes/admin.py` about 3519-3520).
- `apartment_update` in the `if outcome == "ok":` branch (about 2620).
A failed test, or "saved untested", never sets it.

### 3c. Ready card (shown once)

In `apartment_detail`, after building the bundle: if `is_first_setup(state)` and `setup_complete(...)` then `property_setup.finish(apartment_id)`; set `ready_card = property_setup.celebrate_once(apartment_id)` (True only the first time after finishing). Pass `ready_card`, and `ready_qr = payments.qr_data_uri(permalink) if ready_card else ""`. Template: at the top of the editor (before the section list), if `ready_card`, one card (`ui-section-card`, no nested box): title "You're ready", one line, the guest link with `copy_inline`, the PIN with `copy_inline`, the QR `<img src="{{ ready_qr }}" alt=...>` with fixed width/height attributes, no coral background. Never shown again after one render (`celebrated`). A property already `finished` before this change never gets the card.

### 3d. Which sections are open (server decides; no JavaScript needed)

Add a Jinja macro `sec_open(id)` at the top of `_property_editor.html` and use it in all six `<details class="prop-sec">` openers, replacing the five inline `open` conditions. Context added in `apartment_detail`: `first_setup` (bool), `setup_open` (`"sec-basics"`, `"sec-police"` or `""`), `section_explicit` (`True` when `?section=` is in the query string).

- **Always open** (both modes): a section with `save_errors` for it; the police section when `letter_rows` or `letter_status` is set (1085 flow); the section named by an explicit `?section=` or by `inline_flash_section` when the flash is an error. A hash deep link (`#ubyport`) keeps working through the existing JS and `:target`; do not remove it.
- **First-setup mode:** additionally open exactly `setup_open`. The default-open rule for `sec-basics` is dropped. Saving a section posts to the existing routes, which redirect back to the property page, and the next GET computes the next `setup_open`. A success flash for a section that is now done needs no extra display: its header flips to "Done". The in-section error flashes keep their section open (rule above).
- **Later edits (not first-setup):** everything closed unless one of the "always open" signals holds. Drop the `settings_section in [...]` conditions unless `section_explicit`.
- `data-start-section` (line 130): `sec-police` for the letter flow (keep), else `setup_open` in first-setup mode, else as today. At 768 px and up the tab shown is that section.
- The hidden `return_to` input (line 143, `section={{ settings_section }}`) must not force Basic details open: in first-setup mode post back to `?view=settings` with no `section`. Check the redirects of `apartment_update` keep that (grep `property-return` in `app.js` if it rewrites the value; if JS rewrites it with the active tab, that is fine because the server still computes `setup_open` first when `section_explicit` is false).

### 3e. Section header: state and minutes

Replace the `.sec-state` text of each summary with one line: `{state}` and, when the section is not done, ` · {minutes}`. Reuse existing state strings where they exist (`property_nav.address_missing`, `property_nav.report_ready`, `property_nav.report_missing`, `apartment.form.calendars_count`, `apartments.chip_state.off`, `property_nav.switch_enabled`, `property_nav.switch_off`). New keys (add to en and cs together, one new block `_SHORT_EDITOR_1099_STRINGS` placed after the last `STRINGS[_lang].update` block):

| Key | en | cs |
|---|---|---|
| `setup.sec.done` | Done | Hotovo |
| `setup.sec.minutes` | about %(n)s min | asi %(n)s min |
| `setup.sec.optional` | Optional | Nepovinné |
| `setup.sec.recommended` | Recommended | Doporučeno |
| `setup.sec.police_untested` | Saved, not tested yet | Uloženo, zatím netestováno |
| `setup.label.idub` | Accommodation number (IDUB) | Číslo ubytování (IDUB) |
| `setup.label.login` | Login from the police letter | Přihlášení z dopisu od policie |
| `setup.label.password` | Password from the police letter | Heslo z dopisu od policie |
| `setup.label.mark` | Short name (zkratka) | Krátký název (zkratka) |
| `setup.label.facility` | Facility name on the letter | Název zařízení z dopisu |
| `setup.ready.title` | You're ready | Máte hotovo |
| `setup.ready.text` | Send this link and PIN to your guests. | Pošlete hostům tento odkaz a PIN. |
| `setup.ready.qr_alt` | QR code for the guest link | QR kód odkazu pro hosty |

Police header in first-setup mode: `report_missing` text if the report is incomplete; `setup.sec.police_untested` if complete but not tested; `setup.sec.done` once tested. Outside first-setup mode keep `property_nav.report_ready` / `report_missing`. Minutes come from `SECTION_MINUTES` (pass it to the template as `section_minutes`). CS is written so the em dash rule and `test_no_em_dashes.py` pass; no "cookies" wording.

Labels: use the five `setup.label.*` keys on the police fields **in the editor only** (do not edit `apartment.form.ubyport.idub_label`, `automation.login`, `automation.password`, `automation.facility_name` or `apartment.form.ubyport.mark_label`, which other pages use). Keep each field's "?" help exactly as is. Contact at registration keeps `automation.contact`.

### 3f. Police section in first-setup mode

`details.police-letter-find` and `details.police-letter-paste` render with `open` while `first_setup` and the police section is not done and no letter flow is active (the 1085 `letter_status` rule for `paste` stays). Order inside `#ubyport` stays: letter picture, paste box, check block, fields, the test button. In later-edit mode they stay closed disclosures as 1085 settled them. Do not touch 1097's check step.

### 3g. Stop sending new properties to the wizard

`apartment_create` (`routes/admin.py:1877`) redirects to `/apartments/{id}?view=settings` (keep the `flash.apartments.created` message) instead of `/setup/calendar`. `property_setup.start()` is still called (it creates the first-setup state). The "Continue setup" card (`_property_editor.html:70`) stays for hidden/legacy cases but its link is changed to `/apartments/{id}?view=settings` when `first_setup`. Wizard routes and tests stay untouched; retiring them is a later brief (owner question in the report).

## 3. Files

| Path | Action | What |
|---|---|---|
| `App/app/property_setup.py` | edit | `tested` in `load`/`_save`; `SECTION_MINUTES`, `SETUP_ORDER`, `mark_tested`, `is_first_setup`, `section_done`, `open_section`, `setup_complete` (3a) |
| `App/app/routes/admin.py` | edit | `mark_tested` at the two `ok` call sites (3b); `apartment_detail` context and ready-card logic (3c, 3d); `apartment_create` redirect (3g). No other function. |
| `App/app/templates/_property_editor.html` | edit | `sec_open` macro and the six openers; header state line; labels; `open` on the two police disclosures; ready card; `data-start-section` |
| `App/app/host_i18n.py` | edit | the new en and cs block (3e) |
| `App/app/static/app2.css` | edit | ready card and header state line, under `body.v2`, tokens only |
| `App/app/templates/base.html` | edit | line 23: `app2.css?v=` becomes `20261111-1099a` (next letter if 1097 already used that date key) |
| `App/tests/static_versions.json` | regenerate | from `App/`: `.venv/bin/python tests/test_static_versions.py --write` |
| `App/tests/test_first_setup_open_section.py` | create | server tests (step 3) |
| `App/tests/test_host_short_editor_browser.py` | create | browser, no-JS and geometry tests (step 4) |
| `docs/tasks/screenshots-1099/` | create | the PNGs |
| `docs/tasks/1099-report.md` | create | the report |

`app.js` and its key stay unchanged. If a step seems to need JavaScript, STOP.

## 5. Do not touch

`_run_connection_test` and `test_connection` logic (only the one added `mark_tested` line after `ok`), UbyPort credential handling (`uby_ws_password*`, `reporting.client_for`, encryption, the password never rendered), anything under `App/app/ubyport/`, `reporting.py`, filing and submission (`submit_state`, worker, watchdog), `police_letter.py` and the 1085/1086 flow logic (names, hidden inputs, `required`, `autofocus`, `form`, `data-*`, the `req-star` and `police-letter-note` classes), 1097's changes, `app.js`, `host.css`, `validation.py`, `db.py` and migrations, `routes/onboarding_wizard.py`, `retention.py`, any dependency, `ALLOW` in `test_layout_lint_browser.py`. Never push to `main`.

## 4. Steps (commit after each: `1099 step k`)

1. `git fetch origin main`, `git merge origin/main`. Confirm 1097 is in main: `git log origin/main --oneline | grep -i 1097 | head -3` and `ls docs/tasks/1097-report.md`. **If 1097 has not merged: STOP** (report `blocked: 1097 not merged`). Re-grep every anchor in section 2 by its quoted text (`sec-police`, `police-letter-find`, `police-letter-paste`, `formaction="{{ base_url }}/test-connection"`, `def mark(`, `def celebrate_once`, `def _run_connection_test`, `qr_data_uri`, `app2.css?v=`). A missing one: STOP.
2. Implement 3a to 3g (section 2b) (`property_setup.py`, `admin.py`, template, i18n, CSS, cache key). Keep each section's inner fields untouched. Run the test-map rows for `test_first_*` and the copy row (section 6) once to catch breakage.
3. `test_first_setup_open_section.py` (plain `TestClient`, which is the no-JavaScript case; parse the HTML for `open` on each `details.prop-sec`):
   - `open_section` and `section_done` as pure functions: new property, basics done, police filled but untested, police tested.
   - New property (just created, police empty): only `sec-police` is open; `sec-basics` is closed and says Done; the police header shows the missing text and "about 3 min"; the letter find and paste `details` are open.
   - Police fields saved, test not run: police still open, header says "Saved, not tested yet"; no ready card.
   - Test passes (`fake_client` from `tests/test_police_letter_flow.py`, imported as the other test files do): `state.tested` is true, the page shows the ready card exactly once with the guest link, the PIN and an `<img src="data:image/png;base64,`; a second GET shows no card and all sections closed.
   - Test fails (`auth`): `tested` stays false, no card, police open with the error.
   - Saving basics (a valid edit) in first-setup mode: the next GET opens police and closes basics.
   - A finished property (state `finished`): all sections closed, each header has a state; no card; a `?section=reporting` link opens only that one.
   - A save error in one section keeps that section open.
   - `apartment_create` redirects to `/apartments/{id}?view=settings`.
   - `mark_tested` is not called when the test returns `auth` or `unreachable`; the password is not in the page.
4. `test_host_short_editor_browser.py` (width parametrized 390, 768, 1280; `UBYHOST_REQUIRE_BROWSER=1`; model the server thread and session on `test_host_police_letter_browser.py` or `test_0833_property_editor_browser.py`):
   - New property at 390: one section open, the rest closed; headers show state and minutes; no sideways scroll; each summary at least 44 px.
   - Mid-setup (police saved, untested) at the three widths.
   - Ready card at the three widths: card, link, QR (natural size at least 120 px, inside the viewport), no overlap, 12 px gaps.
   - Later edit (finished property) at the three widths: all closed on the phone, the start tab at 768/1280 is the first section.
   - No JavaScript (`java_script_enabled=False`): the new property shows police open; saving basics opens the next incomplete section; the test flow reaches the ready card.
   - Screenshots into `docs/tasks/screenshots-1099/`: `new-`, `mid-`, `ready-`, `edit-` each at 390, 768, 1280 (12 files, `page.screenshot(full_page=True)`).
5. **UX gate (rules 7 and 10):** from `App/`: `UBYHOST_REQUIRE_BROWSER=1 UBYHOST_SHOTS_DIR=/tmp/shots .venv/bin/python -m pytest tests/test_layout_lint_browser.py -q -x 2>&1 | tail -30`, green, 0 skipped, no new `ALLOW`. Open the 12 screenshots and the lint shots for the property settings page. In the report write, per page and state (new property, mid-setup, ready, later edit) and per width, what you saw. Paste and tick the design-system section 5 checklist in the report (and in the PR). A finding is fixed in the template or `app2.css`, never silenced.
5. Section 6 commands, then the report. Update `docs/context/status.md` (5 lines at most) only if the owner asks; the orchestrator does that.

## 6. Commands (each ends `2>&1 | tail -30`; no full suite)

From `App/`:

1. Server: `.venv/bin/python -m pytest tests/test_first_setup_open_section.py tests/test_police_letter_flow.py tests/test_onboarding.py tests/test_property_page.py tests/test_host_i18n.py tests/test_no_em_dashes.py tests/test_copy_cleanup.py tests/test_flash_literals.py tests/test_static_versions.py tests/test_wp07_cache_heartbeats.py tests/test_privacy_first.py -q --tb=short -x` (test-map rows: Onboarding and properties, Copy and translations, Static files).
2. Browser, 0 skipped: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_host_short_editor_browser.py tests/test_host_police_letter_browser.py tests/test_host_police_letter_guard_browser.py tests/test_0833_property_editor_browser.py tests/test_property_navigation_browser.py tests/test_host_geometry.py tests/test_layout_lint_browser.py tests/test_design_guardrails_browser.py tests/test_a11y_guard_browser.py tests/test_required_stars.py tests/test_onboarding_wizard_browser.py -q --tb=short -rs` (test-map row: Host pages; if a police-letter browser file is not on main, drop it).
3. v2 row: `UBYHOST_REQUIRE_BROWSER=1 .venv/bin/python -m pytest tests/test_0710_v2_mockup_match_browser.py -q --tb=short -rs`.

Repo root: `python3 scripts/design_lint.py 2>&1 | tail -30` and `python3 scripts/context_lint.py 2>&1 | tail -30`.

Existing tests that pin the old open rules (Basic details open by default, the 1085 `details` closed) may need an expectation change. Change only the open-state expectation, nothing else. If more than 6 existing test files need that, STOP and report. Two failures are known on clean main (`test_host_ux_acceptance.py` guide page; `test_reporting_help_0097.py`); name them, do not fix.

## 7. Acceptance

- [ ] A new property opens with only the police section open (no JavaScript needed); saving a section opens the next incomplete one.
- [ ] Setup is complete only after the connection test passes; a failed or untested save never completes it.
- [ ] The ready card shows once, with the guest link, the PIN and a QR code; never twice; never for a property that was already finished.
- [ ] Later edits: all sections closed on the phone, each header shows its state; minutes only on sections not done.
- [ ] Police labels in plain words (en and cs); help only behind the existing "?"; no new always-visible text.
- [ ] `test_connection`, `_run_connection_test`, credential handling and filing are unchanged (`git diff origin/main -- App/app/ubyport App/app/reporting.py App/app/police_letter.py` is empty; the diff in `admin.py` touches only the lines named in section 3).
- [ ] en and cs keys match; no em dash; `app2.css` key bumped; `static_versions.json` regenerated; no new dependency; no schema change.
- [ ] Layout lint green, 0 skipped, no new `ALLOW`; browser tests 0 skipped; 12 screenshots and per-page notes in the report and PR; design-system checklist ticked.
- [ ] The PR says why no outbound request was added (the QR is generated locally).

## 8. Stop and ask

STOP and report `blocked` if: 1097 has not merged; an anchor is missing; a step needs JavaScript, a migration, a new dependency, a route change beyond section 4, a change to the connection-test logic, or a change to 1097's work; the host CSP blocks a `data:` image for the QR (the guest fee page already uses `qr_data_uri`, so check how it is allowed before changing anything); the existing flash for an error does not keep its section open; a test fails twice on the same cause (attempt 3 of 3); more than 6 existing test files need an open-state edit; 60 tool calls (finish the step, commit, write `Done: steps 1 to k. Left: steps k+1 to 5.`).

## 9. Report

`docs/tasks/1099-report.md`: what changed (files), the test results (commands and counts, 0 skipped), the per-page and per-width notes for the four states, the ticked checklist, the 12 screenshot names, any existing test expectation you changed (names), and anything left.
